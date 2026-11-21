'use strict';
// Actual HTTPS origin. No API responses mocked. Temporary certificate key pin only.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {X509Certificate,createHash}=require('node:crypto');
const {chromium}=require(process.env.PRICE01_PLAYWRIGHT_MODULE);
const f=JSON.parse(fs.readFileSync(process.env.PRICE01_FIXTURE,'utf8'));
const url=new URL(f.origin);
assert(url.protocol==='https:'&&url.hostname==='127.0.0.1'&&url.port);
const spki=new X509Certificate(fs.readFileSync(f.certificate_der)).publicKey.export({type:'spki',format:'der'});
const pin=createHash('sha256').update(spki).digest('base64');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.PRICE01_CHROME,headless:true,args:['--disable-background-networking','--no-first-run','--ignore-certificate-errors-spki-list='+pin]});
 try{
  const ctx=await browser.newContext({viewport:{width:1280,height:900},serviceWorkers:'block'});
  await ctx.route('**/*',r=>new URL(r.request().url()).origin===f.origin?r.continue():r.abort());
  const page=await ctx.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const l=id=>page.locator('#'+id);
  const click=async id=>{await l(id).click();await page.waitForFunction(()=>!uiBusy);assert.equal(await l('state').textContent(),'Готово',id+': '+await l('result').textContent())};
  const signIn=async token=>{await l('saved-token').fill(token);await click('use-token');await click('company-load')};
  await page.goto(f.origin+'/saas');assert(await page.evaluate(()=>isSecureContext&&!!crypto.subtle));
  await signIn(f.token);
  await l('company-case').selectOption(f.case_id);await click('company-open');
  await click('historical-load');assert.match(await l('historical-catalog').innerText(),/74000/);
  await click('reviewed-contract-load');assert.match(await l('reviewed-contract-result').innerText(),/Нет опубликованных групп/);
  await click('cost-norm-load');await l('cost-norm-select').selectOption(f.norm_key);
  await l('price-mode').selectOption('itemized');await click('cost-norm-apply');
  assert.match(await l('price-line-list').innerText(),/Development/);
  for(const k of ['external_direct_rub','cash_overhead_rub','reserve_rub','fixed_platform_fees_rub','guarantee_financing_cost_rub'])await l('price-zero-'+k).check();
  await l('price-no-double').check();
  for(const [k,v] of Object.entries({revenue_tax_percent:'6',variable_platform_fee_percent:'0',minimum_profit_rub:'0',target_profit_rub:'0'}))await l('price-'+k).fill(v);
  await l('price-note').fill('Synthetic HTTPS browser approval binding');await l('price-confirm').check();
  await click('price-history');await click('price-preview');
  assert.match(await l('price-totals').innerText(),/10000\.00/);
  await l('price-save-confirm').check();await click('price-save');
  assert.equal(await page.evaluate(()=>priceHistory[0].revision),2);
  assert.equal(await page.evaluate(()=>priceHistory[0].itemized_estimate.lines[0].norm_binding.norm_key),f.norm_key);
  await signIn(f.foreign_token);assert.equal(await page.evaluate(()=>companyItems.length),0);
  assert.equal(await l('reviewed-contract-result').textContent(),'');
  assert.deepEqual(errors,[]);
  console.log('PRICE01_REAL_HTTPS_BROWSER_PASS: auth, portfolio, legacy archive, registry, norm binding, saved v2, tenant switch');
 }finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exitCode=1});
