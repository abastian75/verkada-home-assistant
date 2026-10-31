# Validation — 0.1.0

## Passed locally

- Python lint/format and JavaScript syntax checks.
- Ten contract/security tests: signature validation and stale/future replay
  rejection; native LPR and custom Helix mapping; untrusted image URL filtering;
  concurrent token caching and renewal; expired-auth retry; pagination completion
  and repeated-cursor rejection; explicit failure on truncated Helix results;
  streaming key and region/query construction; complete chunked thumbnail reads;
  rate-limit backoff.
- Isolated official Home Assistant **2026.10.4** container with external networking
  disabled: actual config flow, setup, options/reload, camera/sensor/event entities,
  partial source permission failure/recovery, history deduplication, diagnostics
  redaction, valid/invalid signed webhook delivery over HTTP, authenticated
  websocket commands, rejection of non-admin history access, invalid recording
  interval rejection, HLS output generated from synthetic footage, and unload.
- Edge/Chromium desktop **1440 px** and mobile **390 px** browser checks against
  a clearly labeled synthetic fixture: camera tiles, source/camera/text filters,
  cloud search request, playback error, webhook instructions, no horizontal main
  overflow, and HTML-in-event-label rendered as text rather than executed.
- The actual bundled HLS.js player decoded changing **320×180** synthetic video
  for both live-view and recorded-playback paths in the browser, without page errors.
- Rendered desktop/mobile views inspected; encoding and accessible select labels corrected.

The fixtures contain only invented cameras, plate numbers and credentials.
The mock API layer follows the response schemas embedded in Verkada's official
documentation (including `detections`, `notifications`, `events` and streaming `jwt`).

## Not yet validated

- Real Verkada authentication, organization-specific permissions or payloads.
- Real live/history footage, continuous token renewal across an actual expiring
  Verkada stream, cloud latency and retained-video availability.
- A real Command webhook reaching an externally exposed HA instance.
- Actual Helix event type/plate schema and production LPR volume.
- Installation through the user's existing HACS/HA instance or physical devices.
- Safari/iOS, other HA releases, multi-day reliability and large deployments.

## Reproduce

```sh
pip install ruff
ruff check custom_components tests
ruff format --check custom_components tests
node --check custom_components/verkada/frontend/verkada-panel.js
docker run --rm --network none -v "$PWD:/repo:ro" -w /repo ghcr.io/home-assistant/home-assistant:2026.10.4 python tests/test_core.py
docker run --rm --network none -v "$PWD:/repo:ro" -w /repo ghcr.io/home-assistant/home-assistant:2026.10.4 python tests/ha_smoke.py
```

For frontend tests, install Playwright 1.64.1 in your development environment,
install its Chromium browser, serve the repository on loopback port 8769 and run
`node tests/frontend.test.cjs`. `CHROME_PATH` can point to an existing Chromium
browser; `UI_OUTPUT` optionally selects a screenshot folder. The GitHub workflow
runs these checks along with HACS validation and hassfest.

The integration is an initial community release, not a claim of official vendor
certification, HACS default-list acceptance or UniFi Protect feature parity.
