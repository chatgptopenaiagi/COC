import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs';
let input='';for await(const chunk of process.stdin)input+=chunk;
const config=JSON.parse(input);input='';
const browser=await chromium.launch(process.platform==='win32'?{channel:'msedge',headless:true}:{headless:true});
const errors=[];
try {
 const page=await browser.newPage({viewport:{width:1440,height:1080}});
 page.on('pageerror',error=>errors.push(error.message));
 await page.goto(config.url);
 await page.locator('#agent').fill(config.agent);await page.locator('#token').fill(config.token);config.token='';
 await page.locator('#connect button').click();
 await page.waitForFunction(()=>document.querySelector('#connection').textContent.startsWith('Connected'));
 assert.equal(await page.locator('#token').inputValue(),'');
 await page.locator('#tool').selectOption('python-science|statistics');
 await page.locator('#arguments').fill('{"values":[10,20,30]}');
 await page.locator('#dispatch button').click();
 await page.waitForFunction(()=>document.querySelector('#task-rows').textContent.includes('succeeded'));
 await page.locator('#task-rows button').filter({hasText:'Inspect receipt'}).first().click();
 assert.match(await page.locator('#receipt').textContent(),/"mean": 20/);
 await page.locator('#browser-host').click();
 await page.waitForFunction(()=>document.querySelector('#tool').textContent.includes('Browser application'));
 await page.locator('#tool').selectOption('browser-tab|uppercase');
 await page.locator('#arguments').fill('{"text":"real browser"}');await page.locator('#dispatch button').click();
 await page.waitForFunction(()=>[...document.querySelectorAll('#task-rows tr')].some(r=>r.textContent.includes('browser-tab / uppercase')&&r.textContent.includes('succeeded')));
 const browserRow=page.locator('#task-rows tr').filter({hasText:'browser-tab / uppercase'});
 await browserRow.getByText('Inspect receipt').click();assert.match(await page.locator('#receipt').textContent(),/REAL BROWSER/);
 let chatResult=null;
 if(config.liveChat){
  await page.locator('#instruction').fill('Use python-science statistics with values [4,8,12], and javascript-web text_metrics with text "real independent application". Execute both application tools, then report the actual returned mean and word count.');
  await page.locator('#chat button').click();
  await page.waitForFunction(()=>{try{return JSON.parse(document.querySelector('#chat-result').textContent).status==='completed'}catch{return false}},{},{timeout:150000});
  chatResult=JSON.parse(await page.locator('#chat-result').textContent());
  assert(chatResult.tool_results.some(r=>r.state==='succeeded'&&r.result?.mean===8));
  assert(chatResult.tool_results.some(r=>r.state==='succeeded'&&r.result?.words===3));
  assert.equal(chatResult.process_ownership,'external');
 }
 await page.evaluate(()=>window.scrollTo(0,0));
 await page.screenshot({path:`evidence/integration/operator-${config.liveChat?'live-chat':'desktop'}.png`,fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:'evidence/integration/operator-mobile.png',fullPage:true});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth),false);
 assert.deepEqual(errors,[]);
 fs.writeFileSync(`evidence/integration/operator-${config.liveChat?'live-chat':'panel'}.json`,JSON.stringify({browser:'real Chromium/Edge',real_broker:true,scientific_result:20,browser_host_result:'REAL BROWSER',credential_persisted:false,desktop:[1440,1080],mobile:[390,844],page_errors:errors,live_chat:chatResult},null,2));
 console.log('Operator UI: real broker, scientific task, browser capability, mobile layout passed');
} finally {await browser.close()}
