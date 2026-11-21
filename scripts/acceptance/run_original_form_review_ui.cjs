'use strict';
// Actual Chromium with synthetic local HTTP responses; never a live tenant or source.
const assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto');
const {chromium}=require(process.env.APR08_PLAYWRIGHT_MODULE);
const html=fs.readFileSync(process.env.READINESS_HTML,'utf8'),origin='http://127.0.0.1:1';
const base='/api/saas/runs/fixture/original-form-review/candidates';
const bytes=Buffer.from('synthetic-form-fixture'),hash=b=>crypto.createHash('sha256').update(b).digest('hex'),sha=hash(bytes);
const MIME='application/vnd.openxmlformats-officedocument.wordprocessingml.document';
const members=[{member_id:'author',name:'Synthetic author',role:'owner',active:true},{member_id:'reviewer',name:'Synthetic reviewer',role:'admin',active:true},{member_id:'viewer',name:'Synthetic viewer',role:'viewer',active:true}];
const fixture={candidate_id:'c1',run_id:'fixture',creator_id:'author',reviewer_id:'reviewer',candidate_sha256:'a'.repeat(64),document_sha256:sha,created_at:'2026-11-19T00:00:00Z',expires_at:'2026-11-19T00:30:00Z',status:'PRIVATE_FORM_REVIEW_PENDING',historical_only:true,application_ready:false,external_export_allowed:false,signed:false,submitted:false,source:{file_id:'f1',observed_version:'1',template_sha256:'b'.repeat(64)}};
(async()=>{const browser=await chromium.launch({executablePath:process.env.APR08_CHROME,headless:true,args:['--disable-background-networking','--no-first-run']});
try{for(const width of [1280,390]){
 const c=await browser.newContext({viewport:{width,height:900},acceptDownloads:true,serviceWorkers:'block'}),page=await c.newPage();
 let candidate=null,tamper=true,acks=0,creates=0;const errors=[];page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(8000);
 await c.route('**/*',async route=>{
  const req=route.request(),u=new URL(req.url());if(u.origin!==origin)return route.abort();
  if(u.pathname==='/saas')return route.fulfill({contentType:'text/html',body:html});
  const member=req.headers().authorization?.replace('Bearer ','');
  assert(['author','reviewer'].includes(member));
  if(u.pathname==='/api/saas/me')return route.fulfill({json:{member_id:member,role:member==='author'?'owner':'admin',legal_accepted:true}});
  if(u.pathname==='/api/saas/members')return route.fulfill({json:{members}});
  if(u.pathname==='/api/saas/logout')return route.fulfill({json:{status:'logged_out'}});
  if(u.pathname===base&&req.method()==='GET')return route.fulfill({json:{items:candidate?[candidate]:[],historical_only:true,application_ready:false,external_export_allowed:false}});
  if(u.pathname===base&&req.method()==='POST'){assert.equal(member,'author');assert.deepEqual(req.postDataJSON(),{item_code:'application_form',file_id:'f1',mapping:{},reviewer_id:'reviewer'});candidate={...fixture};creates++;return route.fulfill({status:201,json:candidate});}
  if(u.pathname===base+'/c1/document')return route.fulfill({contentType:MIME,body:tamper?Buffer.from('bad'):bytes});
  if(u.pathname===base+'/c1/acknowledge'){assert.equal(member,'reviewer');assert.deepEqual(req.postDataJSON(),{candidate_sha256:fixture.candidate_sha256,document_sha256:sha,confirm_exact_private_form:true});acks++;candidate={...candidate,status:'INDEPENDENT_INTERNAL_REVIEW_RECORDED',receipt_id:'receipt1'};return route.fulfill({json:candidate});}
  throw Error('unexpected request '+u.pathname);
 });
 await page.goto(origin+'/saas');const l=id=>page.locator('#'+id),state=s=>page.waitForFunction(s=>document.getElementById('state').textContent===s,s);
 const login=async member=>{await l('saved-token').fill(member);await l('use-token').click();await state('Готово');await l('run-id').fill('fixture');await l('original-form-refresh').click();await state('Готово');};
 await page.getByText('Независимая проверка оригинальной формы (эксперимент)',{exact:true}).click();
 await login('author');assert.deepEqual(await l('original-form-reviewer').locator('option').evaluateAll(opts=>opts.map(o=>o.value)),['','reviewer']);
 await l('original-form-reviewer').selectOption('reviewer');await l('original-form-input').setInputFiles({name:'map.json',mimeType:'application/json',buffer:Buffer.from('{"item_code":"application_form","file_id":"f1","mapping":{}}')});
 await l('original-form-create').click();await state('Готово');assert.equal(creates,1);
 assert.equal(await l('original-form-select').inputValue(),'c1');assert(await l('original-form-confirm').isDisabled());
 await l('logout').click();await state('Готово');assert(await l('original-form-editor').isHidden());
 await login('reviewer');await l('original-form-select').selectOption('c1');assert(await l('original-form-ack').isDisabled());
 await l('original-form-download').click();await state('Нужна проверка');assert(await l('original-form-ack').isDisabled());assert.equal(acks,0);
 tamper=false;const pending=page.waitForEvent('download');await l('original-form-download').click();const d=await pending;await state('Готово');
 assert.equal(d.suggestedFilename(),'PRIVATE-UNSIGNED-FORM-DO-NOT-SUBMIT.docx');assert.equal(hash(fs.readFileSync(await d.path())),sha);
 assert(await l('original-form-confirm').isDisabled());await l('original-form-ack').check();await l('original-form-confirm').click();await state('Готово');
 assert.equal(acks,1);assert((await l('original-form-summary').innerText()).includes('Историческое согласование записано'));assert(await l('original-form-confirm').isDisabled());
 await l('run-id').fill('different');assert(await l('original-form-editor').isHidden());await l('logout').click();await state('Готово');assert.deepEqual(errors,[]);
 await c.close();console.log('ORIGINAL_FORM_REVIEW_CHROMIUM_PASS',width);
}}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
