"""Small async client for documented Verkada camera APIs."""

import asyncio
import time
from urllib.parse import urlencode

import aiohttp

from .const import REGIONS


class VerkadaError(Exception):
    """Sanitized error safe to show without logging credentials or URLs."""


class AuthenticationError(VerkadaError):
    """API key rejected."""


class PermissionError(VerkadaError):
    """A specific permission is missing."""


class VerkadaClient:
    def __init__(self, session, region, api_key, org_id, streaming_api_key=""):
        self.session = session
        self.base = REGIONS[region]
        self.api_key = api_key
        self.streaming_api_key = streaming_api_key or api_key
        self.org_id = org_id
        self._token = None
        self._token_until = 0
        self._jwt = None
        self._jwt_until = 0
        self._blocked_until = 0
        self._lock = asyncio.Lock()

    async def _request(self, method, path, *, headers=None, params=None, json=None, binary=False):
        if time.monotonic() < self._blocked_until:
            raise VerkadaError("Rate limited; waiting before retrying")
        try:
            async with self.session.request(
                method,
                self.base + path,
                headers=headers,
                params=params,
                json=json,
                timeout=aiohttp.ClientTimeout(total=25),
                allow_redirects=False,
            ) as response:
                if response.status == 401:
                    raise AuthenticationError("API credentials rejected or expired")
                if response.status == 403:
                    raise PermissionError("API permission denied for this feature")
                if response.status == 429:
                    try:
                        delay = min(3600, max(60, int(response.headers.get("Retry-After", "60"))))
                    except ValueError:
                        delay = 60
                    self._blocked_until = time.monotonic() + delay
                    raise VerkadaError("Rate limited; waiting before retrying")
                if response.status != 200:
                    raise VerkadaError(f"Verkada API returned HTTP {response.status}")
                if binary:
                    chunks, size = [], 0
                    async for chunk in response.content.iter_chunked(65536):
                        size += len(chunk)
                        if size > 8 * 1024 * 1024:
                            raise VerkadaError("Oversized thumbnail")
                        chunks.append(chunk)
                    data = b"".join(chunks)
                    if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
                        raise VerkadaError("Invalid or oversized thumbnail")
                    return data
                return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise VerkadaError("Cannot connect to Verkada or read its response") from err

    async def token(self):
        async with self._lock:
            if not self._token or time.monotonic() >= self._token_until:
                data = await self._request("POST", "/token", headers={"x-api-key": self.api_key})
                if not isinstance(data, dict) or not isinstance(data.get("token"), str):
                    raise VerkadaError("Unexpected token response")
                self._token = data["token"]
                self._token_until = time.monotonic() + 25 * 60
            return self._token

    async def request(self, method, path, **kwargs):
        for attempt in range(2):
            token = await self.token()
            try:
                return await self._request(
                    method, path, headers={"x-verkada-auth": token}, **kwargs
                )
            except AuthenticationError:
                if attempt:
                    raise
                self._token = None

    async def pages(self, path, key, params=None):
        result, seen = [], set()
        params = dict(params or {})
        params["page_size"] = 200
        for _ in range(100):
            data = await self.request("GET", path, params=params)
            if not isinstance(data, dict) or not isinstance(data.get(key), list):
                raise VerkadaError(f"Unexpected response format for {key}")
            result.extend(data[key])
            token = data.get("next_page_token") or data.get("page_token")
            if not token:
                return result
            if str(token) in seen:
                raise VerkadaError("Pagination repeated; results are incomplete")
            seen.add(str(token))
            params["page_token"] = token
        raise VerkadaError("Pagination limit reached; results are incomplete")

    async def cameras(self):
        return await self.pages("/cameras/v1/devices", "cameras")

    async def alerts(self, start, end):
        return await self.pages(
            "/cameras/v1/alerts", "notifications", {"start_time": start, "end_time": end}
        )

    async def lpr(self, camera_id, start, end):
        return await self.pages(
            "/cameras/v1/analytics/lpr/images",
            "detections",
            {
                "camera_id": camera_id,
                "start_time": start,
                "end_time": end,
            },
        )

    async def helix(self, camera_ids, event_type, start, end):
        data = await self.request(
            "POST",
            "/cameras/v1/video_tagging/event/search",
            json={
                "camera_ids": camera_ids,
                "event_type_uid": event_type,
                "start_time_ms": start * 1000,
                "end_time_ms": end * 1000,
            },
        )
        if not isinstance(data, dict) or not isinstance(data.get("events"), list):
            raise VerkadaError("Unexpected Helix events response")
        # The public schema returns next_token but documents no request cursor.
        # shortcut: refuse truncated Helix results; use narrower intervals for dense history.
        if data.get("next_token"):
            raise VerkadaError("Helix results are incomplete; search a shorter time range")
        return data["events"]

    async def thumbnail(self, camera_id, high=False, timestamp=None):
        params = {"camera_id": camera_id, "resolution": "hi-res" if high else "low-res"}
        path = "/cameras/v1/footage/thumbnails/latest"
        if timestamp is not None:
            path = "/cameras/v1/footage/thumbnails"
            params["timestamp"] = timestamp
        return await self.request("GET", path, params=params, binary=True)

    async def stream_url(self, camera_id, *, high=False, start=0, end=0):
        async with self._lock:
            if not self._jwt or time.monotonic() >= self._jwt_until:
                data = await self._request(
                    "GET",
                    "/cameras/v1/footage/token",
                    headers={"x-api-key": self.streaming_api_key},
                )
                if not isinstance(data, dict) or not isinstance(data.get("jwt"), str):
                    raise VerkadaError("Unexpected streaming token response")
                self._jwt = data["jwt"]
                self._jwt_until = time.monotonic() + 25 * 60
        return (
            self.base
            + "/stream/cameras/v1/footage/stream/stream.m3u8?"
            + urlencode(
                {
                    "org_id": self.org_id,
                    "camera_id": camera_id,
                    "jwt": self._jwt,
                    "start_time": start,
                    "end_time": end,
                    "resolution": "high_res" if high else "low_res",
                    "codec": "h264",
                    "type": "stream",
                }
            )
        )
