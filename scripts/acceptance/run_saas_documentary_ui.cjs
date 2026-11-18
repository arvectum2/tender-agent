'use strict';
// Real browser rendering of current HTML; every HTTP response is a synthetic fixture.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require(process.env.APR08_PLAYWRIGHT_MODULE);
const origin='http://127.0.0.1:1';
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.APR08_CHROME,headless:true,args:['--disable-background-networking','--no-first-run']});
 try {
  for(const width of [1280,390]){
   const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});
   const page=await context.newPage();page.setDefaultTimeout(8000);
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   let status='ARCHIVED_QUOTATION_CHECKLIST_REVIEW_ONLY',called=0;
   await context.route('**/*',async route=>{
    const req=route.request(),url=new URL(req.url());
    if(url.origin!==origin)return route.abort();
    if(url.pathname==='/saas')return route.fulfill({contentType:'text/html',body:fs.readFileSync(process.env.READINESS_HTML,'utf8')});
    assert.equal(req.headers().authorization,'Bearer saas_synthetic_ui_only');
    let value;
    if(url.pathname==='/api/saas/me')value={customer_id:'synthetic',role:'owner'};
    else if(url.pathname==='/api/saas/logout')value={status:'logged_out'};
    else if(url.pathname==='/api/saas/profile/documentary-readiness'){
     value={contract:'tenant_documentary_readiness_v1',qualification_verified:false,external_action_allowed:false,recommendation:'DEFER',
      requirements:['current_registry','sme_membership','current_tax','completed_experience','license_scope_review','certificate_scope_review','sro_scope_review'].map(code=>({requirement_code:code,state:code==='sme_membership'?'DOCUMENTED_OWNER_CLAIM_REVIEW_REQUIRED':'MISSING',claim_assertion:'PRESENT'}))};
    }else if(url.pathname==='/api/saas/runs/fixture/application-readiness'){
     called++;
     const body=req.postDataJSON();assert.equal(body.signatory,'DIRECTOR');assert.equal(body.goods_used,false);
     value={contract:'tenant_archived_application_readiness_v1',run_id:'fixture',...body,status,qualification_verified:false,application_ready:false,external_action_allowed:false,recommendation:'DEFER',
      rows:status==='ARCHIVED_QUOTATION_CHECKLIST_REVIEW_ONLY'?Array.from({length:9},(_,i)=>({title:'Требование '+i,applicability:'REQUIRED',state:'REVIEW_REQUIRED',documentary_candidates:[]})):[]};
    }else throw Error('Unexpected request: '+url.pathname);
    return route.fulfill({json:value});
   });
   await page.goto(origin+'/saas');
   const l=id=>page.locator('#'+id);
   await l('saved-token').fill('saas_synthetic_ui_only');await l('use-token').click();await page.waitForFunction(()=>document.getElementById('state').textContent==='Готово');
   await page.getByText('Квалификационные доказательства',{exact:true}).click();
   await l('read-documentary-profile').click();
   await l('documentary-profile-result').getByText(/Статус МСП — Подтверждение владельца/).waitFor();
   assert.equal(await l('documentary-profile-result').locator('p').count(),8);
   await page.getByText('Комплектность заявки и документы компании',{exact:true}).click();
   await l('run-id').fill('fixture');await l('documentary-signatory').selectOption('DIRECTOR');
   await l('documentary-goods').selectOption('NO');await l('read-documentary-run').click();
   await l('documentary-run-result').getByText(/Готовность заявки и актуальная редакция/).waitFor();
   assert.equal(await l('documentary-run-result').locator('p').count(),10);
   await l('run-id').fill('other');assert.equal(await l('documentary-run-result').innerText(),'');
   await l('run-id').fill('fixture');status='ARCHIVED_NOTIFICATION_NOT_APPLICATION';
   await l('read-documentary-run').click();await l('documentary-run-result').getByText(/извещение без подачи/).waitFor();
   assert.equal(called,2);
   await l('logout').click();await page.waitForFunction(()=>document.getElementById('run-id').value==='');
   assert.equal(await l('documentary-run-result').innerText(),'');
   assert.equal(await l('documentary-profile-result').innerText(),'');
   assert.deepEqual(errors,[]);
   await context.close();console.log('SAAS_DOCUMENTARY_UI_PASS',width);
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
