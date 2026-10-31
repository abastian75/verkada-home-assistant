# Validation — 0.2.3

## Added for 0.2.3

- Configured LPR/Helix cameras expose their latest plate and detection timestamp
  on the camera state. Sidebar live tiles and Camera cards render a caption below
  the video, without restarting video on state updates. Other cameras omit it.
- HA runtime checks cover plate metadata on configured sources and its absence on
  other cameras. Browser checks cover populated/empty/non-LPR captions, safe text
  rendering and live updates.
- Disabled HLS.js low-latency mode. HA documents that LL-HLS uses extra connections
  and its own player falls back to regular HLS for HTTP/1 multi-camera grids; our
  custom player previously lacked that protection. A browser regression decodes
  five simultaneous synthetic streams, checks advancing times and regular-HLS
  configuration on each, and verifies another HTTP request completes.
- Installed the change with exact encrypted-SMB read-back and selected low
  resolution through HA's options flow, retaining the other integration options.
- The actual HA dashboard rendered the LPR caption and five automatic camera
  streams, including Side Yard. The sustained test was interrupted by a separate
  user-initiated HA update/restart; initial playback is not a long-run pass.

- A cold-start regression replaces the custom-element registry before HA becomes
  ready. Cards now wait for HA before declaring their classes, avoiding definitions
  silently lost during the HA scoped-registry polyfill installation.

## Real installation checks on 2026-10-30

- HACS downloaded 0.2.0 on the user's existing HA installation; after restart,
  HA displayed version 0.2.0 and discovered the existing cameras.
- All five real cameras produced decoded video automatically in the sidebar,
  with nonzero video dimensions and advancing playback times. Some low-resolution
  feeds stalled/reconnected. High-resolution feeds also produced video on all five;
  this does not establish uninterrupted or multi-day reliability.
- Native LPR polling succeeded and imported recent detections from the initial
  24-hour window. Actual plate values, camera identifiers, images and credentials
  are excluded from the repository.
- A real recorded H.264 playlist returned HTTP 200 but its video segments returned
  HTTP 404, "Error fetching historical video m4s." The same camera/time interval
  with the documented default HEVC codec returned segments successfully and the
  official HA decoder decoded an actual frame. Version 0.2.1 requests HEVC for
  recordings and keeps H.264 for live video; contract tests verify both choices.
- The installed 0.2.1 recording path successfully served a real LPR clip through
  HA's HLS proxy and the official HA decoder decoded HEVC at 3840×2160. Two plate
  sensors were active; eight legacy non-LPR plate sensors were disabled/hidden.
- Created and read-back verified a separate example Verkada Cards dashboard on
  the user's HA, without modifying existing dashboards. Final real-browser card
  and HEVC rendering checks were blocked by a stalled Chrome automation connection;
  they are not claimed as passed. Synthetic card/editor/browser checks passed.

## Added for 0.2.0

- Native LPR initial/migration sync checks 24 hours once, without historical
  automation events. The first setup creates no plate sensors until a plate
  source is selected. Legacy non-LPR plate entities are disabled/hidden while
  retaining IDs, custom names and history.
- Actual HA runtime tests verify non-admin card access through existing camera
  permissions and rejection of a user with no camera access; card data excludes
  webhook URLs/credentials and playback rejects unauthorized camera IDs.
- Three bundled cards register in the picker and provide graphical editors.
  Browser checks cover camera selection, source filtering, recording errors,
  empty/denied states, XSS-safe rendering, and light/dark/mobile layouts.
- A browser regression advertises native HLS support, then proves the shared
  MSE player still decodes actual synthetic HLS, starts without a Live view
  click in the sidebar/camera card, and plays/closes a recording in the LPR card.
- Real HA inspection of the older release found LPR was not configured; enabled
  polling for the intended LPR camera only. Real camera discovery/thumbnails work.
  Reproduced the old grey/paused live-video pane; the updated player produced
  actual video automatically as described above.

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

- All permission combinations, continuous token renewal across an actual expiring
  Verkada stream, uninterrupted cloud playback and retained-video availability.
- End-to-end recorded playback in every browser/device; HEVC support varies.
- A real Command webhook reaching an externally exposed HA instance.
- Actual Helix event type/plate schema and production LPR volume.
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
