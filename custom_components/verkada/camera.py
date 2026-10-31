"""Verkada cameras with HA-proxied HLS and cached cloud thumbnails."""

import time

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .api import VerkadaError
from .entity import VerkadaEntity

PARALLEL_UPDATES = 2


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    known = set()

    @callback
    def discover():
        new = set(coordinator.data) - known
        async_add_entities(VerkadaCamera(coordinator, cid) for cid in new)
        known.update(new)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


class VerkadaCamera(VerkadaEntity, Camera):
    _attr_name = None
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_is_streaming = False

    def __init__(self, coordinator, camera_id):
        Camera.__init__(self)
        VerkadaEntity.__init__(self, coordinator, camera_id)
        self._image = None
        self._image_at = 0
        self._renewing = False
        self._stream_jwt = None

    @property
    def available(self):
        return super().available and str(
            self.coordinator.data.get(self.camera_id, {}).get("status", "")
        ).lower() in ("live", "online")

    async def async_camera_image(self, width=None, height=None):
        if self._image is not None and time.monotonic() - self._image_at < 60:
            return self._image
        try:
            self._image = await self.coordinator.api.thumbnail(
                self.camera_id, self.coordinator.options["high_resolution"]
            )
            self._image_at = time.monotonic()
            return self._image
        except VerkadaError:
            return None

    async def stream_source(self):
        try:
            url = await self.coordinator.api.stream_url(
                self.camera_id, high=self.coordinator.options["high_resolution"]
            )
            self._stream_jwt = self.coordinator.api._jwt
            return url
        except VerkadaError as err:
            raise HomeAssistantError(str(err)) from err

    @callback
    def _handle_coordinator_update(self):
        if (
            self.stream
            and not self._renewing
            and (
                time.monotonic() >= self.coordinator.api._jwt_until
                or self._stream_jwt != self.coordinator.api._jwt
            )
        ):
            self._renewing = True
            self.hass.async_create_task(self._renew_stream())
        super()._handle_coordinator_update()

    async def _renew_stream(self):
        try:
            if self.stream:
                self.stream.update_source(await self.stream_source())
        except HomeAssistantError:
            pass
        finally:
            self._renewing = False
