"""Last plate, camera diagnostics and explicit source health."""

from datetime import datetime, timezone

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback

from .entity import VerkadaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    hub = entry.runtime_data
    async_add_entities([SourceSensor(hub)])
    known = set()

    @callback
    def discover():
        new = set(hub.data) - known
        async_add_entities(
            entity
            for cid in new
            for entity in (
                CameraSensor(hub, cid, "last_plate", "Last plate"),
                CameraSensor(hub, cid, "last_seen", "Plate last seen"),
                CameraSensor(hub, cid, "firmware", "Firmware status"),
            )
        )
        known.update(new)

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
