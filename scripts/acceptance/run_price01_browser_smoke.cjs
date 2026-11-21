'use strict';
// Offline real-browser smoke. Every page network request is intercepted.
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const {chromium}=require(process.env.PRICE01_PLAYWRIGHT_MODULE||'playwright');
const chrome=process.env.PRICE01_CHROME;
const py=process.env.PYTHON||'python3';
const fixture=JSON.parse(execFileSync(py,['-c',`
import json
from src.modules.saas_foundation import company_historical_comparables as history
from src.modules.saas_foundation import company_reviewed_contracts as registry
from src.modules.saas_foundation.ui import render_saas_html
target={'customer_id':'fixture','case_id':'case-a','target_source_platform':'eis','target_external_id':'0158300034526000388','target_scope_verified':False}
history._context=lambda *a:target
registry._context=lambda *a:target
print(json.dumps({'html':render_saas_html(),'registry':registry.catalog(None,None,None),'archive':history.catalog(None,None,None)},ensure_ascii=False))
`],{encoding:'utf8',maxBuffer:4*1024*1024}));
(async()=>{
 const origin='https://price01-acceptance.invalid';
 const browser=await chromium.launch({...(chrome?{executablePath:chrome}:{}),headless:true,args:['--disable-background-networking','--no-first-run']});
 try{
  const ctx=await browser.newContext({viewport:{width:1280,height:900},serviceWorkers:'block'});
  const page=await ctx.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await ctx.route('**/*',async route=>{
   const url=route.request().url();
   if(url===origin+'/')return route.fulfill({contentType:'text/html',body:fixture.html});
   if(url===origin+'/api/saas/company-portfolio/cases/case-a/reviewed-contracts')return route.fulfill({json:fixture.registry});
   if(url===origin+'/api/saas/company-portfolio/cases/case-a/historical-comparables')return route.fulfill({json:fixture.archive});
   return route.abort();
  });
  await page.goto(origin+'/',{waitUntil:'domcontentloaded'});
  await page.evaluate(()=>{
   token='synthetic';
   companyIdentity={customer_id:'fixture',tenant_id:'fixture',member_id:'fixture',company_name:'Synthetic fixture',role:'owner',legal_accepted:true};
   companyCase={case_id:'case-a',source_platform:'eis',external_id:'0158300034526000388',registry_number:'0158300034526000388',revision:0};
   el('company-detail').hidden=false;syncCompanyControls();
  });
  await page.locator('#reviewed-contract-panel').waitFor({state:'visible'});
  await page.locator('#reviewed-contract-load').click();
  await page.waitForFunction(()=>el('reviewed-contract-result').textContent.includes('Нет опубликованных групп'));
  await page.locator('#historical-load').click();
  await page.waitForFunction(()=>el('historical-catalog').textContent.includes('74000'));
  assert.match(await page.locator('#reviewed-contract-result').innerText(),/Нет опубликованных групп/);
  await page.setViewportSize({width:390,height:844});
  for(const selector of ['#historical-comparable-panel','#reviewed-contract-panel']){
   const panel=page.locator(selector);await panel.scrollIntoViewIfNeeded();
   const result=await panel.evaluate(e=>({scroll:e.scrollWidth,client:e.clientWidth}));
   assert(result.scroll<=result.client+2,'Horizontal overflow: '+selector+' '+JSON.stringify(result));
  }
  await page.evaluate(()=>{resetCompanyDetail();syncCompanyControls()});
  await page.locator('#reviewed-contract-panel').waitFor({state:'hidden'});
  assert.equal(await page.locator('#reviewed-contract-result').textContent(),'');
  assert.deepEqual(errors,[]);
  console.log('PRICE01_BROWSER_SMOKE_PASS: pinned archive and registry, 1280/390px, cleared on case change');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
