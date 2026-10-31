"""Shared device metadata."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class VerkadaEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, camera_id=None):
        super().__init__(coordinator)
        self.camera_id = camera_id
        self._attr_unique_id = f"{coordinator.entry.unique_id}_{camera_id or 'organization'}"

    @property
    def device_info(self):
        if self.camera_id is None:
            return DeviceInfo(
                identifiers={(DOMAIN, self.coordinator.entry.unique_id)},
                name=self.coordinator.entry.title,
                manufacturer="Verkada",
                model="Command organization",
            )
        camera = self.coordinator.data.get(self.camera_id, {})
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.entry.unique_id}_{self.camera_id}")},
            name=camera.get("name", self.camera_id),
            manufacturer="Verkada",
            model=camera.get("model"),
            serial_number=camera.get("serial"),
            suggested_area=camera.get("site"),
            via_device_id=self.coordinator.device_id,
        )

    @property
    def available(self):
        return super().available and (
            self.camera_id is None or self.camera_id in self.coordinator.data
        )
