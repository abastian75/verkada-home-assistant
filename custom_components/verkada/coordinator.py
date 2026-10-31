"""Camera discovery, independent source health, bounded event history."""

import logging
import time
from datetime import timedelta

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthenticationError, VerkadaError
from .const import DEFAULT_OPTIONS, DOMAIN
from .models import normalize_event

_LOGGER = logging.getLogger(__name__)


class VerkadaCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, api):
        self.entry = entry
        self.api = api
        self.options = {**DEFAULT_OPTIONS, **entry.options}
        self.events = []
        self.status = {}
        self.cursors = {}
        self.last_event = None
        self.last_webhook = None
        self.last_poll = None
        self.cameras_by_id = {}
        self.inventory = {}
        self.playbacks = {}
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.history")
        super().__init__(
            hass,
            _LOGGER,
            name="Verkada",
            config_entry=entry,
            update_interval=timedelta(seconds=self.options["poll_interval"]),
        )

    async def async_load(self):
        saved = await self.store.async_load()
        if isinstance(saved, dict):
            self.events = [
                e
                for e in saved.get("events", [])
                if isinstance(e, dict)
                and "id" in e
                and isinstance(e.get("timestamp"), (int, float))
            ]
            self.cursors = saved.get("cursors", {})
        self.prune()

    def prune(self):
        cutoff = time.time() - self.options["history_days"] * 86400
        self.events = sorted(
            (e for e in self.events if e["timestamp"] >= cutoff),
            key=lambda e: e["timestamp"],
            reverse=True,
        )[:1000]

    def add_events(self, events, *, notify=True):
        known = {e["id"] for e in self.events}
        selected = set(self.cameras_by_id)
        for event in sorted((e for e in events if e), key=lambda e: e["timestamp"]):
            if event["id"] in known or (event["camera_id"] and event["camera_id"] not in selected):
                continue
            known.add(event["id"])
            self.events.append(event)
            if notify:
                self.last_event = event
                self.hass.bus.async_fire(
                    "verkada_event", {"entry_id": self.entry.entry_id, **event}
                )
        self.prune()
        self.store.async_delay_save(lambda: {"events": self.events, "cursors": self.cursors}, 5)

    async def _source(self, key, fetch, normalize):
        end = int(time.time())
        initial = key not in self.cursors
        requested_start = int(self.cursors.get(key, end - 300)) - 10
        start = max(requested_start, end - 86400)
        try:
            rows = await fetch(start, end)
            events = [normalize(row) for row in rows]
            if any(event is None for event in events):
                raise VerkadaError("Response contains invalid events; cursor was not advanced")
            self.add_events(events, notify=not initial)
            self.cursors[key] = end
            self.status[key] = {"state": "ok", "last_success": end}
            if requested_start < start:
                self.status[key].update(
                    state="partial",
                    message="Automatic backfill covers only the last 24 hours; older events may be missing",
                )
        except VerkadaError as err:
            previous = self.status.get(key, {}).get("last_success")
            self.status[key] = {"state": "error", "message": str(err), "last_success": previous}

    async def _async_update_data(self):
        try:
            rows = await self.api.cameras()
            if any(not isinstance(c, dict) or not c.get("camera_id") for c in rows):
                raise VerkadaError("Invalid camera inventory response")
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("Verkada API credentials rejected") from err
        except VerkadaError as err:
            raise UpdateFailed(str(err)) from err
        selected = self.options.get("camera_ids", [])
        self.inventory = {c["camera_id"]: c for c in rows}
        self.cameras_by_id = {
            c["camera_id"]: c for c in rows if not selected or c["camera_id"] in selected
        }
        self.last_poll = int(time.time())
        if self.options["alerts"]:
            await self._source("alerts", self.api.alerts, lambda row: normalize_event(row, "alert"))
        for cid in self.options["lpr_camera_ids"]:
            if cid in self.cameras_by_id:
                await self._source(
                    f"lpr:{cid}",
                    lambda start, end, cid=cid: self.api.lpr(cid, start, end),
                    lambda row, cid=cid: normalize_event(row, "lpr", camera_id=cid),
                )
        if event_type := self.options["helix_event_type"]:
            await self._source(
                "helix",
                lambda start, end: self.api.helix(list(self.cameras_by_id), event_type, start, end),
                lambda row: normalize_event(
                    row, "helix", plate_attribute=self.options["helix_plate_attribute"]
                ),
            )
        self.prune()
        return self.cameras_by_id

    def webhook(self, payload):
        if not isinstance(payload, dict) or payload.get("org_id") != self.api.org_id:
            return False
        data = payload.get("data")
        if not isinstance(data, dict):
            return False
        source = "lpr" if payload.get("webhook_type") == "lpr" else "webhook"
        event = normalize_event(data, source, plate_attribute=self.options["helix_plate_attribute"])
        if event is None:
            return False
        self.last_webhook = int(time.time())
        self.add_events([event])
        self.async_set_updated_data(self.cameras_by_id)
        return True
