# Verkada for Home Assistant

Personal, unofficial HACS integration for an HA administrator with Verkada cameras.
The explicit brief is a UniFi Protect-like experience: native HA configuration,
discovered devices/entities, live views, alerts, recorded video, LPR and optional
Helix event history. Use only documented APIs. Publish under abastian75.

Scope: read-only camera integration; no door unlock, alarm control or user management.
Credentials stay in HA config entries. History stays in bounded local HA storage.
Cloud failures and partial source failures must be distinguishable from no events.
Live hardware validation requires a user's authorized API credentials.

Assumptions: use HA's existing theme, typography, menu and camera player; no separate
visual identity. A dedicated sidebar panel supplements standard dashboard entities.
