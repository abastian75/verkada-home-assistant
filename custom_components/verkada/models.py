"""Validate and normalize event data without keeping raw credential-bearing payloads."""

import hashlib
import hmac
import json
import math
import time
from datetime import datetime
from urllib.parse import urlsplit


def verify_signature(body, header, secret, now=None):
    try:
        timestamp, signature = header.split("|")
        if abs((time.time() if now is None else now) - int(timestamp)) > 60:
            return False
        expected = hmac.new(
            secret.encode(), body + b"|" + timestamp.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except (ValueError, AttributeError):
        return False


def event_time(value):
    try:
        if isinstance(value, str) and not value.replace(".", "", 1).isdigit():
            value = datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        value = float(value)
        if value > 1e11:
            value /= 1000
        if not math.isfinite(value) or value < 0 or value > time.time() + 300:
            return None
        return value
    except (ValueError, TypeError, OverflowError):
        return None


def normalize_event(data, source, *, camera_id="", plate_attribute="license_plate"):
    if not isinstance(data, dict):
        return None
    details = data.get("details") if isinstance(data.get("details"), dict) else {}
    attributes = data.get("attributes") if isinstance(data.get("attributes"), dict) else {}
    timestamp = event_time(
        data.get(
            "time_ms",
            data.get(
                "timestamp", data.get("created", data.get("event_time", data.get("trigger_time")))
            ),
        )
    )
    if timestamp is None:
        return None
    kind = str(
        data.get("alert_type") or data.get("notification_type") or data.get("event_type") or source
    )[:150]
    cid = str(
        data.get("camera_id")
        or camera_id
        or (data.get("device_id") if data.get("product_type") == "CAMERA" else "")
        or ""
    )[:150]
    plate = (
        data.get("license_plate_number")
        or data.get("license_plate")
        or details.get("plate_number")
        or attributes.get(plate_attribute)
    )
    if isinstance(plate, (dict, list)):
        plate = None
    event = {
        "source": source,
        "kind": kind,
        "camera_id": cid,
        "timestamp": timestamp,
        "plate": str(plate)[:64] if plate is not None else None,
        "label": str(
            data.get("alert_name")
            or data.get("person_label")
            or details.get("profile_name")
            or data.get("trigger_device_name")
            or kind
        )[:200],
    }
    objects = data.get("objects") or (
        [details["object_type"]] if details.get("object_type") else []
    )
    event["objects"] = (
        [str(item)[:40] for item in objects[:10]] if isinstance(objects, list) else []
    )
    confidence = data.get("confidence")
    if isinstance(confidence, (float, int)) and math.isfinite(confidence):
        event["confidence"] = confidence
    image_url = data.get("image_url") or details.get("lpr_capture_url")
    if isinstance(image_url, str) and len(image_url) < 8192:
        try:
            url = urlsplit(image_url)
            if (
                url.scheme == "https"
                and not url.username
                and not url.password
                and url.hostname
                and any(
                    url.hostname == host or url.hostname.endswith("." + host)
                    for host in ("verkada.com", "verkadagov.com", "amazonaws.com", "cloudfront.net")
                )
            ):
                event["image_url"] = image_url
        except ValueError:
            pass
    # Helix schemas are user-defined. Keep scalar attributes, redact likely secrets.
    event["attributes"] = {
        str(k)[:80]: v if not isinstance(v, str) else v[:500]
        for k, v in list(attributes.items())[:25]
        if isinstance(v, (str, bool, int, float))
        and not any(
            term in str(k).lower()
            for term in ("password", "secret", "token", "key", "credential", "pin", "url")
        )
    }
    event["id"] = hashlib.sha256(
        json.dumps(
            [
                source,
                cid,
                timestamp,
                kind,
                event["plate"],
                data.get("event_type_uid"),
                event["attributes"],
            ],
            sort_keys=True,
        ).encode()
    ).hexdigest()[:32]
    return event
