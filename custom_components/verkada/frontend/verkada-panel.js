import { attachVideo, clearVideo } from "./player.js?v=0.2.6";
import { plateText } from "./plate.js?v=0.2.6";
/* Native HA panel: no build step, external scripts or credentials in the browser. */
class VerkadaPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this._tab = "live";
    this._page = 0;
    this._request = 0;
  }
  set hass(value) {
    this._hass = value;
    for (const image of this.shadowRoot.querySelectorAll("img[data-entity]")) {
      const picture=value.states[image.dataset.entity]?.attributes.entity_picture;
      if (picture) image.src=value.hassUrl(picture);
    }
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) menu.hass = value;
    this._renderPlates();
    this._start();
  }
  set panel(value) { this._panel = value; this._start(); }
  set narrow(value) { const menu = this.shadowRoot.querySelector("ha-menu-button"); if (menu) menu.narrow = value; }
  connectedCallback() { this._start(); }
  disconnectedCallback() {
    clearInterval(this._timer); this._timer = null;
    this._clearVideos();
    this.shadowRoot.querySelector("#cameras")?.replaceChildren();
    if (this._hass && this._panel) this._call("stop").catch(() => {});
  }
  async _call(action, args = {}) {
    return this._hass.callWS({type: "verkada/dashboard", entry_id: this._panel.config.entry_id, action, ...args});
  }
  _start() {
    if (!this.isConnected || !this._hass || !this._panel?.config?.entry_id || this._timer) return;
    if (!this.shadowRoot.querySelector("main")) this._build();
    this._load();
    this._timer = setInterval(() => this._load(), 30000);
  }
  _build() {
    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;color:var(--primary-text-color,#212121);background:var(--primary-background-color,#fafafa);font-family:var(--paper-font-body1_-_font-family,Roboto,sans-serif);height:100%;overflow:auto;color-scheme:light dark}
        *{box-sizing:border-box} header{display:flex;align-items:center;gap:12px;padding:12px 20px;background:var(--app-header-background-color,var(--primary-color,#03a9f4));color:var(--app-header-text-color,#fff)}
        h1{font-size:22px;margin:0;flex:1;font-weight:500} h2{font-size:20px;font-weight:500;margin:0 0 16px} p{line-height:1.5;max-width:72ch} main{padding:24px;max-width:1500px;margin:auto}
        nav{display:flex;gap:8px;border-bottom:1px solid var(--divider-color,#ddd);padding-bottom:12px;margin-bottom:20px} button,input,select{font:inherit;color:inherit} button{min-height:44px;padding:8px 16px;border:1px solid var(--divider-color,#bbb);border-radius:8px;background:var(--card-background-color,#fff);cursor:pointer} button:hover{background:var(--secondary-background-color,#eee)} button:disabled{opacity:.6;cursor:wait} button[aria-selected="true"]{background:var(--primary-color,#03a9f4);color:var(--text-primary-color,#fff);border-color:var(--primary-color,#03a9f4)}
        header button{background:transparent;color:inherit;border-color:currentColor} :focus-visible{outline:3px solid var(--primary-color,#03a9f4);outline-offset:3px} ::selection{background:var(--primary-color,#03a9f4);color:var(--text-primary-color,#fff)}
        input,select{display:block;width:100%;min-height:44px;padding:8px;border:1px solid var(--divider-color,#aaa);border-radius:6px;background:var(--card-background-color,#fff);caret-color:var(--primary-color,#03a9f4)} label{display:grid;gap:6px;font-size:14px} .filters{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:16px;align-items:end;margin-bottom:16px} .actions{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}
        #health{margin:0 0 20px;line-height:1.5} #message{color:var(--error-color,#b00020);padding:12px 0;white-space:pre-wrap} #message:empty{display:none} .muted{color:var(--secondary-text-color,#666)} #cameras{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,360px),1fr));gap:20px} #cameras>div{min-width:0} .camera-title{margin:0 0 8px;font-weight:500} #cameras img,#cameras video{display:block;width:100%;aspect-ratio:16/9;object-fit:contain;background:#000;margin-bottom:8px} .table-wrap{overflow:auto} table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums} th,td{text-align:left;padding:12px;border-bottom:1px solid var(--divider-color,#ddd);vertical-align:middle} th{font-size:14px;color:var(--secondary-text-color,#666)} td{overflow-wrap:anywhere} td img{width:112px;height:64px;object-fit:contain;background:var(--secondary-background-color,#eee)} .plate{font-weight:600;letter-spacing:.04em;white-space:nowrap} #player{margin:20px 0;max-width:900px} #player video{display:block;width:100%;background:#000;aspect-ratio:16/9} #player:empty{display:none} details{margin:12px 0} summary{cursor:pointer;min-height:44px;padding:12px 0} code{display:block;padding:12px;white-space:normal;overflow-wrap:anywhere;background:var(--secondary-background-color,#eee)} [hidden]{display:none!important} #pager{display:flex;gap:16px;align-items:center;margin-top:16px} a{color:var(--primary-color,#007da8);text-underline-offset:3px} .empty{padding:32px 0} @media(max-width:600px){main{padding:16px}header{padding:10px 12px}th,td{padding:8px}.optional{display:none}}
      </style>
      <header><ha-menu-button></ha-menu-button><h1>Verkada</h1><button id="settings">Configure</button></header>
      <main><nav aria-label="Verkada views"><button data-tab="live" aria-selected="true">Live cameras</button><button data-tab="events" aria-selected="false">Events & recordings</button><button data-tab="setup" aria-selected="false">Connection</button></nav>
      <div id="message" role="alert"></div><div id="health" role="status">Connecting to Home Assistant…</div>
      <section id="live"><h2>Live cameras</h2><p class="muted">Live video starts automatically. Camera snapshots remain visible while streams connect.</p><div id="cameras"></div></section>
      <section id="events" hidden><h2>Events & recordings</h2>
        <div class="filters"><label>Camera<select id="camera" aria-label="Camera"><option value="">All cameras</option></select></label><label>Source<select id="source" aria-label="Source"><option value="">All saved events</option><option value="alert">Camera alerts</option><option value="lpr">Native LPR</option><option value="helix">Helix</option><option value="webhook">Other webhooks</option></select></label><label>Search plate or event<input id="query" type="search" maxlength="200" placeholder="Plate, event or camera"></label></div>
        <div class="filters"><label>From<input id="from" type="datetime-local"></label><label>To<input id="to" type="datetime-local"></label></div>
        <div class="actions"><button id="cloud">Search Verkada history</button><button id="refresh">Refresh</button><button id="play">Play selected interval</button></div>
        <p class="muted">Cloud search: choose a source and up to 24 hours. Playback: choose a camera and up to one hour. Watch opens a 60-second clip around an event.</p>
        <div id="player"></div><p id="count" class="muted"></p><div class="table-wrap"><table><thead><tr><th>Time</th><th>Camera</th><th>Plate / event</th><th class="optional">Image</th><th>Recording</th></tr></thead><tbody id="rows"></tbody></table></div><div id="pager"><button id="previous">Previous</button><span id="page"></span><button id="next">Next</button></div>
      </section>
      <section id="setup" hidden><h2>Connection</h2><p>Use <strong>Configure</strong> to open the integration settings. The options menu controls cameras, polling, LPR, Helix, history retention and video resolution. Use Reconfigure to replace API keys.</p><div id="sources"></div><h2>Incoming webhooks</h2><p id="webhook-state"></p><code id="webhook-url"></code><p>In Verkada Command → Admin → APIs and Integrations → Webhooks, enter this URL and the same shared secret configured in HA options. A reachable HTTPS URL with a trusted certificate is required. An unset external HA URL must be configured in HA network settings first.</p><p>API keys stay on Home Assistant. The panel is restricted to HA administrators; camera and sensor entities use HA's normal permissions. Local history holds up to 1,000 events within the configured retention period. Signed image links may expire sooner.</p></section></main>`;
    const root = this.shadowRoot;
    const now = new Date();
    const local = date => new Date(date.getTime() - date.getTimezoneOffset()*60000).toISOString().slice(0,16);
    root.querySelector("#from").value = local(new Date(now - 3600000));
    root.querySelector("#to").value = local(now);
    root.querySelector("#settings").onclick = () => {
      history.pushState(null,"","/config/integrations/integration/verkada");
      window.dispatchEvent(new Event("location-changed"));
    };
    root.querySelectorAll("[data-tab]").forEach(button => button.onclick = () => {
      this._tab = button.dataset.tab;
      root.querySelectorAll("[data-tab]").forEach(b => b.setAttribute("aria-selected",String(b === button)));
      for (const id of ["live","events","setup"]) root.querySelector("#"+id).hidden = id !== this._tab;
      if (this._tab !== "live") {this._clearVideos("#cameras video");root.querySelector("#cameras").replaceChildren();}
      else this._renderCameras();
    });
    for (const id of ["camera","source","query","from","to"]) root.querySelector("#"+id).addEventListener("input", () => { this._page=0; this._renderEvents(); });
    root.querySelector("#refresh").onclick = () => this._load("refresh");
    root.querySelector("#cloud").onclick = () => this._search();
    root.querySelector("#play").onclick = () => this._play();
    root.querySelector("#previous").onclick = () => { this._page=Math.max(0,this._page-1); this._renderEvents(); };
    root.querySelector("#next").onclick = () => { this._page++; this._renderEvents(); };
  }
  _text(id, value) { this.shadowRoot.querySelector("#"+id).textContent = value; }
  _renderPlates() {
    for (const label of this.shadowRoot.querySelectorAll("[data-plate-entity]")) {
      const text = plateText(this._hass?.states[label.dataset.plateEntity]?.attributes);
      label.textContent = text; label.hidden = !text;
    }
  }
  _error(error) { this._text("message", error?.message || String(error)); }
  async _load(action="status", args={}) {
    const request = ++this._request;
    try {
      const data = await this._call(action,args);
      if (request !== this._request || !this.isConnected) return;
      this._data=data;
      if (action==="refresh") {this._searchEvents=null;this._searchOmitted=0;}
      if (data.search_results) {this._searchEvents=data.search_results;this._searchOmitted=data.search_omitted;}
      if (this._searchEvents) data.events=[...new Map([...data.events,...this._searchEvents].map(e=>[e.id,e])).values()].sort((a,b)=>b.timestamp-a.timestamp);
      this._text("message", this._searchOmitted ? `${this._searchOmitted} search results are not displayed. Narrow the time range.` : "");
      this._text("health", data.connected ? `Connected · Last poll ${this._time(data.last_poll)}${Object.values(data.sources).some(s=>s.state!=="ok") ? " · Some event sources need attention; see Connection" : ""}` : "Verkada connection unavailable. Cached history is shown; check integration settings.");
      this.shadowRoot.querySelector("h1").textContent=data.title;
      const select = this.shadowRoot.querySelector("#camera");
      const value=select.value;
      select.replaceChildren(new Option("All cameras",""),...data.cameras.map(c=>new Option(c.name,c.camera_id)));
      select.value=data.cameras.some(c=>c.camera_id===value) ? value : "";
      this._renderCameras(); this._renderEvents(); this._renderSetup();
    } catch(error) { this._error(error); }
  }
  async _renderCameras() {
    if (!this._data || this._tab!=="live") return;
    const target=this.shadowRoot.querySelector("#cameras");
    const signature=JSON.stringify(this._data.cameras.map(c=>[c.camera_id,c.entity_id,c.name,c.status]));
    if (target.dataset.signature===signature && target.childElementCount) return;
    this._clearVideos("#cameras video");target.dataset.signature=signature; target.replaceChildren();
    if (!this._data.cameras.length) { target.textContent="No cameras found. Check API permissions and camera selection in integration options."; return; }
    try {
      if (this._tab!=="live" || !this.isConnected) return;
      for (const camera of this._data.cameras) {
        const wrapper=document.createElement("div");
        const title=document.createElement("p");title.className="camera-title";title.textContent=`${camera.name} · ${camera.status||"Unknown"}`;wrapper.append(title);
        if (!camera.entity_id) { const message=document.createElement("p");message.textContent="Camera entity is disabled or not ready.";wrapper.append(message); }
        else {
          const image=document.createElement("img");image.alt=`${camera.name} — latest cloud thumbnail`;image.dataset.entity=camera.entity_id;
          const picture=this._hass.states[camera.entity_id]?.attributes.entity_picture;
          if (picture) image.src=this._hass.hassUrl(picture);
          const video=document.createElement("video");video.hidden=true;video.controls=true;video.muted=true;video.autoplay=true;video.playsInline=true;
          const state=document.createElement("p");state.className="muted";state.setAttribute("role","status");state.textContent="Connecting live video…";
          const button=document.createElement("button");button.textContent="Retry";button.hidden=true;
          const startLive=async()=>{
            button.hidden=true;button.disabled=true;state.textContent="Connecting live video…";
            try {
              const result=await this._hass.callWS({type:"verkada/stream",entity_id:camera.entity_id});
              if(this._tab!=="live"||!wrapper.isConnected)return;
              image.hidden=true;video.hidden=false;video.poster=picture?this._hass.hassUrl(picture):"";
              await attachVideo(video,this._hass.hassUrl(result.url),error=>{state.textContent=error.message;button.hidden=false;},()=>{state.textContent="Live";button.hidden=true;},async()=>this._hass.hassUrl((await this._hass.callWS({type:"verkada/stream",entity_id:camera.entity_id})).url));
            } catch(error) {clearVideo(video);video.hidden=true;image.hidden=false;state.textContent=error.message;button.hidden=false;}
            finally {button.disabled=false;}
          };
          button.onclick=startLive;
          const plate=document.createElement("p");plate.dataset.plateEntity=camera.entity_id;plate.style.fontWeight="600";plate.setAttribute("role","status");
          wrapper.append(image,video,plate,state,button);
          if(["live","online"].includes((camera.status||"").toLowerCase()))setTimeout(startLive,0);
          else {state.textContent="Camera offline";button.hidden=false;}

        }
        target.append(wrapper);
      }
      this._renderPlates();
    } catch(error) { target.textContent=error.message; }
  }
  _time(timestamp) { return timestamp ? new Date(timestamp*1000).toLocaleString() : "Never"; }
  _range() {
    return {camera_id:this.shadowRoot.querySelector("#camera").value,
      start:Math.floor(new Date(this.shadowRoot.querySelector("#from").value).getTime()/1000),
      end:Math.floor(new Date(this.shadowRoot.querySelector("#to").value).getTime()/1000)};
  }
  _renderEvents() {
    if (!this._data) return;
    const root=this.shadowRoot, range=this._range(), source=root.querySelector("#source").value, query=root.querySelector("#query").value.toLowerCase();
    const names=Object.fromEntries(this._data.cameras.map(c=>[c.camera_id,c.name]));
    const events=this._data.events.filter(e=>(!range.camera_id||e.camera_id===range.camera_id)&&(!source||e.source===source)&&(!range.start||e.timestamp>=range.start)&&(!range.end||e.timestamp<=range.end)&&`${e.plate||""} ${e.label} ${e.kind} ${names[e.camera_id]||""} ${JSON.stringify(e.attributes||{})}`.toLowerCase().includes(query));
    this._page=Math.min(this._page,Math.max(0,Math.ceil(events.length/50)-1));
    const rows=root.querySelector("#rows"); rows.replaceChildren();
    for (const event of events.slice(this._page*50,(this._page+1)*50)) {
      const row=document.createElement("tr");
      for (const text of [this._time(event.timestamp), names[event.camera_id]||"Organization", event.plate||event.label]) { const cell=document.createElement("td"); cell.textContent=text; row.append(cell); }
      if (event.plate) row.children[2].className="plate";
      const detail=document.createElement("small"); detail.className="muted"; detail.style.display="block"; detail.textContent=event.source+(event.confidence!=null ? ` · ${Math.round(event.confidence*100)}% confidence` : ""); row.children[2].append(detail);
      if (Object.keys(event.attributes||{}).length) { const details=document.createElement("details"), summary=document.createElement("summary"), content=document.createElement("pre"); summary.textContent="Event details"; content.textContent=JSON.stringify(event.attributes,null,2); details.append(summary,content); row.children[2].append(details); }
      const imageCell=document.createElement("td"); imageCell.className="optional";
      if (event.image_url) { const image=document.createElement("img"); image.src=event.image_url; image.alt="Event thumbnail"; image.loading="lazy"; image.referrerPolicy="no-referrer"; imageCell.append(image); }
      else imageCell.textContent="—";
      row.append(imageCell);
      const cell=document.createElement("td");
      if (event.camera_id && names[event.camera_id]) { const button=document.createElement("button"); button.textContent="Watch"; button.onclick=()=>this._play({camera_id:event.camera_id,start:Math.max(1,Math.floor(event.timestamp)-10),end:Math.min(Math.floor(Date.now()/1000)-1,Math.floor(event.timestamp)+50)});cell.append(button); }
      else cell.textContent="No linked camera";
      row.append(cell); rows.append(row);
    }
    this._text("count",`${events.length} matching events · ${this._data.events.length} locally stored · up to ${this._data.history_days} days / 1,000 events. ${events.length ? "" : "Adjust filters, search Verkada history, or enable LPR/Helix in Configure."}`);
    this._text("page",`Page ${this._page+1} of ${Math.max(1,Math.ceil(events.length/50))}`);
    root.querySelector("#previous").disabled=this._page===0;
    root.querySelector("#next").disabled=(this._page+1)*50>=events.length;
  }
  async _search() {
    const source=this.shadowRoot.querySelector("#source").value;
    if (!["alert","lpr","helix"].includes(source)) { this._error(new Error("Choose Camera alerts, Native LPR or Helix before searching Verkada history.")); return; }
    const range=this._range();
    if (!Number.isFinite(range.start)||!Number.isFinite(range.end)) {this._error(new Error("Enter valid From and To dates."));return;}
    const button=this.shadowRoot.querySelector("#cloud"); button.disabled=true; button.textContent="Searching…";
    await this._load("search",{...range,source});
    button.disabled=false; button.textContent="Search Verkada history";
  }
  async _play(range=this._range()) {
    if (!Number.isFinite(range.start)||!Number.isFinite(range.end)) {this._error(new Error("Enter valid From and To dates."));return;}
    this._text("message", "");
    const target=this.shadowRoot.querySelector("#player");this._clearVideos("#player video");target.textContent="Starting recorded video…";
    try {
      const result=await this._call("playback",range);
      const label=document.createElement("p");label.textContent=`Recorded video · ${this._time(range.start)} – ${this._time(range.end)}`;
      this._clearVideos("#player video");
      const player=document.createElement("video");player.controls=true;player.autoplay=true;player.muted=true;player.playsInline=true;
      const close=document.createElement("button");close.textContent="Close playback";close.onclick=()=>{this._clearVideo(player);target.replaceChildren();this._call("stop").catch(e=>this._error(e));};
      target.replaceChildren(label,player,close);await this._attachVideo(player,this._hass.hassUrl(result.url));target.scrollIntoView({behavior:"smooth",block:"center"});
    } catch(error) {target.replaceChildren();this._error(error);}
  }
  _clearVideo(video) {clearVideo(video);}
  _clearVideos(selector="video") {this.shadowRoot.querySelectorAll(selector).forEach(clearVideo);}
  async _attachVideo(video,url) {await attachVideo(video,url,error=>this._error(error));}
  _renderSetup() {
    const data=this._data,target=this.shadowRoot.querySelector("#sources");target.replaceChildren();
    for (const [name,status] of Object.entries(data.sources)) { const paragraph=document.createElement("p");paragraph.textContent=`${name}: ${status.state}${status.message ? " — "+status.message : ""} · Last success ${this._time(status.last_success)}`;target.append(paragraph); }
    this._text("webhook-state",data.webhook_enabled ? `Signature checking enabled. Last accepted event: ${this._time(data.last_webhook)}.` : "Webhooks disabled. Set a shared secret of at least 16 characters in integration options to enable them.");
    this._text("webhook-url",data.webhook_url);
  }
}
if (!customElements.get("verkada-panel")) customElements.define("verkada-panel",VerkadaPanel);
