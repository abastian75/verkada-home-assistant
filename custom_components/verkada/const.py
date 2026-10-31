"""Constants for the unofficial Verkada integration."""

DOMAIN = "verkada"
VERSION = "0.2.8"
REGIONS = {
    "us": "https://api.verkada.com",
    "us2": "https://api.oh.verkada.com",
    "eu": "https://api.eu.verkada.com",
    "au": "https://api.au.verkada.com",
    "gov": "https://api.verkadagov.com",
}
DEFAULT_OPTIONS = {
    "poll_interval": 60,
    "alerts": True,
    "lpr_camera_ids": [],
    "helix_event_type": "",
    "helix_plate_attribute": "license_plate",
    "helix_camera_ids": [],
    "webhook_secret": "",
    "history_days": 7,
    "high_resolution": False,
    "live_codec": "hevc",
}
