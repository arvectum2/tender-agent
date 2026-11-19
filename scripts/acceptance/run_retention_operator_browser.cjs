'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require(process.env.APR08_PLAYWRIGHT_MODULE);
const cfg=JSON.parse(fs.readFileSync(0,'utf8')),origin=new URL(cfg.origin);
assert.equal(origin.protocol,'http:');assert.equal(origin.hostname,'127.0.0.1');assert(origin.port);
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.APR08_CHROME,headless:true,args:['--disable-background-networking','--no-first-run']});
 try{
  const context=await browser.newContext({viewport:{width:cfg.width,height:900},extraHTTPHeaders:{Authorization:cfg.auth},serviceWorkers:'block'});
  await context.route('**/*',r=>new URL(r.request().url()).origin===origin.origin?r.continue():r.abort());
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.name));page.setDefaultTimeout(8000);
  const l=id=>page.locator('#'+id),wait=s=>page.waitForFunction(s=>document.getElementById('status').textContent===s,s);
  const recorded='Предложение записано. Разрешения не изменены.';
  assert.equal((await page.goto(origin.origin+'/api/operator/saas/retention-console')).status(),200);
  await l('tenant').fill(cfg.tenant);await l('load').click();await wait('Данные загружены');
  assert((await l('metrics').innerText()).includes('Комплекты: 1 шт.'));
  await l('order').fill('fixture-order');await l('policy').fill('fixture-policy');
  await l('confirm-schedule').check();await l('schedule').locator('button').click();await wait(recorded);
  let ids=await l('proposal').locator('option').evaluateAll(o=>o.map(x=>x.value).filter(Boolean));assert.equal(ids.length,1);
  await l('proposal').selectOption(ids[0]);await l('document').selectOption('archive:'+cfg.document);
  await l('evidence').fill('fixture-link');await l('confirm-link').check();
  await l('link').locator('button').click();await wait(recorded);
  assert.equal(await l('document').locator('option').count(),1);
  await l('existing').selectOption(ids[0]);assert.equal(await l('working').inputValue(),'30');
  assert(await l('order').evaluate(e=>e.readOnly));await l('working').fill('31');
  await l('confirm-schedule').check();await l('schedule').locator('button').click();await wait(recorded);
  assert((await l('metrics').innerText()).includes('устарели: 1'));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await l('tenant').fill('different');assert(await l('workspace').isHidden());assert.deepEqual(errors,[]);
  await context.close();console.log('RETENTION_OPERATOR_BROWSER_PASS',cfg.width);
 }finally{await browser.close()}
})().catch(e=>{console.error(e.name+': '+e.message);process.exitCode=1});
