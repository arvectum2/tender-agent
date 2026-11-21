'use strict';
// Local synthetic fixture server only. No API response mocking.
const assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto');
const {chromium}=require(process.env.APR08_PLAYWRIGHT_MODULE);
const config=JSON.parse(fs.readFileSync(0,'utf8'));
const origin=new URL(config.origin);
assert.equal(origin.protocol,'http:');assert.equal(origin.hostname,'127.0.0.1');assert(origin.port);
const endpoint='/api/saas/runs/'+encodeURIComponent(config.run_id)+'/original-form-review/candidates';
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.APR08_CHROME,headless:true,args:['--disable-background-networking','--no-first-run']});
 try{
  const context=await browser.newContext({viewport:{width:config.width,height:900},acceptDownloads:true,serviceWorkers:'block'});
  await context.route('**/*',route=>new URL(route.request().url()).origin===origin.origin?route.continue():route.abort());
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.name));
  page.setDefaultTimeout(10000);
  const l=id=>page.locator('#'+id),state=s=>page.waitForFunction(s=>document.getElementById('state').textContent===s,s);
  const post=path=>page.waitForResponse(r=>new URL(r.url()).pathname===path&&r.request().method()==='POST');
  async function login(token){
   await l('saved-token').fill(token);await l('use-token').click();await state('Готово');
   await l('run-id').fill(config.run_id);await l('original-form-refresh').click();await state('Готово');
  }
  await page.goto(origin.origin+'/saas');await page.getByText('Независимая проверка оригинальной формы (эксперимент)',{exact:true}).click();
  await login(config.creator);await l('original-form-reviewer').selectOption(config.reviewer_id);
  await l('original-form-input').setInputFiles({name:'fixture-map.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(config.map))});
  const created=post(endpoint);await l('original-form-create').click();const response=await created;
  assert.equal(response.status(),201);const candidate=await response.json();await state('Готово');
  assert.equal(candidate.reviewer_id,config.reviewer_id);assert.equal(candidate.application_ready,false);
  assert.equal(await l('original-form-select').inputValue(),candidate.candidate_id);
  assert(await l('original-form-confirm').isDisabled());
  await l('logout').click();await state('Готово');assert(await l('original-form-editor').isHidden());
  await login(config.reviewer);
  await l('original-form-select').selectOption(candidate.candidate_id);
  assert(await l('original-form-ack').isDisabled());
  const pending=page.waitForEvent('download');await l('original-form-download').click();
  const file=await pending;await state('Готово');
  assert.equal(file.suggestedFilename(),'PRIVATE-UNSIGNED-FORM-DO-NOT-SUBMIT.docx');
  const bytes=fs.readFileSync(await file.path());
  assert.equal(bytes.subarray(0,2).toString(),'PK');
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),candidate.document_sha256);
  assert(await l('original-form-confirm').isDisabled());
  await l('original-form-ack').check();
  const acknowledged=post(endpoint+'/'+candidate.candidate_id+'/acknowledge');
  await l('original-form-confirm').click();const ack=await acknowledged;assert.equal(ack.status(),200);
  const receipt=await ack.json();await state('Готово');
  assert.equal(receipt.status,'INDEPENDENT_INTERNAL_REVIEW_RECORDED');assert.equal(receipt.application_ready,false);
  assert.equal(receipt.external_export_allowed,false);assert(receipt.receipt_id);
  assert((await l('original-form-summary').innerText()).includes('Историческое согласование записано'));
  assert(await l('original-form-confirm').isDisabled());
  await l('run-id').fill('other-synthetic-run');assert(await l('original-form-editor').isHidden());
  await l('logout').click();await state('Готово');assert.deepEqual(errors,[]);
  await context.close();
  console.log('LIVE_LOOPBACK_BROWSER_PASS',config.width);
 }finally{await browser.close();}
})().catch(e=>{console.error(e.name+': '+e.message);process.exitCode=1;});
