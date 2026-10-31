"""Event entity usable in standard Home Assistant dashboards and automations."""

from homeassistant.components.event import EventEntity
from homeassistant.core import callback

from .entity import VerkadaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([VerkadaEvent(entry.runtime_data)])


class VerkadaEvent(VerkadaEntity, EventEntity):
    _attr_name = "Latest event"
    _attr_event_types = ["alert", "lpr", "helix", "webhook"]

    def __init__(self, hub):
        super().__init__(hub)
        self._attr_unique_id += "_event"
        self._last_id = None

    @callback
    def _handle_coordinator_update(self):
        event = self.coordinator.last_event
        if event and event["id"] != self._last_id:
            self._last_id = event["id"]
            self._trigger_event(event["source"], {k: v for k, v in event.items() if k != "source"})
        super()._handle_coordinator_update()
