'use strict';
// Actual Chromium, synthetic HTTP only, no real data or API.
const assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto');
const {chromium}=require(process.env.APR08_PLAYWRIGHT_MODULE);
const html=fs.readFileSync(process.env.READINESS_HTML,'utf8');
const origin='http://127.0.0.1:1',base='/api/saas/runs/fixture/application-review/previews';
const archive=Buffer.from('synthetic archive bytes'),hash=b=>crypto.createHash('sha256').update(b).digest('hex'),sha=hash(archive);
const p={preview_id:'p1',run_id:'fixture',procurement_ref:'synthetic',archive_sha256:sha,created_at:'2026-11-19T00:00:00Z',expires_at:'2026-11-19T00:15:00Z',status:'PRIVATE_PREVIEW',application_ready:false,external_action_allowed:false,inventory:[{path:'form.docx',role:'DRAFT_FORM'}],open_item_codes:['QUALIFICATION']};
(async()=>{const browser=await chromium.launch({executablePath:process.env.APR08_CHROME,headless:true,args:['--disable-background-networking','--no-first-run']});
try{for(const width of [1280,390]){
const c=await browser.newContext({viewport:{width,height:900},acceptDownloads:true,serviceWorkers:'block'}),page=await c.newPage();
page.setDefaultTimeout(6000);let tamper=true,confirmed=0;const errors=[];page.on('pageerror',e=>errors.push(e.message));
await c.route('**/*',async route=>{
 const req=route.request(),u=new URL(req.url());if(u.origin!==origin)return route.abort();
 if(u.pathname==='/saas')return route.fulfill({contentType:'text/html',body:html});
 assert.equal(req.headers().authorization,'Bearer synthetic-review-token');
 if(u.pathname==='/api/saas/me')return route.fulfill({json:{customer_id:'synthetic',role:'owner'}});
 if(u.pathname==='/api/saas/logout')return route.fulfill({json:{status:'logged_out'}});
 if(u.pathname===base&&req.method()==='POST'){assert.equal(req.postDataJSON().signatory,'DIRECTOR');return route.fulfill({status:201,json:p});}
 if(u.pathname===base+'/p1/archive')return route.fulfill({contentType:'application/zip',body:tamper?Buffer.from('tampered'):archive});
 if(u.pathname===base+'/p1/confirm'){assert.deepEqual(req.postDataJSON(),{archive_sha256:sha,confirm_reviewed_private_archive:true});confirmed++;return route.fulfill({json:{...p,status:'INTERNAL_REVIEW_RECORDED',decision_id:'d1'}});}
 if(u.pathname===base&&req.method()==='GET')return route.fulfill({json:{historical_only:true,application_ready:false,items:[{decision_id:'d1'}]}});
 throw Error('unexpected request '+u.pathname);
});
await page.goto(origin+'/saas');const l=id=>page.locator('#'+id),state=s=>page.waitForFunction(s=>document.getElementById('state').textContent===s,s);
await l('saved-token').fill('synthetic-review-token');await l('use-token').click();await state('Готово');
await page.getByText('Внутреннее согласование комплекта заявки (эксперимент)',{exact:true}).click();
await l('run-id').fill('fixture');await l('application-review-input').setInputFiles({name:'fixture.json',mimeType:'application/json',buffer:Buffer.from('{"signatory":"DIRECTOR"}')});
await l('application-review-preview').click();await l('application-review-summary').getByText(/Черновик для проверки/).waitFor();
assert(await l('application-review-confirm').isDisabled());assert(await l('application-review-ack').isDisabled());
await l('application-review-download').click();await state('Нужна проверка');assert(await l('application-review-ack').isDisabled());assert.equal(confirmed,0);
tamper=false;const pending=page.waitForEvent('download');await l('application-review-download').click();const d=await pending;await state('Готово');
assert.equal(d.suggestedFilename(),'PRIVATE-REVIEW-DO-NOT-SUBMIT.zip');assert.equal(hash(fs.readFileSync(await d.path())),sha);
assert(await l('application-review-confirm').isDisabled());await l('application-review-ack').check();await l('application-review-confirm').click();
await l('application-review-summary').getByText(/Внутреннее согласование записано/).waitFor();assert.equal(confirmed,1);assert(await l('application-review-confirm').isDisabled());
await l('application-review-history').click();await state('Готово');assert((await l('result').innerText()).includes('historical_only'));
await l('run-id').fill('other');assert.equal(await l('application-review-summary').innerText(),'');assert(await l('application-review-download').isDisabled());
await l('logout').click();await state('Готово');assert.equal(await l('run-id').inputValue(),'');assert.deepEqual(errors,[]);
await c.close();console.log('AUTHENTICATED_REVIEW_CHROMIUM_PASS',width);
}}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
