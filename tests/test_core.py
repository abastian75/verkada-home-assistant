"""Contract/security tests; fixtures are synthetic, shaped like official schemas."""

import asyncio
import hashlib
import hmac
import sys
import time
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
# Import the pure client/model modules without requiring an HA process.
package = types.ModuleType("verkada_test")
package.__path__ = [str(ROOT / "custom_components/verkada")]
sys.modules["verkada_test"] = package
from verkada_test.api import AuthenticationError, VerkadaClient, VerkadaError  # noqa: E402
from verkada_test.models import event_time, normalize_event, verify_signature  # noqa: E402


class ModelTests(unittest.TestCase):
    def test_signature_and_replay(self):
        body = b'{"test": true}'
        signature = hmac.new(b"synthetic-secret", body + b"|100", hashlib.sha256).hexdigest()
        header = "100|" + signature
        self.assertTrue(verify_signature(body, header, "synthetic-secret", now=100))
        for changed, secret, now in [
            (b"tampered", "synthetic-secret", 100),
            (body, "wrong", 100),
            (body, "synthetic-secret", 161),
            (body, "synthetic-secret", 39),
        ]:
            self.assertFalse(verify_signature(changed, header, secret, now=now))
        self.assertFalse(verify_signature(body, "malformed", "x", now=100))

    def test_native_lpr_and_helix(self):
        now = int(time.time())
        event = normalize_event(
            {"license_plate": "TEST123", "timestamp": now}, "lpr", camera_id="c1"
        )
        self.assertEqual(event["plate"], "TEST123")
        self.assertEqual(event["camera_id"], "c1")
        helix = normalize_event(
            {
                "time_ms": now * 1000,
                "camera_id": "c2",
                "attributes": {
                    "plate_id": "TEST456",
                    "api_key": "redact",
                    "password": "redact",
                    "make": "Example",
                },
            },
            "helix",
            plate_attribute="plate_id",
        )
        self.assertEqual(helix["plate"], "TEST456")
        self.assertEqual(helix["attributes"], {"plate_id": "TEST456", "make": "Example"})
        self.assertIsNone(normalize_event({"timestamp": float("nan")}, "lpr"))
        self.assertIsNone(event_time(time.time() + 1000))

    def test_untrusted_urls_and_content(self):
        data = {
            "created": int(time.time()),
            "alert_name": "<script>unsafe</script>",
            "image_url": "https://evil.example/image",
        }
        event = normalize_event(data, "alert")
        self.assertNotIn("image_url", event)
        self.assertEqual(event["label"], data["alert_name"])
        data["image_url"] = "https://images.verkada.com/test.jpg"
        self.assertIn("image_url", normalize_event(data, "alert"))
        data["image_url"] = "https://images.verkada.com.evil.example/test.jpg"
        self.assertNotIn("image_url", normalize_event(data, "alert"))


class ApiTests(unittest.IsolatedAsyncioTestCase):
    def api(self):
        return VerkadaClient(None, "eu", "test-api-key", "test-org", "test-stream-key")

    async def test_token_cache_and_concurrent_requests(self):
        api = self.api()
        api._request = AsyncMock(return_value={"token": "test-token"})
        tokens = await asyncio.gather(*(api.token() for _ in range(10)))
        self.assertEqual(len(set(tokens)), 1)
        self.assertEqual(api._request.await_count, 1)
        api._token_until = 0
        await api.token()
        self.assertEqual(api._request.await_count, 2)

    async def test_expired_auth_retries_once(self):
        api = self.api()
        api._token = "old"
        api._token_until = time.monotonic() + 1000
        api._request = AsyncMock(
            side_effect=[AuthenticationError(), {"token": "new"}, {"cameras": []}]
        )
        self.assertEqual(await api.cameras(), [])
        self.assertEqual(api._request.await_count, 3)

    async def test_pagination_complete_or_error(self):
        api = self.api()
        api.request = AsyncMock(
            side_effect=[
                {"detections": [{"license_plate": "A"}], "next_page_token": 5},
                {"detections": [{"license_plate": "B"}]},
            ]
        )
        self.assertEqual(len(await api.lpr("c1", 1, 2)), 2)
        self.assertEqual(api.request.await_args_list[1].kwargs["params"]["page_token"], 5)
        api.request = AsyncMock(side_effect=[{"cameras": [], "next_page_token": "same"}] * 2)
        with self.assertRaises(VerkadaError):
            await api.cameras()
        api.request = AsyncMock(return_value={"wrong": []})
        with self.assertRaises(VerkadaError):
            await api.cameras()

    async def test_helix_refuses_silent_truncation(self):
        api = self.api()
        api.request = AsyncMock(return_value={"events": [], "next_token": 5})
        with self.assertRaises(VerkadaError):
            await api.helix(["c1"], "type", 1, 2)

    async def test_streaming_uses_top_level_key_and_safe_endpoint(self):
        api = self.api()
        api._request = AsyncMock(return_value={"jwt": "synthetic-jwt"})
        url = await api.stream_url("c1", high=True, start=100, end=160)
        params = parse_qs(urlsplit(url).query)
        self.assertEqual(urlsplit(url).netloc, "api.eu.verkada.com")
        self.assertEqual(params["start_time"], ["100"])
        self.assertEqual(params["resolution"], ["high_res"])
        self.assertNotIn("test-api-key", url)
        self.assertEqual(
            api._request.await_args.kwargs["headers"], {"x-api-key": "test-stream-key"}
        )


if __name__ == "__main__":
    unittest.main()
