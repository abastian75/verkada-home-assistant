"""Unofficial Verkada camera integration."""

from pathlib import Path

from aiohttp import web
from homeassistant.components import frontend, panel_custom, webhook
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import VerkadaClient
from .const import DOMAIN, VERSION
from .coordinator import VerkadaCoordinator
from .models import verify_signature

PLATFORMS = [Platform.CAMERA, Platform.BINARY_SENSOR, Platform.SENSOR, Platform.EVENT]


async def async_setup(hass, config):
    from .live import LiveView, ws_stream  # noqa: PLC0415
    from .websocket import async_register  # noqa: PLC0415

    hass.data.setdefault(DOMAIN, {})
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig("/verkada_static", str(Path(__file__).parent / "frontend"), True),
        ]
    )
    async_register(hass)
    hass.data["verkada_live"] = LiveView(hass)
    hass.http.register_view(hass.data["verkada_live"])
    from homeassistant.components import websocket_api  # noqa: PLC0415

    websocket_api.async_register_command(hass, ws_stream)
    frontend.add_extra_js_url(hass, f"/verkada_static/verkada-cards.js?v={VERSION}")
    return True


async def async_setup_entry(hass, entry):
    api = VerkadaClient(
        async_get_clientsession(hass),
        entry.data["region"],
        entry.data["api_key"],
        entry.data["org_id"],
        entry.data.get("streaming_api_key", ""),
    )
    hub = VerkadaCoordinator(hass, entry, api)
    await hub.async_load()
    await hub.async_config_entry_first_refresh()
    entry.runtime_data = hub
    hass.data[DOMAIN][entry.entry_id] = hub
    hub.device_id = (
        dr.async_get(hass)
        .async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, entry.unique_id)},
            name=entry.title,
            manufacturer="Verkada",
            model="Command organization",
        )
        .id
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    path = "verkada-" + entry.entry_id
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=path,
        webcomponent_name="verkada-panel",
        sidebar_title=entry.title,
        sidebar_icon="mdi:cctv",
        module_url=f"/verkada_static/verkada-panel.js?v={VERSION}",
        config={"entry_id": entry.entry_id},
        require_admin=True,
    )
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    if hub.options["webhook_secret"]:

        async def handle_webhook(hass, webhook_id, request):
            if request.content_length and request.content_length > 256 * 1024:
                return web.json_response({"error": "payload_too_large"}, status=413)
            body = await request.content.read(256 * 1024 + 1)
            if len(body) > 256 * 1024:
                return web.json_response({"error": "payload_too_large"}, status=413)
            if not verify_signature(
                body, request.headers.get("Verkada-Signature", ""), hub.options["webhook_secret"]
            ):
                return web.json_response({"error": "invalid_signature"}, status=403)
            import json  # noqa: PLC0415

            try:
                payload = json.loads(body)
            except (ValueError, UnicodeDecodeError):
                return web.json_response({"error": "invalid_json"}, status=400)
            if not hub.webhook(payload):
                return web.json_response({"error": "invalid_event_or_organization"}, status=400)
            return web.json_response({"accepted": True})

        webhook.async_register(
            hass,
            DOMAIN,
            entry.title,
            entry.data["webhook_id"],
            handle_webhook,
            allowed_methods=["POST"],
            local_only=False,
        )
        entry.async_on_unload(lambda: webhook.async_unregister(hass, entry.data["webhook_id"]))
    return True


async def _async_reload(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hub = hass.data[DOMAIN].pop(entry.entry_id)
        hass.data["verkada_live"].discard(hub)
        frontend.async_remove_panel(hass, "verkada-" + entry.entry_id)
        await hub.store.async_save(hub.saved_history())
        return True
    return False


async def async_remove_entry(hass, entry):
    from homeassistant.helpers.storage import Store  # noqa: PLC0415

    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.history").async_remove()
