import { attachVideo, clearVideo } from "./player.js?v=0.2.2";
import { plateText } from "./plate.js?v=0.2.2";

const styles = `
  :host{display:block;color:var(--primary-text-color,#212121);font-family:var(--paper-font-body1_-_font-family,Roboto,sans-serif)}
  *{box-sizing:border-box}ha-card{display:block;background:var(--ha-card-background,var(--card-background-color,#fff));border-radius:var(--ha-card-border-radius,12px);border:var(--ha-card-border-width,1px) solid var(--ha-card-border-color,var(--divider-color,#ddd));overflow:hidden}
  header{display:flex;align-items:center;gap:12px;padding:16px 16px 12px}h2{font-size:20px;font-weight:500;line-height:1.3;margin:0;flex:1}p{line-height:1.45;margin:8px 0}button,input,select{font:inherit;color:inherit}button{min-height:44px;border:1px solid var(--divider-color,#bbb);background:var(--card-background-color,#fff);border-radius:8px;padding:8px 14px;cursor:pointer}button:hover{background:var(--secondary-background-color,#eee)}button:disabled{opacity:.6;cursor:wait}
  :focus-visible{outline:3px solid var(--primary-color,#007da8);outline-offset:2px}::selection{background:var(--primary-color,#007da8);color:var(--text-primary-color,#fff)}input,select{width:100%;min-height:44px;padding:8px;background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#bbb);border-radius:6px;caret-color:var(--primary-color,#007da8)}
  label{display:grid;gap:6px;font-size:14px;margin-bottom:16px}.content{padding:0 16px 16px}.muted{color:var(--secondary-text-color,#616161);font-size:14px}.error{color:var(--error-color,#b00020);white-space:pre-wrap;overflow-wrap:anywhere}.error:empty{display:none}.empty{padding:16px 0}.media{position:relative;background:#111;aspect-ratio:16/9}.media video,.media img{display:block;width:100%;height:100%;object-fit:contain}.status{padding:4px 16px 12px;font-size:14px;color:var(--secondary-text-color,#616161)}.status:empty{display:none}.badge{font-size:13px;color:var(--secondary-text-color,#616161)}
  ul{list-style:none;padding:0;margin:0}li{display:flex;align-items:center;gap:12px;padding:12px 0;border-top:1px solid var(--divider-color,#ddd)}li>div{flex:1;min-width:0}li img{width:88px;height:52px;object-fit:contain;background:var(--secondary-background-color,#eee)}.label{display:block;overflow-wrap:anywhere;font-size:15px}.plate{font-weight:600;letter-spacing:.04em;font-variant-numeric:tabular-nums}.latest{display:flex;align-items:center;gap:16px;padding:4px 0 20px}.latest strong{font-size:28px;letter-spacing:.04em;overflow-wrap:anywhere}.latest img{width:120px;max-height:80px;object-fit:contain}.latest>div{flex:1;min-width:0}.recording{margin-bottom:16px}.recording video{width:100%;aspect-ratio:16/9;background:#111}.recording:empty{display:none}.actions{display:flex;gap:12px;align-items:center;flex-wrap:wrap}details{margin-top:6px}summary{cursor:pointer;font-size:14px;padding:6px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}[hidden]{display:none!important}
  @media(max-width:420px){li{gap:8px}li img{width:64px;height:44px}.latest img{width:88px}button{padding:8px 10px}}
`;

class VerkadaBase extends HTMLElement {
  constructor() { super(); this.attachShadow({mode:"open"}); this._client=Array.from(crypto.getRandomValues(new Uint8Array(12)),v=>v.toString(16).padStart(2,"0")).join(""); }
  setConfig(config) {
    if (!config || typeof config.type!=="string") throw new Error("Choose a Verkada card type.");
    const changed=JSON.stringify(this._config)!==JSON.stringify(config);
    this._config={...config};
    if(changed){this._configGeneration=(this._configGeneration||0)+1;}
    if(changed&&this._built){this._cleanup();this._built=false;this._resolvedEntry=null;}
    this._start();
  }
  set hass(value) {this._hass=value;this._start();this._updateState?.();}
  connectedCallback(){this._start();}
  disconnectedCallback(){this._cleanup();}
  _cleanup(){clearInterval(this._timer);this._timer=null;this._running=false;this.shadowRoot.querySelectorAll("video").forEach(clearVideo);if(this._ownsPlayback){this._call("stop").catch(()=>{});this._ownsPlayback=false;}}
  _text(id,text){const el=this.shadowRoot.querySelector("#"+id);if(el)el.textContent=text;}
  _error(error){this._text("error",error?.message||String(error));}
  _frame(title){this.shadowRoot.innerHTML=`<style>${styles}</style><ha-card><header><h2></h2><span id="badge" class="badge"></span></header><div id="body"></div></ha-card>`;this.shadowRoot.querySelector("h2").textContent=this._config.title||title;}
  async _call(action,args={}){return this._hass.callWS({type:"verkada/cards",action,entry_id:this._config.entry_id||this._resolvedEntry||"",client_id:this._client,...args});}
  static getConfigElement(){return document.createElement("verkada-card-editor");}
  getCardSize(){return 5;}
  getGridOptions(){return {columns:12,rows:"auto",min_columns:6,min_rows:3};}
}

class VerkadaCameraCard extends VerkadaBase {
  static getStubConfig(){return {type:"custom:verkada-camera-card",entity:""};}
  _start(){
    if(!this.isConnected||!this._hass||!this._config)return;
    if(!this._built){
      this._frame("Verkada camera");
      this.shadowRoot.querySelector("#body").innerHTML=`<div class="media"><video controls autoplay muted playsinline></video></div><div class="content"><p id="plate" style="font-weight:600" role="status" hidden></p><p id="error" class="error" role="alert"></p><div class="actions"><p id="status" class="muted" role="status"></p><button id="retry" hidden>Retry</button></div></div>`;
      this.shadowRoot.querySelector("#retry").onclick=()=>{this._running=false;this._startCamera();};
      this._built=true;
    }
    this._updateState();this._startCamera();
  }
  _updateState(){
    if(!this._built)return;
    const state=this._hass.states[this._config.entity];
    const plate=this.shadowRoot.querySelector("#plate");plate.textContent=plateText(state?.attributes);plate.hidden=!plate.textContent;
    this.shadowRoot.querySelector("h2").textContent=this._config.title||state?.attributes.friendly_name||"Verkada camera";
    this._text("badge",state&&!["unavailable","unknown"].includes(state.state)?"Connected":"Unavailable");
    const video=this.shadowRoot.querySelector("video");
    if(state?.attributes.entity_picture)video.poster=this._hass.hassUrl(state.attributes.entity_picture);
    if(!this._config.entity)this._text("status","Edit this card and select a Verkada camera.");
    else if(!state)this._text("status","Camera entity not found. Check this card's camera selection.");
    else if(state.state==="unavailable")this._text("status","Camera unavailable. Check the integration connection.");
  }
  async _startCamera(){
    if(this._running||!this.isConnected||!this._config.entity)return;
    const state=this._hass.states[this._config.entity];
    if(!state||["unavailable","unknown"].includes(state.state))return;
    this._running=true;this._text("error","");this._text("status","Connecting live video…");
    const video=this.shadowRoot.querySelector("video"),button=this.shadowRoot.querySelector("#retry");button.hidden=true;
    try{
      const result=await this._hass.callWS({type:"camera/stream",entity_id:this._config.entity,format:"hls"});
      if(!this.isConnected||video!==this.shadowRoot.querySelector("video"))return;
      await attachVideo(video,this._hass.hassUrl(result.url),error=>{this._error(error);this._text("status","Live video unavailable");button.hidden=false;},()=>this._text("status","Live"));
    }catch(error){this._error(error);this._text("status","Live video unavailable");button.hidden=false;}
  }
}

class VerkadaHistoryCard extends VerkadaBase {
  _start(){
    if(!this.isConnected||!this._hass||!this._config)return;
    if(!this._built){
      this._frame(this.plates?"Verkada LPR":"Verkada events");
      this.shadowRoot.querySelector("#body").innerHTML=`<div class="content"><p id="error" class="error" role="alert"></p><div id="latest"></div><div id="recording" class="recording"></div><p id="status" class="muted" role="status">Loading…</p><ul id="events"></ul><div class="actions"><button id="refresh">Refresh</button></div></div>`;
      this.shadowRoot.querySelector("#refresh").onclick=()=>this._refresh();this._built=true;
    }
    if(!this._timer){this._refresh();this._timer=setInterval(()=>this._refresh(),15000);}
  }
  async _refresh(){
    if(this._busy)return;this._busy=true;const generation=this._configGeneration;const button=this.shadowRoot.querySelector("#refresh");button.disabled=true;
    try{
      if(!this._config.entry_id&&!this._resolvedEntry){const list=await this._call("list");if(list.entries.length!==1)throw new Error("Edit this card and choose your Verkada integration.");this._resolvedEntry=list.entries[0].entry_id;}
      const data=await this._call("status",{camera_id:this._config.camera_id||"",source:this.plates?"lpr":"alert",limit:Math.max(1,Math.min(20,Number(this._config.rows)||5))});
      if(!this.isConnected||generation!==this._configGeneration)return;
      this._data=data;this._text("error","");this._renderEvents(data);
    }catch(error){this._error(error);this._text("status","Could not load Verkada history.");}
    finally{this._busy=false;button.disabled=false;}
  }
  _renderEvents(data){
    const names=Object.fromEntries(data.cameras.map(c=>[c.camera_id,c.name]));
    this._text("badge",data.connected?"Connected":"Unavailable");
    const selected=this._config.camera_id;
    const tracking=selected?data.cameras.find(c=>c.camera_id===selected)?.plate_tracking:data.plate_tracking;
    const failures=Object.entries(data.sources).filter(([key,value])=>value.state!=="ok"&&(!this.plates||key==="helix"||key.startsWith("lpr:")));
    if(!data.connected)this._text("error","Connection unavailable. Showing retained history.");
    else if(failures.length)this._text("error",failures.map(([key,value])=>`${key}: ${value.message||value.state}`).join("\n"));
    this._text("status",this.plates&&!tracking?"Plate tracking is not enabled for this camera. Select LPR cameras or Helix plate cameras in integration options.":!data.events.length?(this.plates?"No plate detections in retained history. The first LPR sync checks the last 24 hours.":"No alerts in retained history."):`${data.events.length} recent ${this.plates?"plate detections":"alerts"} · Updated ${new Date((data.last_poll||Date.now()/1000)*1000).toLocaleTimeString()}`);
    const latest=this.shadowRoot.querySelector("#latest");latest.replaceChildren();
    if(this.plates&&data.events[0]){
      const event=data.events[0],box=document.createElement("div");box.className="latest";
      const details=document.createElement("div"),plate=document.createElement("strong"),seen=document.createElement("p");plate.textContent=event.plate;plate.className="plate";seen.className="muted";seen.textContent=`${names[event.camera_id]||"Camera"} · ${new Date(event.timestamp*1000).toLocaleString()}`;details.append(plate,seen);box.append(details);
      if(event.image_url)box.append(this._image(event));latest.append(box);
    }
    const list=this.shadowRoot.querySelector("#events");list.replaceChildren();
    for(const event of data.events){
      const row=document.createElement("li"),details=document.createElement("div"),label=document.createElement("span"),meta=document.createElement("p");label.className=this.plates?"label plate":"label";label.textContent=event.plate||event.label;meta.className="muted";meta.textContent=`${names[event.camera_id]||"Camera"} · ${new Date(event.timestamp*1000).toLocaleString()}${event.confidence!=null?` · ${Math.round(event.confidence*100)}%`:""}`;details.append(label,meta);
      if(Object.keys(event.attributes||{}).length){const extra=document.createElement("details"),summary=document.createElement("summary"),pre=document.createElement("pre");summary.textContent="Details";pre.textContent=JSON.stringify(event.attributes,null,2);extra.append(summary,pre);details.append(extra);}
      if(event.image_url&&!this.plates)row.append(this._image(event));row.append(details);
      const watch=document.createElement("button");watch.textContent="Watch";watch.setAttribute("aria-label",`Watch recording for ${event.plate||event.label}`);watch.onclick=()=>this._play(event);row.append(watch);list.append(row);
    }
  }
  _image(event){const image=document.createElement("img");image.src=event.image_url;image.alt=this.plates?"Plate capture":"Event capture";image.loading="lazy";image.referrerPolicy="no-referrer";return image;}
  async _play(event){
    const target=this.shadowRoot.querySelector("#recording");target.querySelectorAll("video").forEach(clearVideo);target.textContent="Starting recording…";
    try{
      const result=await this._call("playback",{camera_id:event.camera_id,start:Math.max(1,Math.floor(event.timestamp)-10),end:Math.min(Math.floor(Date.now()/1000)-1,Math.floor(event.timestamp)+50)});
      this._ownsPlayback=true;if(!this.isConnected){await this._call("stop");return;}
      const video=document.createElement("video");video.controls=true;video.muted=true;video.autoplay=true;video.playsInline=true;
      const close=document.createElement("button");close.textContent="Close recording";close.onclick=()=>{clearVideo(video);target.replaceChildren();this._ownsPlayback=false;this._call("stop").catch(error=>this._error(error));};
      target.replaceChildren(video,close);await attachVideo(video,this._hass.hassUrl(result.url),error=>this._error(error));
    }catch(error){target.replaceChildren();this._error(error);}
  }
}
class VerkadaEventsCard extends VerkadaHistoryCard{static getStubConfig(){return {type:"custom:verkada-events-card",rows:5};}}
class VerkadaLprCard extends VerkadaHistoryCard{get plates(){return true;}static getStubConfig(){return {type:"custom:verkada-lpr-card",rows:5};}}

class VerkadaCardEditor extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});}
  setConfig(config){if(JSON.stringify(this._config)!==JSON.stringify(config)){this._config={...config};this._render();}}
  set hass(value){this._hass=value;if(!this._loading&&!this._entries){this._loading=true;value.callWS({type:"verkada/cards",action:"list"}).then(data=>{this._entries=data.entries;this._render();}).catch(()=>{this._entries=[];this._render();});}this._render();}
  _change(key,value){this._config={...this._config,[key]:value};this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:this._config},bubbles:true,composed:true}));if(key==="entry_id")this._render(true);}
  _render(force=false){
    if(!this._config||!this._hass)return;
    const signature=JSON.stringify([this._config.type,this._config.entry_id,this._entries]);if(!force&&this._signature===signature)return;this._signature=signature;
    this.shadowRoot.innerHTML=`<style>${styles}</style><div id="fields"></div><p class="muted">Camera and event access follows Home Assistant permissions. Configure LPR sources in the integration options.</p>`;
    const fields=this.shadowRoot.querySelector("#fields"),entries=this._entries||[];
    const input=(title,key,type="text")=>{const label=document.createElement("label"),control=document.createElement("input");label.textContent=title;control.type=type;control.value=this._config[key]??"";if(type==="number"){control.min=1;control.max=20;}control.onchange=()=>this._change(key,type==="number"?Math.max(1,Math.min(20,Number(control.value)||5)):control.value);label.append(control);fields.append(label);};
    const select=(title,key,options,empty)=>{const label=document.createElement("label"),control=document.createElement("select");label.textContent=title;control.setAttribute("aria-label",title);control.append(new Option(empty,""),...options.map(o=>new Option(o.label,o.value)));control.value=this._config[key]||"";control.onchange=()=>this._change(key,control.value);label.append(control);fields.append(label);};
    input("Title (optional)","title");
    if(this._config.type==="custom:verkada-camera-card")select("Camera","entity",entries.flatMap(e=>e.cameras.map(c=>({value:c.entity_id,label:c.name}))),"Select a camera");
    else{
      select("Verkada integration","entry_id",entries.map(e=>({value:e.entry_id,label:e.name})),entries.length===1?`Automatic: ${entries[0].name}`:"Select an integration");
      const entry=entries.find(e=>e.entry_id===this._config.entry_id)||(entries.length===1?entries[0]:null);
      select("Camera","camera_id",(entry?.cameras||[]).filter(c=>this._config.type!=="custom:verkada-lpr-card"||c.plate_tracking).map(c=>({value:c.camera_id,label:c.name})),"All cameras");
      input("Number of events","rows","number");
    }
  }
}

for(const [tag,klass] of [["verkada-camera-card",VerkadaCameraCard],["verkada-events-card",VerkadaEventsCard],["verkada-lpr-card",VerkadaLprCard],["verkada-card-editor",VerkadaCardEditor]])if(!customElements.get(tag))customElements.define(tag,klass);
window.customCards=window.customCards||[];
for(const [type,name,description] of [
  ["verkada-camera-card","Verkada Camera","Automatically playing live video with connection status."],
  ["verkada-events-card","Verkada Events","Recent camera alerts with recorded-video playback."],
  ["verkada-lpr-card","Verkada LPR","Latest plate, detection history and linked recordings."],
])if(!window.customCards.some(card=>card.type===type))window.customCards.push({type,name,description,preview:true,documentationURL:"https://github.com/abastian75/verkada-home-assistant#dashboard-cards"});
