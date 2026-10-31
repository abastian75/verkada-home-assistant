# Validation — 0.2.8

Last plate now shares the live camera title row in both the sidebar and Camera
card. The detection time remains in the label tooltip. Non-LPR cameras omit the
label; absent detections retain the existing empty message. Long plate strings
clip within the header without changing the video position or tile height.

Focused browser geometry checks at 1440px and 390px verify title/plate alignment,
identical tile height and video offset with/without LPR, long-content clipping,
and timestamp tooltip. Existing card/sidebar empty/XSS/state-update checks pass.
No Home Assistant restart or panel editor refresh is part of this frontend change.
The separately staged 0.2.7 recorded-playback backend still requires HA restart.

# Validation — 0.2.7

Watch requested the correct event-centered window (10 seconds before the detection
through 50 seconds after). The recorded playback path incorrectly fed the finite
vendor clip through HA's live remuxer. A real vendor response contained 17 segments,
68 seconds and ENDLIST; HA exposed a moving 2–3-segment, 8–12-second playlist without
ENDLIST. Those checks demonstrate a lost recording boundary, not a timezone fix.

Recorded playback now uses the same bounded camera-scoped relay as live footage,
with the requested start/end fixed in the server-side session. It preserves all
segments, encryption-key references and ENDLIST, and HLS.js explicitly starts at
position zero. Ordinary HA camera entities retain HA's own stream path.

Official HA tests verify exact requested camera/interval/codec, complete finite
playlist and first segment, stopped-session invalidation, eight-recording limit,
existing camera permissions and unload cleanup. Browser checks verify the clip
starts within its opening seconds and remains VOD, with unchanged Watch interval.
A real plate/vehicle visual match requires checking the installed backend after
HA restarts. No private footage, plates, camera identifiers or signed URLs are
published in this repository.

## Prior checks

# Validation — 0.2.6

The user reported continued spinning after 0.2.5. An old open dashboard was still
running 0.2.4, but a separate fresh 0.2.5 page also stalled on all five feeds at
about 133 video seconds. Cache alone did not explain the report. Fresh relay
requests still returned advancing playlists and playable media. The exact
upstream/browser trigger for the interruption remains unconfirmed.

The shared live player now reconnects after fatal network failures and after
25 seconds without playback progress. It renews expired relay sessions and
cancels retries when cards are removed. Recordings retain their existing lifecycle.
The sidebar also rebuilds cleared tiles when the same panel element reconnects.

Focused browser checks exercise real HLS decode, a simulated fatal network error,
an expired-session response, silent-stall recovery, retry cancellation, and
sidebar removal/reinsertion. Contract tests and isolated HA smoke tests pass in
the official HA 2026.10.4 container. Frontend assets were installed and read back
without restarting HA or publishing any dashboard configuration.

## Earlier bounded checks (0.2.5)


## Verified on the installed HA 2026.10.4 system

- Five real low-resolution HEVC Camera cards advanced together across a 208-second
  observation window: playback counters increased from about 28 seconds to
  233–236 seconds, with all five unpaused and ready at the final sample. This
  exceeded the old 4–70-second cutoff windows without a manual retry.
- Opened the original Verkada sidebar afterwards: all five cameras automatically
  started and advanced past 79 seconds. The LPR tile and Camera card both displayed
  the latest real plate and its timestamp; other cameras omitted the caption.
- A real HEVC recording played in the browser through the LPR card. Cold-start
  registration and actual card rendering were also verified after the registry fix.
- The user independently updated/restarted HA during the earlier test. That run
  was interrupted and is not counted as a playback pass. Subsequent checks used
  the resulting HA 2026.10.4 installation.

Private screenshots remain outside the public repository. These are bounded
desktop checks, not Companion-device acceptance or an all-day reliability test.

## Live passthrough and security

Longer native HEVC tests exposed an additional FFmpeg-reader failure: Side Yard
ended after 41.96 video seconds, although repeated HTTP playlist requests continued
to advance their media sequence. Changing FFmpeg's persistent-connection and
segment-retry options did not fix it. Custom live views now relay original HLS
playlists, initialization fragments, keys and segments through HA to HLS.js,
avoiding that reader/remuxer. Ordinary HA camera cards retain HA's stream path.

The authenticated `verkada/stream` command checks existing camera read permission
before issuing an unguessable, camera-scoped playback session. Resource URLs are
kept server-side, rewritten to opaque IDs, restricted to the configured Verkada
streaming host/path, and bounded to 256 resources per session / 64 sessions. Sessions
expire after five idle minutes and are discarded on integration unload. Redirects
are rejected; responses are size-limited; only Range headers are forwarded.

Actual isolated HA websocket/HTTP tests cover ordinary-user access, rejection of
a no-access user, JWT-free rewritten playlists (including MAP URIs), binary/range
responses, invalid/expired sessions, untrusted playlist hosts and unload cleanup.

## Native live-video fix

Direct parallel probes outside HA reproduced the reported stalls: Side Yard's
H.264 input ended after 4.96 video seconds / 120 packets, and Driveway's after
3.96 seconds / 96 packets. The native HEVC inputs each delivered the full 25-second
test window (577 / 601 packets). This is evidence of a truncated input feed,
separate from client connection pressure. Actual Chrome playback of a real HEVC
recording advanced past 38 seconds, confirming support on the user's browser.

Live defaults to HEVC, retaining low resolution. An explicit H.264 live format
option remains for browsers without HEVC support. Recordings remain HEVC.
Contract tests cover default/native and explicit H.264 URLs; the official HA
runtime tests cover setup/options and camera streams. Browser errors explain
HEVC support and the live compatibility option.

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
  the user's HA, without modifying existing dashboards. The 0.2.1 real-browser card
  and HEVC checks were initially blocked; the later checks above supersede that
  pending state. Synthetic card/editor/browser checks also passed.

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
