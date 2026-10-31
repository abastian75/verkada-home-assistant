"""Authenticated admin-only dashboard commands. No credentials are returned."""

import time

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.camera import DynamicStreamSettings
from homeassistant.components.stream import create_stream
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.network import get_url

from .api import VerkadaError
from .const import DOMAIN
from .models import normalize_event


@callback
def async_register(hass):
    websocket_api.async_register_command(hass, ws_dashboard)
    from .cards import ws_cards  # noqa: PLC0415

    websocket_api.async_register_command(hass, ws_cards)


async def async_stop_playback(hub, owner):
    stream = hub.playbacks.pop(owner, None)
    if stream:
        await stream.stop()


async def async_start_playback(hass, hub, owner, cid, start, end):
    if not cid or not (0 < start < end <= time.time() and end - start <= 3600):
        raise HomeAssistantError("Choose a camera and a past interval of at most one hour.")
    for key, stream in list(hub.playbacks.items()):
        if not stream.outputs():
            hub.playbacks.pop(key, None)
    if owner not in hub.playbacks and len(hub.playbacks) >= 8:
        raise HomeAssistantError("Close another recorded playback before starting a new one.")
    url = await hub.api.stream_url(cid, high=hub.options["high_resolution"], start=start, end=end)
    await async_stop_playback(hub, owner)
    stream = create_stream(hass, url, {}, DynamicStreamSettings(), stream_label="verkada_history")
    stream.add_provider("hls")
    hub.playbacks[owner] = stream
    await stream.start()
    return stream.endpoint_url("hls")


@websocket_api.websocket_command(
    {
        vol.Required("type"): "verkada/dashboard",
        vol.Required("entry_id"): str,
        vol.Required("action"): vol.In(["status", "refresh", "search", "playback", "stop"]),
        vol.Optional("camera_id", default=""): str,
        vol.Optional("source", default="alert"): vol.In(["alert", "lpr", "helix"]),
        vol.Optional("start", default=0): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("end", default=0): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)
@websocket_api.async_response
async def ws_dashboard(hass, connection, msg):
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Administrator access is required.")
        return
    hub = hass.data.get(DOMAIN, {}).get(msg["entry_id"])
    if not hub:
        connection.send_error(
            msg["id"], "not_loaded", "Verkada is not loaded. Check the integration settings."
        )
        return
    cid, action = msg["camera_id"], msg["action"]
    searched = None
    if cid and cid not in hub.data:
        connection.send_error(msg["id"], "invalid_camera", "Select a configured camera.")
        return
    try:
        if action == "stop":
            await async_stop_playback(hub, connection.user.id)
            connection.send_result(msg["id"], {})
            return
        if action == "playback":
            start, end = msg["start"], msg["end"]
            url = await async_start_playback(hass, hub, connection.user.id, cid, start, end)
            connection.send_result(msg["id"], {"url": url})
            return
        if action == "search":
            start, end = msg["start"], msg["end"]
            if not (0 < start < end <= time.time() and end - start <= 86400):
                raise HomeAssistantError("Search a past interval of at most 24 hours.")
            source = msg["source"]
            if source == "lpr":
                if cid not in hub.options["lpr_camera_ids"]:
                    raise HomeAssistantError(
                        "Select a camera enabled for LPR in integration options."
                    )
                rows = await hub.api.lpr(cid, start, end)
            elif source == "helix":
                if not hub.options["helix_event_type"]:
                    raise HomeAssistantError("Set a Helix event type UID in integration options.")
                rows = await hub.api.helix(
                    [cid] if cid else list(hub.data), hub.options["helix_event_type"], start, end
                )
            else:
                rows = await hub.api.alerts(start, end)
            events = [
                normalize_event(
                    row, source, camera_id=cid, plate_attribute=hub.options["helix_plate_attribute"]
                )
                for row in rows
            ]
            if any(event is None for event in events):
                raise HomeAssistantError("Unexpected event data returned by Verkada.")
            hub.add_events(events, notify=False)
            hub.async_set_updated_data(hub.data)
            searched = sorted(
                (
                    e
                    for e in events
                    if (not e["camera_id"] or e["camera_id"] in hub.data)
                    and (not cid or e["camera_id"] == cid)
                ),
                key=lambda e: e["timestamp"],
                reverse=True,
            )
        elif action == "refresh":
            await hub.async_request_refresh()
        registry = er.async_get(hass)
        cameras = []
        for camera_id, camera in hub.data.items():
            unique_id = f"{hub.entry.unique_id}_{camera_id}"
            cameras.append(
                {
                    "camera_id": camera_id,
                    "name": camera.get("name", camera_id),
                    "status": camera.get("status"),
                    "site": camera.get("site"),
                    "entity_id": registry.async_get_entity_id("camera", DOMAIN, unique_id),
                }
            )
        try:
            external = get_url(hass, allow_internal=False)
        except HomeAssistantError:
            external = ""
        connection.send_result(
            msg["id"],
            {
                "title": hub.entry.title,
                "cameras": cameras,
                "events": hub.events,
                "sources": hub.status,
                "last_poll": hub.last_poll,
                "connected": hub.last_update_success,
                "last_webhook": hub.last_webhook,
                "webhook_enabled": bool(hub.options["webhook_secret"]),
                "webhook_url": external + "/api/webhook/" + hub.entry.data["webhook_id"],
                "external_url_configured": bool(external),
                "lpr_camera_ids": hub.options["lpr_camera_ids"],
                "helix_enabled": bool(hub.options["helix_event_type"]),
                "history_days": hub.options["history_days"],
                "search_results": searched[:1000] if searched is not None else None,
                "search_omitted": max(0, len(searched) - 1000) if searched is not None else 0,
            },
        )
    except (VerkadaError, HomeAssistantError) as err:
        connection.send_error(msg["id"], "verkada_error", str(err))
