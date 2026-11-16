'use strict';
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const {randomUUID,webcrypto,createHash} = require('node:crypto');
const fileBytes=Buffer.from('%PDF-1.4\nfixture\n%%EOF'), fileSha=createHash('sha256').update(fileBytes).digest('hex');
let downloaded=0, artifact=null, corruptDownload=false, readyMode='blocked', bound=null;
const readyEvent={event_id:'ready-commercial',case_id:'commercial-a',revision:1,stage:'READY',origin:'HUMAN_ATTESTATION',readiness_stale:false,external_fact_verified:false,external_submission_allowed:false};
const html = execFileSync(process.env.PYTHON || 'python3', ['-c', 'from src.modules.saas_foundation.ui import render_saas_html; print(render_saas_html())'], {encoding:'utf8'});
const script = html.split('<script>')[1].split('</script>')[0];
class Element {
 constructor(tag='div'){this.tagName=tag.toUpperCase();this.children=[];this.events={};this.value='';this.defaultValue='';this.defaultChecked=false;this.checked=false;this.disabled=false;this.hidden=false;this.dataset={};this.style={};this.files=[];this.type='';this.text='';}
 set textContent(value){this.text=String(value);this.children=[];}
 get textContent(){return this.text;}
 set selectedIndex(value){this.value=this.children[value]?.value||'';}
 append(...items){this.children.push(...items);}
 replaceChildren(...items){this.children=[...items];this.value='';this.text='';}
 addEventListener(name,handler){this.events[name]=handler;}
 click(){assert.equal(this.tagName,"A");downloaded++;}
}
const ids=new Map();
for(const match of html.matchAll(/<([a-z][a-z0-9-]*)\b([^>]*?)\bid="([^"]+)"([^>]*)>/gi)){
 const [,tag,before,id,after]=match;const element=new Element(tag), attrs=before+after;
 element.type=attrs.match(/\btype="([^"]+)"/)?.[1]||'';
 element.defaultValue=attrs.match(/\bvalue="([^"]+)"/)?.[1]||'';element.value=element.defaultValue;
 element.disabled=/\bdisabled\b/.test(attrs);element.hidden=/\bhidden\b/.test(attrs);ids.set(id,element);
}
const get=id=>{assert(ids.has(id),'missing element '+id);return ids.get(id)};
const controls=[...ids.values()].filter(e=>['BUTTON','INPUT','SELECT','TEXTAREA'].includes(e.tagName));
const fields=controls.filter(e=>e.tagName!=='BUTTON');
const calls=[], history={a:[],b:[]};
const fixture={a:{customer_id:'customer-a',tenant_id:'tenant-a',member_id:'a',company_name:'Компания A',role:'owner',legal_accepted:true},b:{customer_id:'customer-b',tenant_id:'tenant-b',member_id:'b',company_name:'Компания B',role:'viewer',legal_accepted:true}};
const reply=(value,status=200)=>({ok:status>=200&&status<300,status,json:async()=>value});
let lostResponse=false, mismatch=false, delayed=null;
let lifecycleEnabled=true, lifecycleLost=false, lifecycleMismatch=false;
const lifecycleRows={a:[],b:[]};
const priceRows=[];let priceLost=false,priceMismatch=false,priceDisabled=false;
const priceInputs={external_direct_rub:'60000',own_labor_rub:'20000',cash_overhead_rub:'10000',reserve_rub:'5000',fixed_platform_fees_rub:'2000',guarantee_financing_cost_rub:'3000',revenue_tax_percent:'6',variable_platform_fee_percent:'4',minimum_profit_rub:'5000',target_profit_rub:'20000',reference_ceiling_rub:'120000',manual_bid_prices_rub:['120000'],assumption_note:'Private scenario A',accept_hypothetical_assumptions_only:true};
const priceResult={schema:'company_price_scenario_v1',currency:'RUB',cash_fixed_and_reserved_rub:'80000.00',own_labor_rub:'20000.00',full_economic_cost_before_revenue_rates_rub:'100000.00',revenue_retention_rate:'0.90',thresholds_rounded_up_to_kopecks:true,profits_rounded_down_to_kopecks:true,reference_ceiling_user_supplied:true,assumptions_independently_verified:false,tax_model_verified:false,market_comparables_used:false,probability_of_winning_estimated:false,is_procurement_bid_recommendation:false,commercial_owner_go:false,external_submission_allowed:false,scenarios:['CASH_BREAK_EVEN','FULL_BREAK_EVEN','STRATEGIC_MINIMUM_PROFIT','COMMERCIAL_TARGET_PROFIT','MANUAL_PRICE'].map((kind,i)=>({kind,price_rub:['88888.89','111111.12','116666.67','133333.34','120000.00'][i],cash_surplus_rub:'28000.00',economic_profit_rub:'8000.00',economic_margin_percent:'6.6666',cash_break_even_met:true,full_break_even_met:i>0,minimum_profit_met:i>1,target_profit_met:i===3,within_user_reference_ceiling:i!==3}))};

let discoveryRun=null, savedCandidate=null, savedCommercial=null;
let captureEnabled=true, captureReceipt=null, captureMismatch=false;
let attachmentEnabled=true, attachmentRecord=null, projectionEnabled=true, requirementReview=null;
const fragmentKey="a".repeat(64);
const candidateID='e'.repeat(64), candidate={candidate_id:candidateID,source_url:'https://workspace.ru/docs/spec.docx',format_hint:'docx',display_label:'ТЗ'};
const priorCapture={attempt_id:'capture-old',case_id:'commercial-a',source_url:'https://workspace.ru/tenders/fixture-1234567/',capture_day:'2026-11-15',outcome:'CAPTURED'};
let scheduleState={enabled:false,execution_enabled:true,revision:0,hour_moscow:8,sources:{},profile_current:false};
const commercialURL="https://workspace.ru/tenders/fixture-1234567/";
const commercialItem={case_id:"commercial-a",registry_number:null,external_id:"1234567",source_platform:"workspace",source_kind:"commercial_reference",source_url:commercialURL,revision:0,decision:null,source_verified:false};
const item=key=>({case_id:'case-'+key,registry_number:'0123456789012345678',revision:history[key].length,decision:history[key][0]||null,source_verified:false,external_submission_allowed:false});
async function fetch(route,opts){
 const key=opts.headers.Authorization?.slice(-1), method=opts.method;
 calls.push({route,method,key,body:typeof opts.body==="string"?JSON.parse(opts.body):null});
 assert.equal(opts.credentials,'omit');assert.equal(opts.redirect,'error');
 if(!fixture[key])return reply({detail:'invalid'},401);
 if(route==='/api/saas/me'){if(delayed)await delayed;return reply(fixture[key]);}
 if(route==='/api/saas/company-portfolio/discovery/schedule'){
  if(method==='PUT'){
   assert.equal(key,'a');const body=JSON.parse(opts.body);assert.equal(body.expected_revision,scheduleState.revision);
   if(body.enabled){assert.equal(body.confirm_unattended_public_search,true);assert.equal(body.expected_profile_version,1);assert.equal(body.hour_moscow,9);assert.deepEqual(body.commercial_indexes,['workspace_rss']);}
   scheduleState={...scheduleState,enabled:body.enabled,revision:scheduleState.revision+1,hour_moscow:body.hour_moscow||8,sources:body.enabled?{include_eis:body.include_eis,commercial_indexes:body.commercial_indexes}:{},profile_current:body.enabled};
  }
  return reply({...scheduleState,customer_id:fixture[key].customer_id});
 }
 if(route==='/api/saas/company-portfolio/discovery/latest')return reply({enabled:true,commercial_indexes:["workspace_rss"],run:key==='a'?discoveryRun:null});
 if(route==='/api/saas/company-portfolio/discovery/runs'&&method==='POST'){
  assert.equal(key,'a');assert.deepEqual(JSON.parse(opts.body),{expected_profile_version:1,commercial_indexes:["workspace_rss"]});
  discoveryRun={run_id:'run-discovery-a',customer_id:'customer-a',run_day:'2026-11-16',status:'PENDING',plan:{profile_version:1,steps:[{query:'A'},{query:'B'}]},completed_steps:0,step_receipts:[],candidates:[],discovery_incomplete:true};
  return reply(discoveryRun,201);
 }
 if(route==='/api/saas/company-portfolio/discovery/runs/run-discovery-a/step'){
  assert.equal(key,'a');const index=JSON.parse(opts.body).expected_step;assert.equal(index,discoveryRun.completed_steps);
  const candidate={registry_number:'0123456789012345678',title:'Кандидат A'};
  discoveryRun={...discoveryRun,status:index===1?'PARTIAL':'IN_PROGRESS',completed_steps:index+1,candidates:index?[candidate,{registry_number:null,source_platform:"workspace",external_id:"1234567",source_url:commercialURL,title:"Commercial A"}]:[candidate],step_receipts:[...discoveryRun.step_receipts,{query:index?'B':'A',outcome:index?'source_unavailable':'success_with_results',coverage_complete:false,candidates:index?[]:[candidate]}]};return reply(discoveryRun);
 }
 if(route==='/api/saas/company-portfolio/cases'&&method==='POST'){
  assert.equal(key,'a');savedCandidate=JSON.parse(opts.body).registry_number;return reply(item(key),201);
 }
 if(route==='/api/saas/company-portfolio/commercial-cases'&&method==='POST'){assert.equal(key,'a');savedCommercial=JSON.parse(opts.body).source_url;return reply(commercialItem,201);}
 if(route.includes('/commercial-captures/capture-a/attachments')){
  assert.equal(key,'a');
  if(route.endsWith('/attachments'))return reply({customer_id:fixture.a.customer_id,case_id:'commercial-a',attempt_id:'capture-a',items:attachmentRecord?[attachmentRecord]:[]});
  if(method==='POST'&&!route.includes('/requirements')){assert.equal(route.split('?')[1],'confirm_user_supplied=true');assert.equal(opts.body.name,'spec.docx');attachmentRecord={evidence_id:'file-a',case_id:'commercial-a',attempt_id:'capture-a',candidate_id:candidateID,source_url:candidate.source_url,origin:'USER_SUPPLIED_UNATTESTED',stored_bytes_reverified:true,platform_original_verified:false,inspection:{sha256:'doc-digest',text_preview:[{part:'word/document.xml',paragraph_index:1,text:'Поставка ТЗ'}]}};return reply(attachmentRecord,201)}
  assert(attachmentRecord);if(route.includes('/requirements')){
   if(method==='POST'){const req=JSON.parse(opts.body);assert.equal(req.fragment_key,fragmentKey);assert.equal(req.profile_fact_id,'profile-a');assert.equal(req.expected_revision,0);assert.equal(req.reference_fact_id,'reference-a');requirementReview={fragment_key:fragmentKey,revision:1,qualification_verified:false,assessment:req.assessment,rationale:req.rationale};return reply(requirementReview,201)}
   if(route.endsWith('/requirements/'+fragmentKey))return reply({qualification_verified:false,items:[requirementReview]});
   return reply({customer_id:fixture.a.customer_id,case_id:'commercial-a',attempt_id:'capture-a',candidate_id:candidateID,qualification_verified:false,profile:{fact_id:'profile-a',state:'ACTIVE'},reference_list:{fact_id:'reference-a',selectable:true},document_options:[],summary:{unreviewed:requirementReview?0:1},items:[{fragment_key:fragmentKey,fragment:{text:'Требования поставки'},revision:requirementReview?1:0,review:requirementReview}]});
  }
  if(route.endsWith('/text-evidence'))return reply({...attachmentRecord,text_projection:{source_sha256:'doc-digest',status:'PARTIAL_PREVIEW',requirements_verified:false,requirement_candidates:[{fragment_id:1}],fragments:[{text:'Поставка ТЗ'}]},supplier_profile_context:{profile_state:'MISSING'}});return reply({...attachmentRecord,...(route.includes('?')?{comparison:{previous_attempt_id:'capture-old',supplied_bytes_changed:true}}:{})});
 }
 if(route.includes('/commercial-captures/capture-a/requirement-matrix?')){
  assert.equal(key,'a');const offset=route.includes('offset=3')?3:0;return reply({customer_id:fixture.a.customer_id,case_id:'commercial-a',attempt_id:'capture-a',offset,coverage_complete:false,qualification_verified:false,candidate_count:4,missing_copy_count:2,has_more:offset===0,page_summary:{unreviewed:1},documents:[]});
 }
 if(route.startsWith('/api/saas/company-portfolio/cases/commercial-a/commercial-captures')){
  assert.equal(key,'a');
  if(method==='POST'){
   assert.deepEqual(JSON.parse(opts.body),{confirm_public_capture:true});assert.equal(captureEnabled,true);
   captureReceipt={attempt_id:'capture-a',case_id:'commercial-a',source_url:commercialURL,capture_day:'2026-11-16',outcome:'CAPTURED',receipt:{title:'<img src=x onerror=evil()>',html_sha256:'fixture'}};return reply(captureReceipt,201);
  }
  if(route.endsWith('?limit=20'))return reply({customer_id:captureMismatch?'wrong':fixture.a.customer_id,case_id:'commercial-a',items:captureReceipt?[captureReceipt,priorCapture]:[priorCapture],has_more:false,capture_enabled:captureEnabled});
  assert(['','?previous_attempt_id=capture-old'].includes(route.split('/commercial-captures/capture-a')[1]));return reply({...captureReceipt,original_reverified:true,attachment_intake_enabled:attachmentEnabled,text_projection_enabled:projectionEnabled,requirement_review_enabled:projectionEnabled,attachment_inventory:{candidates:[candidate],coverage_complete:false},...(route.includes('?')?{comparison:{previous_attempt_id:'capture-old',html_changed:true}}:{})});
 }
 if(route==='/api/saas/company-portfolio/cases/commercial-a/lifecycle')return reply({customer_id:fixture.a.customer_id,case_id:'commercial-a',decision_revision:1,decision_action:'GO',revision:1,latest:readyEvent,external_submission_allowed:false});
 if(route==='/api/saas/company-portfolio/cases/commercial-a/readiness-evidence'){
  const sha=(readyMode==='stale'?'b':'a').repeat(64), issues=readyMode==='blocked'?['UNREVIEWED_FRAGMENT']:readyMode==='stale'?['STALE_REVIEW']:[];
  if(method==='POST'){assert.equal(key,'a');assert.deepEqual(JSON.parse(opts.body),{ready_event_id:readyEvent.event_id,projection_sha256:sha,acknowledge_partial_coverage:true});assert.equal(readyMode,'resolved');bound=sha;}
  return reply({ready_event_id:readyEvent.event_id,projection_sha256:sha,projection:{schema:'commercial_readiness_partial_v1',customer_id:fixture.a.customer_id,case_id:'commercial-a',card_sha256:'c'.repeat(64),issues,documents:[],partial_review_resolved:!issues.length,coverage_complete:false,qualification_verified:false,platform_original_verified:false,external_submission_allowed:false},binding_id:bound?'binding-fixture':null,bound_projection_sha256:bound,binding_current:bound===sha&&!issues.length,qualification_verified:false,external_submission_allowed:false});
 }
 if(route.startsWith('/api/saas/company-portfolio/cases/commercial-a')){assert.equal(key,'a');if(route.endsWith('/decisions?limit=50'))return reply({items:[],has_more:false});assert.equal(route,'/api/saas/company-portfolio/cases/commercial-a');return reply(commercialItem);}
 if(route.startsWith('/api/saas/company-portfolio/manager-inbox?')){
  const view=route.match(/view=([^&]+)/)[1],offset=Number(route.match(/offset=(\d+)/)[1]);
  const current=item(key),state=current.decision?.action==='GO'?'go':'undecided';
  const items=view==='attention'||view==='undecided'||view==='go'?((view==='go'&&state!=='go')||(view!=='go'&&state==='go')?[]:[{...current,inbox_state:state}]):[];
  return reply({customer_id:mismatch?'foreign':fixture[key].customer_id,view,offset,scope:'SAVED_COMPANY_REFERENCES_AND_HUMAN_DECISIONS',external_submission_allowed:false,as_of:'2026-11-16T10:00:00Z',summary:{all:1,attention:state==='undecided'?1:0,undecided:state==='undecided'?1:0,deferred_due:0,deferred_future:0,go:state==='go'?1:0,no_go:0},items,has_more:false});
 }
 if(route.startsWith('/api/saas/company-portfolio/cases?'))return reply({customer_id:mismatch?'foreign':fixture[key].customer_id,items:[item(key),...(key==='a'&&savedCommercial?[commercialItem]:[])],has_more:false});
 if(route==='/api/saas/company-portfolio/search-context')return reply({customer_id:fixture[key].customer_id,profile_state:'ACTIVE',profile_version:1});
 if(route==='/api/saas/company-portfolio/lifecycle-metrics'){
  if(!lifecycleEnabled)return reply({detail:'disabled'},404);
  const stage=lifecycleRows[key][0]?.stage,submitted=['SUBMITTED','WON','LOST','REJECTED','WITHDRAWN','CANCELLED'].includes(stage)?1:0,go=history[key].some(x=>x.action==='GO')?1:0,win=stage==='WON'?1:0,decided=['WON','LOST','REJECTED'].includes(stage)?1:0;
  return reply({customer_id:fixture[key].customer_id,scope:'ALL_TIME_SAVED_CASES_HUMAN_ATTESTATIONS',external_facts_verified:false,market_coverage_complete:false,contract_revenue_verified:false,saved_cases:1,ever_go_cases:go,recorded_submissions:submitted,go_to_submission:{numerator:submitted,denominator:go,rate:go?submitted/go:null},win_rate:{numerator:win,denominator:decided,rate:decided?win/decided:null},stage_counts:{SUBMITTED:stage==='SUBMITTED'?1:0,WITHDRAWN:0,CANCELLED:0},as_of:'2026-11-16T10:00:00Z'});
 }
 if(route===('/api/saas/company-portfolio/cases/case-'+key+'/lifecycle')||route===('/api/saas/company-portfolio/cases/case-'+key+'/lifecycle/history?limit=50')){
  if(!lifecycleEnabled)return reply({detail:'disabled'},404);
  const rows=lifecycleRows[key],current=item(key),scope={customer_id:lifecycleMismatch?'foreign':fixture[key].customer_id,case_id:current.case_id,external_submission_allowed:false};
  if(method==='POST'){
   assert.equal(key,'a');const body=JSON.parse(opts.body),prior=rows.find(x=>x.attestation.idempotency_key===body.idempotency_key);if(prior)return reply(prior,201);
   assert.equal(body.expected_revision,rows.length);assert.equal(body.expected_decision_revision,current.revision);
   const record={event_id:'lifecycle-'+rows.length,case_id:current.case_id,revision:rows.length+1,stage:body.stage,attestation:body,origin:'HUMAN_ATTESTATION',readiness_stale:false,external_fact_verified:false,external_submission_allowed:false};rows.unshift(record);
   if(lifecycleLost){lifecycleLost=false;throw Error('network interrupted after lifecycle write')}return reply(record,201);
  }
  if(route.includes('/history?'))return reply({...scope,items:rows,has_more:false});
  return reply({...scope,revision:rows.length,decision_revision:current.revision,decision_action:current.decision?.action??null,latest:rows[0]??null});
 }
 if(route.includes('/lifecycle/lifecycle-1/artifact')){
  assert.equal(key,'a');if(method==='POST'){assert.match(route,/format_hint=pdf&confirm_user_supplied=true/);assert.equal(opts.body.name,'receipt.pdf');artifact={customer_id:fixture.a.customer_id,case_id:'case-a',event_id:'lifecycle-1',event_revision:2,event_stage:'SUBMITTED',artifact_kind:'SUBMISSION_RECEIPT',artifact_id:'artifact-a',format_hint:'pdf',inspection:{format_hint:'pdf',sha256:fileSha,size_bytes:fileBytes.length},origin:'USER_SUPPLIED_UNATTESTED',stored_bytes_reverified:true,platform_original_verified:false,external_fact_verified:false,external_submission_allowed:false};return reply(artifact,201)}
  if(route.endsWith('/download'))return new Response(corruptDownload?Buffer.alloc(fileBytes.length,1):fileBytes,{headers:{'x-artifact-sha256':fileSha}});
  return artifact?reply(artifact):reply({detail:'missing'},404);
 }
 if(route.includes('/price-scenarios')){
  assert.equal(key,'a');if(priceDisabled)return reply({detail:'disabled'},404);
  const scope={customer_id:priceMismatch?'foreign':fixture.a.customer_id,case_id:'case-a'};
  if(route.endsWith('/preview')){assert.deepEqual(JSON.parse(opts.body),priceInputs);return reply({...scope,inputs_stored:false,result:priceResult})}
  if(method==='POST'){const body=JSON.parse(opts.body);assert.deepEqual(body.scenario,priceInputs);const prior=priceRows.find(x=>x.key===body.idempotency_key);if(prior)return reply(prior.row,201);if(body.expected_revision!==priceRows.length)return reply({detail:'changed'},409);const row={...scope,scenario_id:'price-'+(priceRows.length+1),revision:priceRows.length+1,member_id:'a',created_at:'2026-11-16T12:00:00Z',origin:'EXPLICIT_USER_ASSUMPTIONS',external_submission_allowed:false,inputs:body.scenario,result:priceResult};priceRows.unshift({key:body.idempotency_key,row});if(priceLost){priceLost=false;throw Error('response lost')}return reply(row,201)}
  return reply({...scope,items:priceRows.map(x=>x.row),has_more:false,external_submission_allowed:false})
 }
 if(route.startsWith('/api/saas/company-portfolio/cases/case-'+key)){
  if(route.endsWith('/decisions?limit=50'))return reply({items:history[key],has_more:false});
  if(route.endsWith('/decisions')&&method==='POST'){
   const body=JSON.parse(opts.body), old=history[key].find(x=>x.key===body.idempotency_key);
   if(old)return reply(old);
   if(body.expected_revision!==history[key].length)return reply({detail:'stale'},409);
   const saved={revision:history[key].length+1,action:body.action,rationale:body.rationale,key:body.idempotency_key,decided_at:'2026-11-15T00:00:00Z'};
   history[key].unshift(saved);
   if(lostResponse){lostResponse=false;throw Error('network interrupted after write');}
   return reply(saved);
  }
  if(route.endsWith('/evidence?limit=50'))return reply({items:[{case_id:'case-'+key,binding_id:'binding-'+key,run_id:'run-'+key,profile_version:1,profile_state:'ACTIVE'}],has_more:false});
  if(route.endsWith('/evidence/binding-'+key))return reply({case_id:'case-'+key,binding_id:'binding-'+key,archived_source_snapshot_verified:true,profile_state:'ACTIVE',report_status:'REPORT_UNAVAILABLE'});
  return reply(item(key));
 }
 throw Error('Unexpected route '+route);
}
const ctx=vm.createContext({document:{getElementById:get,createElement:tag=>new Element(tag),querySelectorAll:s=>s.startsWith('button')?controls:fields},fetch,crypto:{randomUUID,subtle:webcrypto.subtle},Blob,URL,setTimeout,console});
vm.runInContext(script,ctx);
const click=async id=>{assert(get(id).events.click,'no click '+id);await get(id).events.click()};
const change=id=>get(id).events.change();
async function selectAccount(key){get('saved-token').value='fixture-'+key;await click('use-token');await click('company-load');}
async function openCase(key){get('company-case').value='case-'+key;change('company-case');await click('company-open');}
async function main(){
 await selectAccount('a');assert.match(get('company-identity').textContent,/Компания A/);
 await click('company-inbox-load');assert.match(get('company-inbox-summary').textContent,/Требуют внимания: 1/);assert.equal(get('company-case').children[1].value,'case-a');
 get('company-inbox-filter').value='go';await click('company-inbox-load');assert.equal(get('company-case').children.length,1);
 mismatch=true;await click('company-inbox-load');assert.equal(vm.runInContext('token',ctx),'');assert.equal(get('company-inbox-summary').textContent,'');mismatch=false;await selectAccount('a');

 await click('company-search-refresh');assert.equal(get('company-search-start').disabled,false);get("company-search-index").value="workspace_rss";
 await click('company-schedule-refresh');get('company-schedule-hour').value='9';await click('company-schedule-enable');assert.equal(scheduleState.revision,0);
 get('company-schedule-confirm').checked=true;await click('company-schedule-enable');assert.equal(scheduleState.enabled,true);assert.match(get('company-schedule-state').textContent,/Разрешено владельцем/);
 await click('company-schedule-disable');assert.equal(scheduleState.enabled,false);assert.equal(scheduleState.revision,2);
 await click('company-search-start');
 assert.match(get('company-search-state').textContent,/Ожидает выполнения/);await click('company-search-run');
 assert.match(get('company-search-state').textContent,/Выдача неполная/);assert.match(get('company-search-receipts').textContent,/source_unavailable/);
 assert.equal(calls.filter(c=>c.route.endsWith('/step')).length,2);
 get('company-search-candidate').value='0123456789012345678';change('company-search-candidate');await click('company-search-accept');
 assert.equal(savedCandidate,'0123456789012345678');assert.match(get('company-search-state').textContent,/Выдача неполная/);
 get('company-search-candidate').value='workspace:1234567';change('company-search-candidate');await click('company-search-accept');assert.equal(savedCommercial,commercialURL);
 get('company-case').value='commercial-a';change('company-case');await click('company-open');assert.match(get('company-case-url').textContent,/workspace.ru/);assert.equal(get('company-evidence-panel').hidden,true);
 assert.equal(get('company-commercial-evidence-panel').hidden,false);assert.equal(get('company-capture-start').disabled,true);
 await click('company-capture-start');assert.equal(captureReceipt,null);
 get('company-capture-confirm').checked=true;change('company-capture-confirm');assert.equal(get('company-capture-start').disabled,false);await click('company-capture-start');assert.equal(captureReceipt.attempt_id,'capture-a');assert.equal(get('company-capture-confirm').checked,false);
 get('company-capture-attempt').value='capture-a';change('company-capture-attempt');await click('company-capture-recheck');assert.match(get('company-capture-state').textContent,/повторно проверен/);assert.match(get('company-capture-result').textContent,/<img src=x onerror=evil\(\)>/);
 assert.equal(get('company-attachment-panel').hidden,false);get('company-attachment-candidate').value=candidateID;change('company-attachment-candidate');get('company-attachment-file').files=[{name:'spec.docx',size:123}];change('company-attachment-file');await click('company-attachment-save');assert.equal(attachmentRecord,null);get('company-attachment-confirm').checked=true;change('company-attachment-confirm');assert.equal(get('company-attachment-save').disabled,false);await click('company-attachment-save');assert.equal(attachmentRecord.origin,'USER_SUPPLIED_UNATTESTED');assert.match(get('company-attachment-result').textContent,/Поставка ТЗ/);
 await click('company-attachment-read');assert.match(get('company-attachment-result').textContent,/stored_bytes_reverified/);await click('company-attachment-text');assert.match(get('company-attachment-result').textContent,/requirement_candidates/);await click('company-case-matrix');assert.match(get('company-case-matrix-result').textContent,/missing_copy_count/);await click('company-case-matrix-next');assert.match(get('company-case-matrix-result').textContent,/\"offset\": 3/);await click('company-case-matrix-prev');await click('company-requirement-load');get('company-requirement-fragment').value=fragmentKey;change('company-requirement-fragment');assert.match(get('company-requirement-source').textContent,/Требования поставки/);get('company-requirement-assessment').value='HUMAN_SUPPORT_RECORDED';get('company-requirement-reference').checked=true;get('company-requirement-rationale').value='Fixture review';await click('company-requirement-save');assert.equal(requirementReview.revision,1);get('company-requirement-fragment').value=fragmentKey;change('company-requirement-fragment');await click('company-requirement-history');assert.match(get('company-requirement-result').textContent,/Fixture review/);
 get('company-capture-previous').value='capture-old';change('company-capture-previous');await click('company-capture-recheck');assert.match(get('company-capture-result').textContent,/html_changed/);get('company-attachment-candidate').value=candidateID;change('company-attachment-candidate');await click('company-attachment-read');assert.match(get('company-attachment-result').textContent,/supplied_bytes_changed/);
 projectionEnabled=false;attachmentEnabled=false;captureEnabled=false;await click('company-capture-refresh');assert.equal(get('company-capture-start').disabled,true);assert.match(get('company-capture-state').textContent,/отключено сервером/);
 get('company-capture-attempt').value='capture-a';change('company-capture-attempt');await click('company-capture-recheck');assert.equal(get('company-capture-result').hidden,false);assert.equal(get('company-attachment-save').disabled,true);get('company-attachment-candidate').value=candidateID;change('company-attachment-candidate');assert.equal(get('company-attachment-read').disabled,false);assert.equal(get('company-attachment-text').disabled,true);assert.equal(get('company-requirement-load').disabled,true);assert.equal(get('company-requirement-panel').hidden,true);
 commercialItem.revision=1;commercialItem.decision={revision:1,action:'GO',rationale:'fixture'};get('company-case').value='commercial-a';change('company-case');await click('company-open');await click('company-lifecycle-load');assert.equal(get('company-readiness-panel').hidden,false);
 await click('company-readiness-load');assert.match(get('company-readiness-state').textContent,/непроверенные/);assert.equal(get('company-readiness-bind').disabled,true);
 readyMode='resolved';await click('company-readiness-load');await click('company-readiness-bind');assert.equal(bound,null);get('company-readiness-confirm').checked=true;change('company-readiness-confirm');await click('company-readiness-bind');assert.match(get('company-readiness-state').textContent,/Снимок актуален/);
 readyMode='stale';await click('company-readiness-load');assert.match(get('company-readiness-state').textContent,/Снимок устарел/);assert.equal(get('company-readiness-bind').disabled,true);
 captureMismatch=true;await click('company-capture-refresh');assert.equal(vm.runInContext('token',ctx),'');assert.equal(get('company-capture-result').textContent,'');assert.equal(get('company-attachment-result').textContent,'');captureMismatch=false;await selectAccount('a');

 assert.equal(get('company-save-panel').hidden,false);await openCase('a');
 assert.equal(get('company-decision-panel').hidden,false);assert.equal(get('company-evidence-panel').hidden,false);
 get('company-evidence').value='binding-a';change('company-evidence');await click('company-read-evidence');
 assert.match(get('company-evidence-state').textContent,/Актуальный правовой статус не подтверждён/);
 get('company-rationale').value='Решение A';await click('company-decide');assert.equal(history.a.length,0);
 get('company-confirm').checked=true;lostResponse=true;await click('company-decide');assert.equal(history.a.length,1);assert.equal(get('company-confirm').checked,false);
 get('company-confirm').checked=true;await click('company-decide');assert.equal(history.a.length,1);assert.match(get('company-history').textContent,/Решение A/);
 const writes=calls.filter(c=>c.method==='POST'&&c.route.endsWith('/decisions'));assert.equal(writes.length,2);assert.equal(writes[0].body.idempotency_key,writes[1].body.idempotency_key);
 lifecycleEnabled=false;await click('company-lifecycle-load');assert.match(get('company-lifecycle-state').textContent,/отключён/);assert.equal(get('company-lifecycle-editor').hidden,true);
 lifecycleEnabled=true;await click('company-lifecycle-load');assert.equal(get('company-lifecycle-editor').hidden,false);assert(!get('company-lifecycle-stage').children.some(x=>x.value==='SUBMITTED'));
 get('company-lifecycle-stage').value='READY';change('company-lifecycle-stage');get('company-lifecycle-rationale').value='Готовность A';await click('company-lifecycle-save');assert.equal(lifecycleRows.a.length,0);
 get('company-lifecycle-confirm').checked=true;change('company-lifecycle-confirm');lifecycleLost=true;await click('company-lifecycle-save');assert.equal(lifecycleRows.a.length,1);assert.equal(get('company-lifecycle-confirm').checked,false);
 get('company-lifecycle-confirm').checked=true;change('company-lifecycle-confirm');await click('company-lifecycle-save');assert.equal(lifecycleRows.a.length,1);assert.match(get('company-lifecycle-state').textContent,/Готовность подтверждена/);
 const lifeWrites=calls.filter(c=>c.method==='POST'&&c.route.endsWith('/lifecycle'));assert.equal(lifeWrites.length,2);assert.equal(lifeWrites[0].body.idempotency_key,lifeWrites[1].body.idempotency_key);
 get('company-lifecycle-stage').value='SUBMITTED';change('company-lifecycle-stage');get('company-lifecycle-rationale').value='Подача A';get('company-lifecycle-confirm').checked=true;await click('company-lifecycle-save');assert.equal(lifecycleRows.a.length,1);
 get('company-lifecycle-ref').value='receipt A';get('company-lifecycle-date').value='2026-01-01T10:00';await click('company-lifecycle-save');assert.equal(lifecycleRows.a[0].stage,'SUBMITTED');
 get('company-lifecycle-stage').value='WON';change('company-lifecycle-stage');get('company-lifecycle-rationale').value='Победа A';get('company-lifecycle-ref').value='protocol A';get('company-lifecycle-date').value='2026-01-02T10:00';get('company-lifecycle-confirm').checked=true;await click('company-lifecycle-save');assert.equal(lifecycleRows.a[0].stage,'WON');
 await click('company-lifecycle-history');assert.match(get('company-lifecycle-history-result').textContent,/receipt A/);
 get('company-event-file-event').value='lifecycle-1';change('company-event-file-event');await click('company-event-file-load');assert.equal(get('company-event-file-editor').hidden,false);
 get('company-event-file-input').files=[{name:'receipt.pdf',size:fileBytes.length,arrayBuffer:async()=>fileBytes}];change('company-event-file-input');await click('company-event-file-save');assert.equal(artifact,null);
 get('company-event-file-confirm').checked=true;change('company-event-file-confirm');await click('company-event-file-save');assert.equal(artifact.inspection.sha256,fileSha);assert.match(get('company-event-file-state').textContent,/подлинность не подтверждена/);
 corruptDownload=true;await click('company-event-file-download');assert.equal(downloaded,0);assert.match(get('result').textContent,/Контрольная сумма/);corruptDownload=false;await click('company-event-file-download');assert.equal(downloaded,1);
await click('company-metrics-load');assert.match(get('company-metrics-result').textContent,/100.0%/);assert.match(get('company-metrics-result').textContent,/по сведениям сотрудников/);
 get('company-lifecycle-stage').value='LOST';change('company-lifecycle-stage');get('company-lifecycle-rationale').value='Коррекция A';get('company-lifecycle-ref').value='protocol corrected A';get('company-lifecycle-date').value='2026-01-03T10:00';get('company-lifecycle-confirm').checked=true;await click('company-lifecycle-save');assert.equal(lifecycleRows.a[0].attestation.correct_outcome,true);assert.equal(get('company-metrics-result').textContent,'');await click('company-metrics-load');assert.match(get('company-metrics-result').textContent,/0.0%/);
 assert.equal(get('company-price-panel').hidden,false);
 assert.equal(get('price-external_direct_rub').value,'');assert.equal(get('price-revenue_tax_percent').value,'');
 priceDisabled=true;await click('price-history');assert.equal(get('price-save').disabled,true);priceDisabled=false;await click('price-history');
 for(const [k,v] of Object.entries(priceInputs)){if(k.endsWith('_rub')&&k!=='manual_bid_prices_rub'||k.endsWith('_percent'))get('price-'+k).value=v}
 get('price-manual').value='120000';get('price-note').value=priceInputs.assumption_note;
 await click('price-preview');assert.equal(priceRows.length,0);assert.equal(get('price-results').children.length,0);
 get('price-confirm').checked=true;change('price-confirm');await click('price-preview');assert.equal(get('price-results').children[0].children.length,6);assert.equal(priceRows.length,0);assert.equal(get('price-save').disabled,true);
 get('price-save-confirm').checked=true;change('price-save-confirm');priceLost=true;await click('price-save');assert.equal(priceRows.length,1);get('price-save-confirm').checked=true;change('price-save-confirm');await click('price-save');assert.equal(priceRows.length,1);assert.match(get('price-status').textContent,/v1 сохранена/);
 const priceWrites=calls.filter(x=>x.method==='POST'&&x.route.endsWith('/price-scenarios'));assert.equal(priceWrites.length,2);assert.equal(priceWrites[0].body.idempotency_key,priceWrites[1].body.idempotency_key);
 get('price-version').value='price-1';change('price-version');await click('price-show-version');assert.match(get('price-version-detail').textContent,/Private scenario A/);
 await click('price-preview');get('price-own_labor_rub').value='999';change('price-own_labor_rub');assert.equal(get('price-results').children.length,0);assert.equal(get('price-save').disabled,true);get('price-own_labor_rub').value='20000';change('price-own_labor_rub');
 history.a.unshift({revision:2,action:'NO_GO',rationale:'other client',decided_at:'2026-11-15T01:00:00Z'});
 get('company-rationale').value='Устаревшее решение';get('company-confirm').checked=true;await click('company-decide');assert.equal(history.a.length,2);assert.equal(get('company-detail').hidden,true);assert.match(get('result').textContent,/Откройте карточку заново/);
 get('keywords').value='privately entered A';get('reference-state').textContent='private A';get('run-id').value='private-run-a';
 await selectAccount('b');assert.match(get('company-identity').textContent,/Компания B/);assert.equal(get('keywords').value,'');assert.equal(get('run-id').value,'');assert.equal(get('reference-state').textContent,'Список пока не загружен');assert.equal(get('company-history').textContent,'');assert.equal(get('company-event-file-result').textContent,'');assert.equal(get('company-readiness-result').textContent,'');assert.equal(get('company-capture-result').textContent,'');assert.equal(get('company-capture-attempt').children.length,1);assert.equal(get('company-evidence-result').textContent,'');assert.equal(get('company-search-receipts').textContent,'');assert.equal(get('company-search-candidate').children.length,1);
 assert.equal(get('price-note').value,'');assert.equal(get('price-version-detail').textContent,'');assert.equal(get('price-results').children.length,0);
 await openCase('b');assert.equal(get('company-price-panel').hidden,true);assert.equal(get('price-preview').disabled,true);await click('company-lifecycle-load');assert.equal(get('company-lifecycle-editor').hidden,true);assert.equal(get('company-lifecycle-current').textContent,'');await click('company-metrics-load');assert.match(get('company-metrics-result').textContent,/нет данных/);assert.equal(get('company-decision-panel').hidden,true);assert.equal(get('company-evidence-panel').hidden,true);assert.equal(get('company-save-panel').hidden,true);assert(!get('company-case').children.some(c=>c.value==='case-a'));
 lifecycleMismatch=true;await click('company-lifecycle-load');assert.equal(vm.runInContext('token',ctx),'');assert.equal(get('company-metrics-result').textContent,'');lifecycleMismatch=false;await selectAccount('b');
 mismatch=true;await click('company-load');assert.match(get('result').textContent,/другой компании/);assert.equal(get('company-detail').hidden,true);assert.equal(get('company-case').children.length,1);assert.equal(vm.runInContext('token',ctx),'');
 mismatch=false;let release;delayed=new Promise(r=>{release=r});get('saved-token').value='fixture-a';const first=click('use-token');get('saved-token').value='fixture-b';await click('use-token');release();await first;delayed=null;assert.equal(vm.runInContext('token',ctx),'fixture-a');
 await click('company-load');await openCase('a');priceMismatch=true;await click('price-history');assert.equal(vm.runInContext('token',ctx),'');assert.equal(get('price-note').value,'');assert.equal(get('price-version-detail').textContent,'');assert.match(get('result').textContent,/другой компании/);
 console.log('Company cabinet JS flow PASS: bounded discovery, partial coverage, candidate acceptance, role/identity, evidence, explicit decision, uncertain retry, stale conflict, session clearing, request serialization.');
}
main().catch(error=>{console.error(error);process.exitCode=1});
