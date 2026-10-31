// Invented data only; used by browser fixtures, never by the integration.
const now=Math.floor(Date.now()/1000)-60;
export const cameras=[{camera_id:"camera-one",entity_id:"camera.synthetic_driveway",name:"Driveway",status:"Live",plate_tracking:true},{camera_id:"camera-two",entity_id:"camera.synthetic_gate",name:"Gate",status:"Offline",plate_tracking:false}];
const picture="data:image/svg+xml,"+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360"><rect width="640" height="360" fill="#263b42"/><path d="M180 360 285 140h70l105 220" fill="#829299"/><path d="M0 160 120 80l100 80v140H0" fill="#506b57"/><text x="320" y="55" fill="white" text-anchor="middle" font-family="sans-serif" font-size="22">Synthetic camera thumbnail</text></svg>');
const data={connected:true,last_poll:now,sources:{alerts:{state:"ok",last_success:now},"lpr:camera-one":{state:"ok",last_success:now}},plate_tracking:true,cameras,events:[{id:"1",source:"lpr",camera_id:"camera-one",timestamp:now-30,plate:"TEST123",label:"lpr",confidence:.98,attributes:{}},{id:"2",source:"alert",camera_id:"camera-one",timestamp:now-60,plate:null,label:"Person in driveway",attributes:{}},{id:"3",source:"helix",camera_id:"camera-two",timestamp:now-90,plate:"DEMO456",label:"Vehicle arrival",attributes:{make:"Synthetic",color:"Blue"}},{id:"4",source:"alert",camera_id:"camera-one",timestamp:now-120,plate:null,label:'<img src=x onerror="window.bad=true">',attributes:{}}]};
export function createHass(){
 const params=new URL(location.href).searchParams,video=params.get("video");window.fixtureCalls=[];
 return {states:Object.fromEntries(cameras.map(c=>[c.entity_id,{state:c.status==="Live"?"idle":"unavailable",attributes:{friendly_name:c.name,entity_picture:picture,...(c.plate_tracking?{plate_tracking:true,last_plate:params.has("empty")?null:"TEST123",plate_last_seen:now-30}:{})}}])),hassUrl:url=>url,callWS:async msg=>{
  window.fixtureCalls.push(msg);
  if(msg.type==="camera/stream"||msg.action==="playback"){if(video)return {url:video};throw new Error("Synthetic fixture: real video is tested separately in the HA runtime.");}
  if(msg.action==="stop")return {};
  if(params.has("denied"))throw new Error("You do not have access to this camera.");
  if(msg.action==="list")return {entries:[{entry_id:"synthetic-entry",name:"Verkada",cameras}]};
  const events=(params.has("empty")?[]:data.events).filter(e=>(!msg.camera_id||e.camera_id===msg.camera_id)&&(msg.source==="lpr"?e.plate:msg.source==="alert"?["alert","webhook"].includes(e.source):true));
  return {...structuredClone(data),events:events.slice(0,msg.limit||5)};
 }};
}
