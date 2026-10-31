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
  video._hls?.destroy(); video._hls = null;
  video.pause(); video.removeAttribute("src"); video.load();
}

export async function attachVideo(video, url, onError = () => {}, onPlaying = () => {}) {
  clearVideo(video);
  const generation = video._verkadaGeneration;
  const current = () => video.isConnected && video._verkadaGeneration === generation;
  video.autoplay = true; video.muted = true; video.defaultMuted = true; video.playsInline = true;
  video.setAttribute("playsinline", ""); video.setAttribute("muted", "");
  const fail = message => { if (current()) onError(new Error(message)); };
  const play = () => {
    if (!current()) return;
    video.play().catch(error => {
      if (error.name !== "AbortError") fail("Playback could not start. Select Retry or use the video's Play control.");
    });
  };
  video.onplaying = () => { if (current()) { clearTimeout(video._verkadaTimeout); onPlaying(); } };
  video.onerror = () => fail("The browser could not decode this video. Select Retry; check the camera's streaming format if it persists.");
  video._verkadaTimeout = setTimeout(() => {
    if (current() && (video.readyState < 2 || video.paused)) fail("No playable video arrived. Select Retry; check streaming permissions and connectivity.");
  }, 30000);
  const Hls = await loadHls();
  if (!current()) return;
  // Prefer MSE: some Chromium versions advertise native HLS without reliable LL-HLS playback.
  if (Hls?.isSupported()) {
    const hls = new Hls({ maxBufferLength: 30 }); video._hls = hls;
    hls.on(Hls.Events.MANIFEST_PARSED, play);
    hls.on(Hls.Events.ERROR, (_, data) => {
      if (!current() || !data.fatal) return;
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
