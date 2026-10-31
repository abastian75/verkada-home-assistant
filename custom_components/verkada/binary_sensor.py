"""Online state is diagnostic; it is not an inferred door or alarm state."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback

from .entity import VerkadaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    hub = entry.runtime_data
    known = set()

    @callback
    def discover():
        new = set(hub.data) - known
        async_add_entities(OnlineSensor(hub, cid) for cid in new)
        known.update(new)

    discover()
    entry.async_on_unload(hub.async_add_listener(discover))


class OnlineSensor(VerkadaEntity, BinarySensorEntity):
    _attr_name = "Connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hub, camera_id):
        super().__init__(hub, camera_id)
        self._attr_unique_id += "_connected"

    @property
    def is_on(self):
        return str(self.coordinator.data.get(self.camera_id, {}).get("status", "")).lower() in (
            "live",
            "online",
        )
