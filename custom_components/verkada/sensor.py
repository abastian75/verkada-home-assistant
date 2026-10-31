"""Last plate, camera diagnostics and explicit source health."""

from datetime import datetime, timezone

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .entity import VerkadaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    hub = entry.runtime_data
    async_add_entities([SourceSensor(hub)])
    known = set()
    known_plates = set()
    registry = er.async_get(hass)

    # Keep entity IDs, user names and recorder history when retiring legacy plate sensors.
    for item in er.async_entries_for_config_entry(registry, entry.entry_id):
        for suffix in ("_last_plate", "_last_seen"):
            prefix = f"{entry.unique_id}_"
            if item.unique_id.startswith(prefix) and item.unique_id.endswith(suffix):
                cid = item.unique_id[len(prefix) : -len(suffix)]
                updates = {}
                if cid not in hub.plate_camera_ids:
                    if item.disabled_by is None:
                        updates["disabled_by"] = er.RegistryEntryDisabler.INTEGRATION
                    if item.hidden_by is None:
                        updates["hidden_by"] = er.RegistryEntryHider.INTEGRATION
                else:
                    if item.disabled_by == er.RegistryEntryDisabler.INTEGRATION:
                        updates["disabled_by"] = None
                    if item.hidden_by == er.RegistryEntryHider.INTEGRATION:
                        updates["hidden_by"] = None
                if updates:
                    registry.async_update_entity(item.entity_id, **updates)

    @callback
    def discover():
        new = set(hub.data) - known
        async_add_entities(CameraSensor(hub, cid, "firmware", "Firmware status") for cid in new)
        new_plates = hub.plate_camera_ids - known_plates
        async_add_entities(
            entity
            for cid in new_plates
            for entity in (
                CameraSensor(hub, cid, "last_plate", "Last plate"),
                CameraSensor(hub, cid, "last_seen", "Plate last seen"),
            )
        )
        known.update(new)
        known_plates.update(new_plates)

    discover()
    entry.async_on_unload(hub.async_add_listener(discover))


class SourceSensor(VerkadaEntity, SensorEntity):
    _attr_name = "Event sources"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hub):
        super().__init__(hub)
        self._attr_unique_id += "_sources"

    @property
    def native_value(self):
        return (
            "error"
            if any(s["state"] != "ok" for s in self.coordinator.status.values())
            else "ok"
            if self.coordinator.status
            else "disabled"
        )

    @property
    def extra_state_attributes(self):
        return {
            "sources": self.coordinator.status,
            "last_poll": self.coordinator.last_poll,
            "last_webhook": self.coordinator.last_webhook,
            "stored_events": len(self.coordinator.events),
        }


class CameraSensor(VerkadaEntity, SensorEntity):
    def __init__(self, hub, camera_id, key, name):
        super().__init__(hub, camera_id)
        self.key = key
        self._attr_name = name
        self._attr_unique_id += "_" + key
        if key == "firmware":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if key == "last_seen":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        if self.key == "firmware":
            return self.coordinator.data.get(self.camera_id, {}).get("firmware")
        event = next(
            (
                e
                for e in self.coordinator.events
                if e["camera_id"] == self.camera_id and e.get("plate")
            ),
            None,
        )
        if event is None:
            return None
        if self.key == "last_seen":
            return datetime.fromtimestamp(event["timestamp"], timezone.utc)
        return event["plate"]

    @property
    def extra_state_attributes(self):
        if self.key == "firmware":
            return None
        hub = self.coordinator
        status = hub.status.get(f"lpr:{self.camera_id}") or hub.status.get("helix", {})
        state = (
            "source_error"
            if status.get("state") == "error"
            else "tracking"
            if self.native_value is not None
            else "no_detections"
        )
        return {
            "tracking_status": state,
            "source_status": status.get("state", "waiting"),
            "source_message": status.get("message"),
            "last_success": status.get("last_success"),
        }
