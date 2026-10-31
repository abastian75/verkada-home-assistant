/* Shared HLS lifecycle for the sidebar and dashboard cards. */
let loading;
let HlsPlayer;
async function loadHls() {
  if (!loading) loading = new Promise((resolve, reject) => {
    const previous = window.Hls;
    const script = document.createElement("script");
    script.src = new URL("./vendor/hls.light.min.js", import.meta.url).href;
    script.onload = () => { HlsPlayer = window.Hls; window.Hls = previous; resolve(HlsPlayer); };
    script.onerror = () => { loading = null; reject(new Error("Video player could not load. Refresh the page.")); };
    document.head.append(script);
  });
  await loading;
  return HlsPlayer;
}

export function clearVideo(video) {
  video._verkadaGeneration = (video._verkadaGeneration || 0) + 1;
  clearTimeout(video._verkadaTimeout);
  clearTimeout(video._verkadaRetry);
  clearInterval(video._verkadaWatchdog);
  video._hls?.destroy(); video._hls = null;
  video.pause(); video.removeAttribute("src"); video.load();
}

export async function attachVideo(video, url, onError = () => {}, onPlaying = () => {}, refreshLiveUrl) {
  clearVideo(video);
  const generation = video._verkadaGeneration;
  const current = () => video.isConnected && video._verkadaGeneration === generation;
  video.autoplay = true; video.muted = true; video.defaultMuted = true; video.playsInline = true;
  video.setAttribute("playsinline", ""); video.setAttribute("muted", "");
  const fail = message => { if (current()) onError(new Error(message)); };
  const reconnect = (detail, expired = false) => {
    if (!current() || video._verkadaReconnecting) return;
    video._verkadaReconnecting = true;
    clearInterval(video._verkadaWatchdog);
    video._hls?.destroy(); video._hls = null;
    const retry = async () => {
      if (!current()) return;
      fail(`Live connection interrupted (${detail}). Reconnecting automatically…`);
      try {
        const nextUrl = expired ? await refreshLiveUrl() : url;
        if (current()) await attachVideo(video, nextUrl, onError, onPlaying, refreshLiveUrl);
      } catch {
        if (current()) video._verkadaRetry = setTimeout(retry, 15000);
      }
    };
    fail(`Live connection interrupted (${detail}). Reconnecting automatically…`);
    video._verkadaRetry = setTimeout(retry, 5000);
  };
  video._verkadaReconnecting = false;
  if (refreshLiveUrl) {
    let position = video.currentTime, lastProgress = Date.now();
    video._verkadaWatchdog = setInterval(() => {
      if (!current()) return;
      if (video.currentTime !== position) { position = video.currentTime; lastProgress = Date.now(); }
      else if (!video.paused && Date.now() - lastProgress > 25000) reconnect("no video progress");
    }, 5000);
  }
  const play = () => {
    if (!current()) return;
    video.play().catch(error => {
      if (error.name !== "AbortError") fail("Playback could not start. Select Retry or use the video's Play control.");
    });
  };
  video.onplaying = () => { if (current()) { clearTimeout(video._verkadaTimeout); onPlaying(); } };
  const decodeError = "This browser could not decode the video. Use a device with HEVC support, or select H.264 live video in Verkada options.";
  video.onerror = () => fail(decodeError);
  video._verkadaTimeout = setTimeout(() => {
    if (current() && (video.readyState < 2 || video.paused)) {
      if (refreshLiveUrl) reconnect("startup timeout");
      else fail("No playable video arrived. Select Retry; check streaming permissions and connectivity.");
    }
  }, 30000);
  const Hls = await loadHls();
  if (!current()) return;
  // Prefer MSE: some Chromium versions advertise native HLS without reliable LL-HLS playback.
  if (Hls?.isSupported()) {
    // LL-HLS long polling exhausts HTTP/1 connection slots in multi-camera grids.
    const hls = new Hls({ maxBufferLength: 30, backBufferLength: 15, lowLatencyMode: false, startPosition: refreshLiveUrl ? -1 : 0 }); video._hls = hls;
    hls.on(Hls.Events.MANIFEST_PARSED, play);
    hls.on(Hls.Events.ERROR, (_, data) => {
      if (!current() || !data.fatal) return;
      if (data.type === Hls.ErrorTypes.MEDIA_ERROR) { fail(decodeError); return; }
      if (refreshLiveUrl) { reconnect(data.details || "network error", data.response?.code === 404); return; }
      fail("Video stream failed. Select Retry; check streaming permissions, network access and recording retention.");
    });
    hls.attachMedia(video);
    hls.loadSource(url);
  } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
    video.onloadedmetadata = play;
    video.src = url;
  } else {
    throw new Error("This browser does not support HLS video. Use a current Chrome, Edge, Firefox or Safari browser.");
  }
}
