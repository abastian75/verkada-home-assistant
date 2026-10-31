"""Run inside official HA 2026.10.4 with --network none; no home equipment used."""

import asyncio
import hashlib
import hmac
import json
import logging
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

from aiohttp import ClientSession, ThreadedResolver, web
from homeassistant import bootstrap, loader
from homeassistant.components.camera import DATA_COMPONENT
from homeassistant.core import HomeAssistant

logging.basicConfig(level=logging.WARNING)

ORG = "11111111-1111-4111-8111-111111111111"
CAM = "22222222-2222-4222-8222-222222222222"
ROOT = Path(__file__).resolve().parents[1]


class IsolatedResolver(ThreadedResolver):
    async def real_close(self):
        await self.close()


async def main():
    with tempfile.TemporaryDirectory(prefix="verkada-ha-") as folder:
        root = Path(folder)
        (root / "custom_components").symlink_to(
            ROOT / "custom_components", target_is_directory=True
        )
        sys.path.insert(0, folder)
        hass = HomeAssistant(folder)
        runner = None
        try:
            loader.async_setup(hass)
            hass.config.skip_pip = True
            assert await bootstrap.async_from_config_dict(
                {
                    "homeassistant": {
                        "latitude": 0,
                        "longitude": 0,
                        "elevation": 0,
                        "unit_system": "metric",
                        "time_zone": "UTC",
                    },
                    "http": {"server_host": "127.0.0.1", "server_port": 8123},
                    "api": {},
                    "frontend": {},
                    "config": {},
                },
                hass,
            )
            from custom_components.verkada.api import PermissionError, VerkadaClient
            from custom_components.verkada.diagnostics import async_get_config_entry_diagnostics

            now = int(time.time())
            permissions = {"alerts": True}

            async def fake_request(self, method, path, **kwargs):
                if path == "/token":
                    return {"token": "SYNTHETIC_API_TOKEN"}
                if path.endswith("/devices"):
                    return {
                        "cameras": [
                            {
                                "camera_id": CAM,
                                "name": "Synthetic Driveway",
                                "model": "TEST",
                                "status": "Live",
                                "site": "Synthetic home",
                                "serial": "TEST-001",
                                "firmware": "Up to date",
                            }
                        ]
                    }
                if path.endswith("/alerts"):
                    if not permissions["alerts"]:
                        raise PermissionError("API permission denied for this feature")
                    return {
                        "notifications": [
                            {
                                "camera_id": CAM,
                                "created": now - 20,
                                "notification_type": "motion",
                                "objects": ["person"],
                            }
                        ]
                    }
                if path.endswith("lpr/images"):
                    return {
                        "camera_id": CAM,
                        "detections": [{"license_plate": "TEST123", "timestamp": now - 10}],
                    }
                if path.endswith("event/search"):
                    return {
                        "events": [
                            {
                                "camera_id": CAM,
                                "time_ms": (now - 15) * 1000,
                                "attributes": {"plate_id": "HELIX123"},
                            }
                        ]
                    }
                if path.endswith("footage/token"):
                    return {"jwt": "SYNTHETIC_JWT"}
                if "thumbnails" in path:
                    return b"\xff\xd8synthetic-thumbnail"
                raise AssertionError(path)

            with (
                patch.object(VerkadaClient, "_request", fake_request),
                patch(
                    "homeassistant.helpers.aiohttp_client._async_make_resolver",
                    lambda hass: IsolatedResolver(),
                ),
            ):
                flow = await hass.config_entries.flow.async_init(
                    "verkada", context={"source": "user"}
                )
                assert flow["type"] == "form", flow
                result = await hass.config_entries.flow.async_configure(
                    flow["flow_id"],
                    user_input={
                        "name": "Verkada Test",
                        "region": "us",
                        "org_id": ORG,
                        "api_key": "SYNTHETIC_KEY",
                    },
                )
                assert result["type"] == "create_entry", result
                entry = result["result"]
                await hass.async_block_till_done()
                assert entry.state.value == "loaded", entry.state
                await hass.async_start()
                await hass.async_block_till_done()
                hub = entry.runtime_data
                assert len(hub.data) == 1 and len(hub.events) == 1
                assert hub.last_event is None, "Historical initial import fired a new event"
                camera = next(
                    c
                    for c in hass.data[DATA_COMPONENT].entities
                    if c.unique_id.startswith(entry.unique_id)
                )
                assert camera.available
                assert "SYNTHETIC_JWT" in await camera.stream_source()
                assert await camera.async_camera_image() == b"\xff\xd8synthetic-thumbnail"
                options = await hass.config_entries.options.async_init(entry.entry_id)
                assert options["type"] == "form", options
                result = await hass.config_entries.options.async_configure(
                    options["flow_id"],
                    user_input={
                        "camera_ids": [],
                        "poll_interval": 60,
                        "alerts": True,
                        "lpr_camera_ids": [CAM],
                        "helix_event_type": "synthetic-type",
                        "helix_plate_attribute": "plate_id",
                        "webhook_secret": "SYNTHETIC_SHARED_SECRET",
                        "history_days": 7,
                        "high_resolution": False,
                    },
                )
                assert result["type"] == "create_entry", result
                await hass.async_block_till_done()
                hub = entry.runtime_data
                assert len(hub.events) == 3, [e["source"] for e in hub.events]
                assert {e["plate"] for e in hub.events if e["plate"]} == {"TEST123", "HELIX123"}
                permissions["alerts"] = False
                await hub.async_refresh()
                assert hub.last_update_success and hub.status["alerts"]["state"] == "error"
                permissions["alerts"] = True
                await hub.async_refresh()
                assert hub.status["alerts"]["state"] == "ok"
                assert "SYNTHETIC" not in json.dumps(
                    await async_get_config_entry_diagnostics(hass, entry)
                )

                user = await hass.auth.async_create_user(
                    "Synthetic administrator", group_ids=["system-admin"]
                )
                refresh = await hass.auth.async_create_refresh_token(
                    user, client_id="http://localhost/"
                )
                access = hass.auth.async_create_access_token(refresh)
                normal = await hass.auth.async_create_user(
                    "Synthetic viewer", group_ids=["system-users"]
                )
                normal_refresh = await hass.auth.async_create_refresh_token(
                    normal, client_id="http://localhost/"
                )
                normal_access = hass.auth.async_create_access_token(normal_refresh)
                async with ClientSession() as session:
                    footage = root / "footage"
                    footage.mkdir()
                    process = await asyncio.create_subprocess_exec(
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-f",
                        "lavfi",
                        "-i",
                        "testsrc=size=320x180:rate=10",
                        "-t",
                        "12",
                        "-pix_fmt",
                        "yuv420p",
                        "-c:v",
                        "libx264",
                        "-g",
                        "10",
                        "-sc_threshold",
                        "0",
                        "-f",
                        "hls",
                        "-hls_time",
                        "1",
                        "-hls_list_size",
                        "0",
                        str(footage / "source.m3u8"),
                    )
                    assert await process.wait() == 0
                    app = web.Application()
                    app.router.add_static("/", str(footage))
                    runner = web.AppRunner(app)
                    await runner.setup()
                    source_site = web.TCPSite(runner, "127.0.0.1", 0)
                    await source_site.start()
                    source_port = source_site._server.sockets[0].getsockname()[1]
                    hub.api.stream_url = AsyncMock(
                        return_value=f"http://127.0.0.1:{source_port}/source.m3u8"
                    )
                    url = "http://127.0.0.1:8123/api/webhook/" + entry.data["webhook_id"]
                    payload = {
                        "org_id": ORG,
                        "webhook_type": "lpr",
                        "webhook_id": "synthetic-event",
                        "data": {
                            "camera_id": CAM,
                            "created": now,
                            "license_plate_number": "WEB123",
                            "confidence": 0.99,
                        },
                    }
                    body = json.dumps(payload).encode()
                    stamp = str(int(time.time()))
                    signature = hmac.new(
                        b"SYNTHETIC_SHARED_SECRET", body + b"|" + stamp.encode(), hashlib.sha256
                    ).hexdigest()
                    received = []
                    unsub = hass.bus.async_listen(
                        "verkada_event", lambda event: received.append(event.data)
                    )
                    async with session.post(
                        url, data=body, headers={"Verkada-Signature": stamp + "|bad"}
                    ) as response:
                        assert response.status == 403
                    for _ in range(2):
                        async with session.post(
                            url, data=body, headers={"Verkada-Signature": stamp + "|" + signature}
                        ) as response:
                            assert response.status == 200, await response.text()
                    await hass.async_block_till_done()
                    assert len(received) == 1, "Webhook was duplicated"
                    unsub()
                    async with session.ws_connect("http://127.0.0.1:8123/api/websocket") as ws:
                        await ws.receive_json()
                        await ws.send_json({"type": "auth", "access_token": access})
                        assert (await ws.receive_json())["type"] == "auth_ok"

                        async def command(num, action, **kwargs):
                            await ws.send_json(
                                {
                                    "id": num,
                                    "type": "verkada/dashboard",
                                    "entry_id": entry.entry_id,
                                    "action": action,
                                    **kwargs,
                                }
                            )
                            return await ws.receive_json()

                        value = await command(1, "status")
                        assert value["success"], value
                        assert value["result"]["cameras"][0]["entity_id"].startswith("camera.")
                        assert "SYNTHETIC_KEY" not in json.dumps(value)
                        value = await command(
                            2, "search", source="lpr", camera_id=CAM, start=now - 3600, end=now - 1
                        )
                        assert value["success"], value
                        value = await command(
                            3, "playback", camera_id=CAM, start=now - 7200, end=now - 1
                        )
                        assert not value["success"], "Overlong playback accepted"
                        value = await command(
                            4, "playback", camera_id=CAM, start=now - 120, end=now - 60
                        )
                        assert value["success"], value
                        async with session.get(
                            "http://127.0.0.1:8123" + value["result"]["url"]
                        ) as response:
                            assert response.status == 200, await response.text()
                            playlist = await response.text()
                            assert "#EXTM3U" in playlist
                        value = await command(5, "stop")
                        assert value["success"]
                    async with session.ws_connect("http://127.0.0.1:8123/api/websocket") as ws:
                        await ws.receive_json()
                        await ws.send_json({"type": "auth", "access_token": normal_access})
                        await ws.receive_json()
                        await ws.send_json(
                            {
                                "id": 1,
                                "type": "verkada/dashboard",
                                "entry_id": entry.entry_id,
                                "action": "status",
                            }
                        )
                        assert not (await ws.receive_json())["success"], (
                            "Non-admin history access accepted"
                        )
                assert await hass.config_entries.async_unload(entry.entry_id)
                assert entry.entry_id not in hass.data["verkada"]
                print(
                    "PASS: actual HA setup/options/reload, entities, source failures, event history, HMAC/replay, websocket admin permissions, real HLS playback from synthetic footage, unload"
                )
        finally:
            if runner:
                await runner.cleanup()
            await hass.async_stop()


asyncio.run(main())
