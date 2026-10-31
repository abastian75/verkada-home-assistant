const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 await page.goto('http://127.0.0.1:8769/tests/cards_fixture.html?video=/tests/.video-fixture/source.m3u8');
 const card=page.locator('verkada-camera-card');await card.getByText('Last plate: TEST123',{exact:true}).waitFor();
 await card.evaluate(c=>{c._config.title='LPR';c.hass={...c._hass};});
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:1000});
  const before=await card.evaluate(c=>{const root=c.shadowRoot,plate=root.querySelector('#plate'),title=root.querySelector('h2');const p=plate.getBoundingClientRect(),t=title.getBoundingClientRect();return {height:c.getBoundingClientRect().height,videoY:root.querySelector('video').getBoundingClientRect().top,inHeader:plate.parentElement.tagName==='HEADER',right:Math.abs(p.right-root.querySelector("header").getBoundingClientRect().right+16)<1,secondRow:p.top>=t.bottom,tooltip:plate.title};});
  assert.ok(before.inHeader&&before.right&&before.secondRow,'Plate is not below the title and right-aligned');
  assert.match(before.tooltip,/Last seen/);
  await card.evaluate(c=>{delete c._hass.states[c._config.entity].attributes.plate_tracking;c.hass={...c._hass};});
  const without=await card.evaluate(c=>({height:c.getBoundingClientRect().height,videoY:c.shadowRoot.querySelector('video').getBoundingClientRect().top}));
  assert.ok(Math.abs(before.height-without.height)<1,'LPR adds tile height');
  assert.ok(Math.abs(before.videoY-without.videoY)<1,'LPR shifts video down');
  await card.evaluate(c=>{c._hass.states[c._config.entity].attributes.plate_tracking=true;c._hass.states[c._config.entity].attributes.last_plate='X'.repeat(64);c.hass={...c._hass};});
  assert.ok(await card.evaluate(c=>c.shadowRoot.querySelector('header').scrollWidth<=c.getBoundingClientRect().width),'Long plate overflows header');
  await card.evaluate(c=>{c._hass.states[c._config.entity].attributes.last_plate='TEST123';c.hass={...c._hass};});
 }
 await page.goto('http://127.0.0.1:8769/tests/frontend_fixture.html?video=/tests/.video-fixture/source.m3u8');
 await page.getByText('Last plate: TEST123',{exact:true}).waitFor();
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:1000});
  assert.ok(await page.locator('verkada-panel').evaluate(c=>{const a=c.shadowRoot.querySelector('.camera-heading'),b=c.shadowRoot.querySelectorAll('.camera-heading')[1],p=a.querySelector('[data-plate-entity]');const title=a.querySelector('.camera-title').getBoundingClientRect(),plate=p.getBoundingClientRect();return plate.top>=title.bottom&&Math.abs(plate.right-a.getBoundingClientRect().right)<1&&p.parentElement===a&&Math.abs(a.getBoundingClientRect().height-b.getBoundingClientRect().height)<1&&a.scrollWidth<=a.clientWidth;}),'Sidebar LPR header changes tile height or overflows');
 }
 await browser.close();console.log('PASS: plate below title and right-aligned; equal tile/video height with or without LPR; desktop/mobile, timestamp tooltip, long plate clipping');
})().catch(e=>{console.error(e);process.exit(1);});
