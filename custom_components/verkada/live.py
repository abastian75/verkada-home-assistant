"""Camera-scoped live HLS passthrough; vendor credentials never reach the browser."""

import hashlib
import re
import secrets
import time
from collections import OrderedDict
from urllib.parse import urljoin, urlsplit

import aiohttp
import voluptuous as vol
from aiohttp import web
from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers import entity_registry as er

from .api import VerkadaError
from .const import DOMAIN

PREFIX = "/stream/cameras/v1/footage/stream/"
URI = re.compile(r'URI="([^"]+)"')


async def fetch_media(hub, url, range_header):
    headers = {"Range": range_header} if range_header else {}
    async with hub.api.session.get(
        url, headers=headers, timeout=aiohttp.ClientTimeout(total=40), allow_redirects=False
    ) as response:
        if response.status not in (200, 206):
            raise web.HTTPBadGateway(text="Verkada video is temporarily unavailable")
        chunks, size = [], 0
        async for chunk in response.content.iter_chunked(65536):
            size += len(chunk)
            if size > 32 * 1024 * 1024:
                raise web.HTTPBadGateway(text="Video response exceeded the size limit")
            chunks.append(chunk)
        return (
            b"".join(chunks),
            response.status,
            {
                k: response.headers[k]
                for k in ("Content-Type", "Content-Range", "Accept-Ranges")
                if k in response.headers
            },
        )


class LiveView(HomeAssistantView):
    url = "/api/verkada/live/{session}/{resource}"
    name = "api:verkada:live"
    requires_auth = False  # Unguessable camera-scoped sessions, like HA's HLS endpoints.

    def __init__(self, hass):
        self.hass = hass
        self.sessions = OrderedDict()

    def start(self, hub, cid):
        now = time.monotonic()
        for key, value in list(self.sessions.items()):
            if now - value["used"] > 300:
                self.sessions.pop(key)
        if len(self.sessions) >= 64:
            raise VerkadaError("Too many video viewers; close another view and retry")
        key = secrets.token_urlsafe(24)
        self.sessions[key] = {"hub": hub, "camera": cid, "used": now, "urls": OrderedDict()}
        return f"/api/verkada/live/{key}/index.m3u8"

    def discard(self, hub):
        for key, value in list(self.sessions.items()):
            if value["hub"] is hub:
                self.sessions.pop(key)

    def rewrite(self, key, session, source, body):
        def replace(uri):
            url = urljoin(source, uri)
            parsed = urlsplit(url)
            expected = urlsplit(session["hub"].api.base)
            if (
                parsed.scheme != "https"
                or parsed.netloc != expected.netloc
                or not parsed.path.startswith(PREFIX)
                or "/../" in parsed.path
            ):
                raise web.HTTPBadGateway(text="Unsupported video resource location")
            resource = hashlib.sha256(url.encode()).hexdigest()
            urls = session["urls"]
            urls[resource] = url
            urls.move_to_end(resource)
            while len(urls) > 256:
                urls.popitem(last=False)
            return f"/api/verkada/live/{key}/{resource}"

        lines = []
        for line in body.decode("utf-8").splitlines():
            if line.startswith("#"):
                lines.append(URI.sub(lambda match: f'URI="{replace(match[1])}"', line))
            elif line.strip():
                lines.append(replace(line.strip()))
        result = "\n".join(lines) + "\n"
        if "jwt=" in result or "https://" in result:
            raise web.HTTPBadGateway(text="Unsupported video playlist")
        return result.encode()

    async def get(self, request, session, resource):
        value = self.sessions.get(session)
        now = time.monotonic()
        if value is None or now - value["used"] > 300:
            self.sessions.pop(session, None)
            raise web.HTTPNotFound()
        hub = value["hub"]
        if (
            self.hass.data.get(DOMAIN, {}).get(hub.entry.entry_id) is not hub
            or value["camera"] not in hub.data
        ):
            self.sessions.pop(session, None)
            raise web.HTTPNotFound()
        value["used"] = now
        try:
            if resource == "index.m3u8":
                url = await hub.api.stream_url(
                    value["camera"],
                    high=hub.options["high_resolution"],
                    codec=hub.options["live_codec"],
                )
            else:
                url = value["urls"].get(resource)
                if url is None:
                    raise web.HTTPNotFound()
            body, status, headers = await fetch_media(hub, url, request.headers.get("Range"))
            if body.startswith(b"#EXTM3U"):
                body = self.rewrite(session, value, url, body)
                headers = {"Content-Type": "application/vnd.apple.mpegurl"}
            elif "json" in headers.get("Content-Type", "") or "html" in headers.get(
                "Content-Type", ""
            ):
                raise web.HTTPBadGateway(text="Invalid video resource")
            headers["Cache-Control"] = "no-store"
            return web.Response(body=body, status=status, headers=headers)
        except (aiohttp.ClientError, TimeoutError, ValueError, VerkadaError) as error:
            raise web.HTTPBadGateway(text="Video connection failed; retry shortly") from error


@websocket_api.websocket_command(
    {vol.Required("type"): "verkada/stream", vol.Required("entity_id"): str}
)
@websocket_api.async_response
async def ws_stream(hass, connection, msg):
    item = er.async_get(hass).async_get(msg["entity_id"])
    hub = hass.data.get(DOMAIN, {}).get(item.config_entry_id) if item else None
    if (
        not item
        or item.platform != DOMAIN
        or item.domain != "camera"
        or hub is None
        or not connection.user.permissions.check_entity(item.entity_id, POLICY_READ)
    ):
        connection.send_error(msg["id"], "unauthorized", "Camera access is required")
        return
    cid = next((cid for cid in hub.data if item.unique_id == f"{hub.entry.unique_id}_{cid}"), None)
    if cid is None:
        connection.send_error(msg["id"], "unavailable", "Camera is not configured")
        return
    try:
        url = hass.data["verkada_live"].start(hub, cid)
    except VerkadaError as error:
        connection.send_error(msg["id"], "unavailable", str(error))
    else:
        connection.send_result(msg["id"], {"url": url})
