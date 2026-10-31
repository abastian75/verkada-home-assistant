const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 // Reproduce a browser that advertises native HLS; MSE must still be preferred.
 await page.addInitScript(()=>{const original=HTMLMediaElement.prototype.canPlayType;HTMLMediaElement.prototype.canPlayType=function(type){return type==='application/vnd.apple.mpegurl'?'probably':original.call(this,type);};});
 await page.goto('http://127.0.0.1:8769/tests/cards_fixture.html?video=/tests/.video-fixture/source.m3u8');
 await page.waitForFunction(()=>{const video=document.querySelector('verkada-camera-card').shadowRoot.querySelector('video');return video.videoWidth===320&&video.currentTime>0.5&&!video.paused;});
 assert.ok(await page.locator('verkada-camera-card').evaluate(card=>!!card.shadowRoot.querySelector('video')._hls),'Advertised native HLS bypassed the reliable MSE player');
 // HTTP/1 camera grids must use regular HLS to leave connections for HA controls.
 await page.evaluate(()=>{const first=document.querySelector('verkada-camera-card');for(let i=0;i<4;i++){const card=document.createElement('verkada-camera-card');card.setConfig(first._config);card.hass=first._hass;first.parentElement.append(card);}});
 await page.waitForFunction(()=>[...document.querySelectorAll('verkada-camera-card')].every(card=>{const v=card.shadowRoot.querySelector('video');return v.videoWidth===320&&v.currentTime>2&&!v.paused&&v._hls.config.lowLatencyMode===false;}));
 const before=await page.locator('verkada-camera-card').evaluateAll(cards=>cards.map(card=>card.shadowRoot.querySelector('video').currentTime));
 await page.waitForFunction(before=>[...document.querySelectorAll('verkada-camera-card')].every((card,i)=>card.shadowRoot.querySelector('video').currentTime>before[i]+1),before);
 assert.equal(await page.evaluate(async()=>{const r=await fetch('/tests/fixtures.js');return r.status;}),200,'Grid blocked other HTTP requests');
 const lpr=page.locator('verkada-lpr-card');await lpr.getByRole('button',{name:'Watch recording for TEST123'}).click();
 await page.waitForFunction(()=>{const video=document.querySelector('verkada-lpr-card').shadowRoot.querySelector('video');return video&&video.videoWidth===320&&video.currentTime>0.5&&!video.paused;});
 await lpr.getByRole('button',{name:'Close recording'}).click();
 assert.equal(await lpr.locator('video').count(),0);
 assert.ok(await page.evaluate(()=>window.fixtureCalls.some(call=>call.action==='stop'&&call.client_id)));
 await page.goto('http://127.0.0.1:8769/tests/frontend_fixture.html?video=/tests/.video-fixture/source.m3u8');
 await page.waitForFunction(()=>{const video=document.querySelector('verkada-panel').shadowRoot.querySelector('#cameras video');return video.videoWidth===320&&video.currentTime>0.5&&!video.paused;});
 assert.equal(await page.getByRole('button',{name:'Live view',exact:true}).count(),0,'Sidebar still needs a Live view click');
 assert.deepEqual(errors,[]);await browser.close();console.log('PASS: actual HLS decode/autoplay in camera card, recorded card and automatic sidebar; MSE preferred over advertised native HLS');
})().catch(error=>{console.error(error);process.exit(1);});
