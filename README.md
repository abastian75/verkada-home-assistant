# Verkada for Home Assistant

Custom live views relay Verkada's original HLS through HA without FFmpeg remuxing.
Long tests found HA's FFmpeg reader could stop while the original live playlists
continued advancing. API keys and streaming JWTs remain on HA; the browser receives
only camera-scoped playback URLs.

Video defaults to Verkada's native HEVC format, requiring HEVC support in the
viewing browser/device. For live video, a
**Live video format → H.264** compatibility option is available in integration
settings. Cloud buffering and retained-footage availability still apply.

Use the bundled Verkada Camera card for this live relay. Ordinary HA camera cards
continue to use HA's own stream component. Recorded H.264 conversion also returned
missing segments in real tests, so recordings use HEVC.

## Downloaded in HACS? Finish setup here

**Download installs the files. It does not open Verkada setup or add cameras yet.**

1. **Restart Home Assistant.** Open **Settings → HACS Restart required → Submit**.
   This briefly interrupts HA while it loads the new integration. A browser refresh
   is not a Home Assistant restart.
2. After HA reconnects, **[Set up Verkada](https://my.home-assistant.io/redirect/config_flow_start/?domain=verkada)**.
   This opens the API-key form in your HA instance. Enter credentials there.
3. Once connected, **Verkada appears in the sidebar** and cameras appear under
   **Settings → Devices & services → Verkada**.

If setup says **Integration not found**, finish the HA restart first, then reload
the browser and try the setup link again. If HACS shows **Version downloaded**,
the download already succeeded; continue at step 1.

**First time here? [Download Verkada in HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=abastian75&repository=verkada-home-assistant&category=integration), then follow the steps above.**

Unofficial, read-only Verkada camera integration for Home Assistant, distributed
through a **HACS custom repository**. Maintained in Anthony's personal GitHub
account, **abastian75**. Not affiliated with Verkada, MGT or Layer 3.

## Install and configure

Requires Home Assistant **2026.10.0 or newer**, HACS, internet access and a Verkada
Command organization with API access. This is an initial community release, not
an official or HACS default-list integration.

1. Open the HACS link above and add the repository. Download **Verkada**.
2. **Restart Home Assistant**.
3. **[Set up Verkada](https://my.home-assistant.io/redirect/config_flow_start/?domain=verkada)**,
   or go to **Settings → Devices & services → Add integration → Verkada**.
4. Enter a name, service region, organization UUID and API key. You may enter a
   separate streaming key, or leave it blank to use the main key for streaming.
5. Cameras appear as HA devices and camera entities. Open **Verkada** in the
   sidebar for live views, events and recorded playback.
6. In **Settings → Devices & services → Verkada**, open the entry's options
   (gear / Configure) to select cameras and enable LPR or Helix. Use the entry's
   **Reconfigure** menu to replace keys. Invalid credentials trigger HA reauthentication.

If the link cannot open HACS: **HACS → three-dot menu → Custom repositories**,
add `https://github.com/abastian75/verkada-home-assistant`, category **Integration**.
HACS must already be installed; the link does not install HACS itself.

Manual installation: copy `custom_components/verkada` into HA's
`config/custom_components/verkada`, restart, then follow step 3.

## What is included

| Feature | Behavior |
|---|---|
| Native HA setup | Config flow, options, credential replacement, reauthentication, multiple organizations |
| Camera devices | Discovered cameras, HA area suggestions from site names, model/serial metadata |
| Live video | Automatically playing sidebar streams, standard HA camera entities, HA-proxied HLS and token renewal |
| Camera health | Connected binary sensor and firmware-status sensor per camera |
| Alerts | Camera alert polling, optional signed incoming webhooks, source-health diagnostics |
| Native LPR | Opt-in per-camera polling, plate history/images, latest plate and last-seen sensors |
| Helix | Opt-in polling/search of one existing event type; configurable plate attribute; scalar event details |
| Recorded video | Timestamp-range HLS playback and Watch buttons around camera-linked events |
| Dashboard | Responsive sidebar panel with camera selection, event/plate text filter, date range and cloud search |
| Automations | `verkada_event` bus events for new records and an HA latest-event entity |
| Local history | Up to 1,000 events, 1–30 days (default 7), persisted on HA and removed when the integration is deleted |
| Dashboard cards | Camera, Events and LPR cards with visual editors; bundled and loaded automatically |

## Dashboard cards

After updating the integration, **restart HA and reload the browser**. Cards are
bundled with the integration; no second HACS repository or manual dashboard
resource is needed.

Open your dashboard → **Edit dashboard → Add card** and search **Verkada**:

- **Verkada Camera**: choose a camera. Live video starts automatically, with a
  thumbnail while connecting and automatic reconnection after network failures or stalled video. A Retry control remains available.
- **Verkada Events**: choose the integration and optionally a camera, title and
  row count. Shows recent alerts; **Watch** plays the associated recording.
- **Verkada LPR**: choose a configured plate camera or all cameras. Shows the
  latest plate, time, history and recordings. The camera selector includes only
  cameras configured as plate sources.

All three have graphical editors. Camera streaming uses HA's normal camera
permissions. The Events/LPR data endpoint filters both events and playback by
the user's camera-read permissions; it does not expose API keys, webhook URLs
or unrelated organization events. At most eight simultaneous historical streams
are allowed per integration; each card stops its own recording independently.

If the cards do not appear, fully reload the HA page after the integration restart.
For YAML dashboards the types are `custom:verkada-camera-card` (set `entity`),
`custom:verkada-events-card` and `custom:verkada-lpr-card` (set `entry_id` if you
have multiple organizations). Visual editing is recommended so IDs are selected
for you.

## Why Last plate can be unknown

`unknown` means the integration has no retained plate record for that camera; it
does not mean a vehicle is absent. The older release created plate entities for
all cameras even when plate collection was disabled. From 0.2.0 onward:

1. In integration options, select **LPR cameras** for cameras already running
   native LPR in Command. The first successful sync loads the previous **24 hours**
   once (also when upgrading), without firing automations for historical records.
2. For plates supplied by an external Helix source, set the event type/plate
   attribute and select **Helix plate cameras**. This creates plate entities
   without incorrectly polling the native LPR endpoint for those cameras.
3. Last plate / Plate last seen entities are created only for configured plate
   sources. Older unwanted entities are disabled and hidden by the integration;
   their names, IDs and recorder history are preserved. Selecting that camera
   later restores integration-hidden entities without overriding user disabling.

The camera inventory API does not supply a documented definitive LPR-mode flag.
The integration therefore uses explicit source selection, not camera model/name
guesses. If no plate was seen in the backfill window, the HA sensor remains
unknown until a detection is collected; the LPR card explains the empty state.
Check **Event sources** if polling fails; missing permissions are not treated as
an empty successful result.

This release deliberately excludes door unlock, alarm arm/disarm, credential/user
management, environmental sensor polling and a full Command-style recording
timeline. It reads and displays cameras/events; it does not replace the Verkada
recorder. HA camera entities can also be added to ordinary HA dashboards using
the normal camera cards. The custom sidebar history is administrator-only;
ordinary entities follow HA's normal permissions.

## Verkada API permissions

An organization administrator creates API keys in **Command → Admin → APIs and
Integrations**. This integration uses the documented APIs only.

- Required for setup: **read Camera devices**.
- Camera pictures: thumbnail/footage read access.
- Live and recorded video: the **Streaming** critical-endpoint permission, including
  live/history access for the desired cameras/sites. Use a separate streaming key
  if your Command key setup requires it.
- Camera alerts: alert read access (disable alert polling in options if unused).
- LPR: LPR read access; select only cameras already running in LPR mode.
- Helix: permission to search existing Helix events and an existing event type UID.
  Verkada's generic POST rule requires Read/Write; the search uses POST but this
  integration never creates or changes Helix records. A narrower read-only
  allowance for this search has not been verified with a real account.

Keys are stored in HA's config entries, never shipped to GitHub or sent to the
browser. Protect HA backups as they can contain these credentials. No password,
API key, plate history or real camera image is included in this repository.

Service regions: `us`, `us2` (Ohio), `eu`, `au`, `gov`. API keys work only in their
organization's region. Setup validates camera-read access; streaming/LPR/Helix
permissions are checked when those features are used, not assumed from setup.

## Dashboard and recordings

- **Live cameras:** online cameras start live video automatically; thumbnails
  remain as posters while connecting. Leaving the tab stops browser playback. HA's stream
  component retires idle stream workers. Camera entities also work in HA cards.
- **Events & recordings:** filter saved events by source/camera/text/time.
  Select Camera alerts, Native LPR or Helix and **Search Verkada history** to fetch
  an interval of up to 24 hours. Search older dates in additional intervals.
- Select a camera and past From/To interval of up to **one hour**, then **Play
  selected interval**. **Watch** selects a roughly 60-second clip around an event.
  Recent footage may not yet be available. Playback depends on camera/cloud retention.
- Cloud searches show at most 1,000 results and identify omitted rows. Older
  searches are held in the open browser session even if outside local retention;
  Refresh clears those temporary results.
- Image links provided by Verkada may expire. Image display is limited to HTTPS
  Verkada/AWS/CloudFront hosts; unsupported image hosts are omitted. Video and
  camera snapshots are proxied through HA. Event images are loaded by the browser
  from the vendor's signed URLs with no referrer.

LPR-enabled live tiles and Verkada Camera cards show the **last detected plate**
and its detection time below the video. Other cameras have no plate caption.
The caption updates from HA state without restarting the stream; it identifies
the latest detection, not a vehicle currently present in the live picture.

The bundled player uses regular HLS to avoid exhausting HTTP/1 browser connection
slots when several cameras play together. This trades some startup/live latency
for multi-camera reliability, following [HA's LL-HLS guidance](https://www.home-assistant.io/integrations/stream/#ll-hls---low-latency-hls).
For lower bandwidth and decoding load, leave **High resolution video and thumbnails**
off in integration options.

The API uses HLS; expect buffering and cloud latency. This is not a local RTSP
replacement or a promise of UniFi Protect feature parity. Still thumbnails may
lag by up to five minutes. HLS.js is bundled locally for browsers without native
HLS support; no player CDN or frontend build/install step is required.

## Helix versus native LPR

Native Verkada plate detections use the dedicated **LPR** API. Helix holds custom
events ingested by other systems. Enter the actual event type UID and exact
attribute containing the plate, such as `plate_id` or `license_plate`.
Only attributes present in that schema can be shown. A plate sighting is not a
reliable current vehicle-presence state. The integration does not post or modify
Helix records. If the API indicates pagination with an undocumented cursor,
search is reported incomplete; narrow the interval rather than silently losing rows.

## Optional real-time webhooks

Polling works without exposing HA to the internet. For lower-latency events:

1. Set a shared secret of **at least 16 characters** in integration options.
2. Set HA's external HTTPS URL in its network settings, using a certificate
   trusted by Verkada. A suitable reverse proxy or HA Cloud webhook route may be
   used, but must actually be reachable and compatible with signed requests.
3. Open the sidebar's **Connection** tab and copy the webhook URL. If HA has no
   external URL set, the panel shows only the path; complete your external setup first.
4. Add the URL and the **same secret** in Command's webhook configuration. Scope
   the subscription to the events you need (for example LPR or event-based alerts).

The integration verifies Verkada's `timestamp|signature` HMAC-SHA256 header over
the exact body plus `|timestamp`, rejects timestamps more than 60 seconds away
in either direction, validates the organization, caps payload size and deduplicates
normalized records. No unverified webhook can create an event. This does not
guarantee delivery through outages; polled APIs backfill the features they support.
Webhooks do not establish full New Alarms sensor/partition state or arm/disarm control.

## Data freshness and limits

Polling defaults to 60 seconds (30–900 configurable). New sources initially load
the last five minutes; native LPR loads 24 hours once. Neither initial import emits automations.
Subsequent polls overlap by ten seconds and deduplicate. Saved cursors permit
up to 24 hours of automatic backfill; longer gaps are flagged as partial when
first recovered and require manual searches if older events are needed.

The camera inventory failing makes coordinator entities unavailable. A failed
optional event source does not take cameras offline: its error and last success
are exposed in the **Event sources** sensor and Connection tab. Missing events
must not be interpreted as no activity. Camera statuses are polled, not instantaneous.
Rate limiting honors `Retry-After`; an organization-wide limit also applies to
other applications using the same Verkada organization.

Only the most recent event in a poll batch is represented by the latest-event
entity. The `verkada_event` event bus emits every new normalized event in that
batch. Replayed events already in retained history are suppressed; this is not
an exactly-once event transport across history expiration.

## Automation example

Create an automation using a **Manual event** trigger with event type
`verkada_event`. Event data includes `entry_id`, `source`, `kind`, `camera_id`,
`timestamp`, `plate`, `objects` and optional `confidence`/Helix `attributes`.

```yaml
alias: Known plate detected
triggers:
  - trigger: event
    event_type: verkada_event
    event_data:
      plate: TEST123
actions:
  - action: persistent_notification.create
    data:
      title: Vehicle detected
      message: "{{ trigger.event.data.plate }} was seen by {{ trigger.event.data.camera_id }}"
```

`TEST123` is synthetic. Do not automatically unlock a door or gate based solely
on a plate match.

## Validation and support status

See [VALIDATION.md](VALIDATION.md) for actual checks and remaining live checks.
The initial release is tested with synthetic fixtures inside the official HA
2026.10.4 image. It has **not yet been validated with a real Verkada account**.
Report issues without API keys, webhook secrets, signed image links or private footage.

Official references: [Verkada API](https://apidocs.verkada.com/llms.txt),
[streaming](https://apidocs.verkada.com/reference/getfootagestreamviewv1),
[webhook signatures](https://apidocs.verkada.com/reference/securing-webhooks),
[LPR](https://apidocs.verkada.com/reference/getlprimagesview),
[Helix search](https://apidocs.verkada.com/reference/postvideotaggingeventsearchviewv1),
[HACS custom repositories](https://www.hacs.xyz/docs/faq/custom_repositories/).
