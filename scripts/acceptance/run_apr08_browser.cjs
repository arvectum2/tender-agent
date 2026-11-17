'use strict';
const assert=require('node:assert/strict');
const {chromium}=require(process.env.APR08_PLAYWRIGHT_MODULE);
const origin=process.env.APR08_BROWSER_ORIGIN;
const run=process.env.APR08_BROWSER_RUN;
const target=new URL(origin);
assert.equal(target.hostname,'127.0.0.1');assert.equal(target.protocol,'http:');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.APR08_CHROME,headless:true,args:['--disable-background-networking','--no-first-run']});
 try{
  const context=await browser.newContext({viewport:{width:1280,height:900},serviceWorkers:'block',httpCredentials:{username:'apr08-replay',password:process.env.APR08_BROWSER_PASSWORD}});
  await context.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  const page=await context.newPage();page.setDefaultTimeout(8000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const l=id=>page.locator('#'+id);
  await page.goto(origin+'/pilot/tender-agent/workspace?run='+run);
  await l('report-panel').waitFor({state:'visible'});
  await page.getByText('Evidence Copilot — вопросы и расчёт по закупке',{exact:true}).click();
  const ask=async(question,pattern)=>{
    await l('copilot-answer-question').fill(question);
    const response=page.waitForResponse(r=>r.url().endsWith('/evidence-answer')&&r.request().method()==='POST');
    await l('copilot-answer-submit').click();assert.equal((await response).status(),200);
    await page.waitForFunction(({id,text})=>document.getElementById(id).innerText.includes(text),{id:'copilot-answer-result',text:pattern});
    return await l('copilot-answer-result').innerText();
  };
  assert.match(await ask('Какой срок оплаты услуг?','7 рабочих дней'),/SHA-256 оригинала/);
  await page.locator('#copilot-answer-result').screenshot({path:process.env.APR08_SCREENSHOT_DIR+'/payment.png'});
  assert.match(await ask('Какой срок оказания услуг?','07.12.2026'),/включительно/);
  assert.equal(await l('copilot-answer-result').getByText('Указано в источнике:',{exact:false}).count(),1);
  assert.equal(await l('copilot-answer-result').getByText('SHA-256 оригинала',{exact:false}).count(),2);
  await l('copilot-answer-result').screenshot({path:process.env.APR08_SCREENSHOT_DIR+'/delivery.png'});
  await ask('Можно ли подписывать контракт?','UNKNOWN');
  await ask('Какова НМЦК?','UNKNOWN'); // this legacy archived run has no pinned notice receipt
  await l('copilot-search').fill('оплата работ');await l('copilot-search-submit').click();
  await page.waitForFunction(()=>document.getElementById('copilot-search-result').innerText.includes('SHA-256'));
  await l('copilot-search').fill('иная тема');assert.equal(await l('copilot-search-result').innerText(),'');
  for(const [id,value] of Object.entries({'cost-external':'100','cost-labor':'200','cost-reserve':'20','cost-fixed':'5','cost-tax':'6','cost-variable':'2','cost-target':'50'}))await l(id).fill(value);
  await l('cost-offer-enabled').check();
  for(const [id,value] of Object.entries({'cost-offer-price':'500','cost-guarantee-fees':'10','cost-bid-cash':'30','cost-contract-cash':'40'}))await l(id).fill(value);
  await l('cost-scenario-confirm').check();await page.locator('#price-cost-form button[type=submit]').click();
  await page.waitForFunction(()=>document.getElementById('price-cost-result').innerText.includes('245,00'));
  const money=await l('price-cost-result').innerText();assert.match(money,/125,00/);assert.match(money,/UNKNOWN/);
  await l('price-cost-result').screenshot({path:process.env.APR08_SCREENSHOT_DIR+'/finance.png'});
  await l('cost-offer-price').fill('501');assert.equal(await l('price-cost-result').innerText(),'');
  await l('cost-clear-btn').click();assert(!await l('cost-offer-enabled').isChecked());
  assert.deepEqual(errors,[]);console.log('APR08_REAL_CHROMIUM_PASS payment delivery unknown legacy search finance clear; no page errors');
 }finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exitCode=1});
