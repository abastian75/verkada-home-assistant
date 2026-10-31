"""Read-only card data, filtered by the user's existing HA camera permissions."""

import voluptuous as vol
from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import websocket_api
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .api import VerkadaError
from .const import DOMAIN


def visible_cameras(hass, connection, hub):
    registry = er.async_get(hass)
    result = []
    for cid, camera in hub.data.items():
        entity_id = registry.async_get_entity_id("camera", DOMAIN, f"{hub.entry.unique_id}_{cid}")
        if entity_id and connection.user.permissions.check_entity(entity_id, POLICY_READ):
            result.append(
                {
                    "camera_id": cid,
                    "entity_id": entity_id,
                    "name": camera.get("name", cid),
                    "status": camera.get("status"),
                    "plate_tracking": cid in hub.plate_camera_ids,
                }
            )
    return result


@websocket_api.websocket_command(
    {
        vol.Required("type"): "verkada/cards",
        vol.Required("action"): vol.In(["list", "status", "playback", "stop"]),
        vol.Optional("entry_id", default=""): str,
        vol.Optional("camera_id", default=""): str,
        vol.Optional("source", default="all"): vol.In(["all", "alert", "lpr"]),
        vol.Optional("limit", default=5): vol.All(int, vol.Range(min=1, max=50)),
        vol.Optional("client_id", default="card"): vol.Match(r"^[a-zA-Z0-9_-]{1,64}$"),
        vol.Optional("start", default=0): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("end", default=0): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)
@websocket_api.async_response
async def ws_cards(hass, connection, msg):
    hubs = hass.data.get(DOMAIN, {})
    if msg["action"] == "list":
        entries = []
        for entry_id, hub in hubs.items():
            cameras = visible_cameras(hass, connection, hub)
            if cameras:
                entries.append({"entry_id": entry_id, "name": hub.entry.title, "cameras": cameras})
        connection.send_result(msg["id"], {"entries": entries})
        return
    hub = hubs.get(msg["entry_id"])
    if not hub:
        connection.send_error(msg["id"], "not_loaded", "Choose a loaded Verkada integration.")
        return
    cameras = visible_cameras(hass, connection, hub)
    allowed = {c["camera_id"] for c in cameras}
    cid = msg["camera_id"]
    if not allowed or (cid and cid not in allowed):
        connection.send_error(msg["id"], "unauthorized", "You do not have access to this camera.")
        return
    from .websocket import async_start_playback, async_stop_playback  # noqa: PLC0415

    owner = f"{connection.user.id}:{msg['client_id']}"
    try:
        if msg["action"] == "stop":
            await async_stop_playback(hub, owner)
            connection.send_result(msg["id"], {})
            return
        if msg["action"] == "playback":
            url = await async_start_playback(hass, hub, owner, cid, msg["start"], msg["end"])
            connection.send_result(msg["id"], {"url": url})
            return
        events = [
            e
            for e in hub.events
            if e["camera_id"] in allowed
            and (not cid or e["camera_id"] == cid)
            and (
                msg["source"] == "all"
                or (
                    bool(e.get("plate"))
                    if msg["source"] == "lpr"
                    else e["source"] in ("alert", "webhook")
                )
            )
        ]
        statuses = {
            key: value
            for key, value in hub.status.items()
            if key in ("alerts", "helix") or (key.startswith("lpr:") and key[4:] in allowed)
        }
        connection.send_result(
            msg["id"],
            {
                "cameras": cameras,
                "events": events[: msg["limit"]],
                "connected": hub.last_update_success,
                "sources": statuses,
                "last_poll": hub.last_poll,
                "plate_tracking": bool(hub.plate_camera_ids & allowed),
            },
        )
    except (VerkadaError, HomeAssistantError) as err:
        connection.send_error(msg["id"], "verkada_error", str(err))
