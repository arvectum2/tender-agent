'use strict';
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const {randomUUID} = require('node:crypto');
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
  if(method==='POST'){assert.equal(route.split('?')[1],'confirm_user_supplied=true');assert.equal(opts.body.name,'spec.docx');attachmentRecord={evidence_id:'file-a',case_id:'commercial-a',attempt_id:'capture-a',candidate_id:candidateID,source_url:candidate.source_url,origin:'USER_SUPPLIED_UNATTESTED',stored_bytes_reverified:true,platform_original_verified:false,inspection:{sha256:'doc-digest',text_preview:[{part:'word/document.xml',paragraph_index:1,text:'Поставка ТЗ'}]}};return reply(attachmentRecord,201)}
  assert(attachmentRecord);if(route.includes('/requirements')){
   if(method==='POST'){const req=JSON.parse(opts.body);assert.equal(req.fragment_key,fragmentKey);assert.equal(req.profile_fact_id,'profile-a');assert.equal(req.expected_revision,0);assert.equal(req.reference_fact_id,'reference-a');requirementReview={fragment_key:fragmentKey,revision:1,qualification_verified:false,assessment:req.assessment,rationale:req.rationale};return reply(requirementReview,201)}
   if(route.endsWith('/requirements/'+fragmentKey))return reply({qualification_verified:false,items:[requirementReview]});
   return reply({customer_id:fixture.a.customer_id,case_id:'commercial-a',attempt_id:'capture-a',candidate_id:candidateID,qualification_verified:false,profile:{fact_id:'profile-a',state:'ACTIVE'},reference_list:{fact_id:'reference-a',selectable:true},document_options:[],summary:{unreviewed:requirementReview?0:1},items:[{fragment_key:fragmentKey,fragment:{text:'Требования поставки'},revision:requirementReview?1:0,review:requirementReview}]});
  }
  if(route.endsWith('/text-evidence'))return reply({...attachmentRecord,text_projection:{source_sha256:'doc-digest',status:'PARTIAL_PREVIEW',requirements_verified:false,requirement_candidates:[{fragment_id:1}],fragments:[{text:'Поставка ТЗ'}]},supplier_profile_context:{profile_state:'MISSING'}});return reply({...attachmentRecord,...(route.includes('?')?{comparison:{previous_attempt_id:'capture-old',supplied_bytes_changed:true}}:{})});
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
 if(route.startsWith('/api/saas/company-portfolio/cases/commercial-a')){assert.equal(key,'a');if(route.endsWith('/decisions?limit=50'))return reply({items:[],has_more:false});assert.equal(route,'/api/saas/company-portfolio/cases/commercial-a');return reply(commercialItem);}
 if(route.startsWith('/api/saas/company-portfolio/cases?'))return reply({customer_id:mismatch?'foreign':fixture[key].customer_id,items:[item(key),...(key==='a'&&savedCommercial?[commercialItem]:[])],has_more:false});
 if(route==='/api/saas/company-portfolio/search-context')return reply({customer_id:fixture[key].customer_id,profile_state:'ACTIVE',profile_version:1});
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
const ctx=vm.createContext({document:{getElementById:get,createElement:tag=>new Element(tag),querySelectorAll:s=>s.startsWith('button')?controls:fields},fetch,crypto:{randomUUID},console});
vm.runInContext(script,ctx);
const click=async id=>{assert(get(id).events.click,'no click '+id);await get(id).events.click()};
const change=id=>get(id).events.change();
async function selectAccount(key){get('saved-token').value='fixture-'+key;await click('use-token');await click('company-load');}
async function openCase(key){get('company-case').value='case-'+key;change('company-case');await click('company-open');}
async function main(){
 await selectAccount('a');assert.match(get('company-identity').textContent,/Компания A/);
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
 await click('company-attachment-read');assert.match(get('company-attachment-result').textContent,/stored_bytes_reverified/);await click('company-attachment-text');assert.match(get('company-attachment-result').textContent,/requirement_candidates/);await click('company-requirement-load');get('company-requirement-fragment').value=fragmentKey;change('company-requirement-fragment');assert.match(get('company-requirement-source').textContent,/Требования поставки/);get('company-requirement-assessment').value='HUMAN_SUPPORT_RECORDED';get('company-requirement-reference').checked=true;get('company-requirement-rationale').value='Fixture review';await click('company-requirement-save');assert.equal(requirementReview.revision,1);get('company-requirement-fragment').value=fragmentKey;change('company-requirement-fragment');await click('company-requirement-history');assert.match(get('company-requirement-result').textContent,/Fixture review/);
 get('company-capture-previous').value='capture-old';change('company-capture-previous');await click('company-capture-recheck');assert.match(get('company-capture-result').textContent,/html_changed/);get('company-attachment-candidate').value=candidateID;change('company-attachment-candidate');await click('company-attachment-read');assert.match(get('company-attachment-result').textContent,/supplied_bytes_changed/);
 projectionEnabled=false;attachmentEnabled=false;captureEnabled=false;await click('company-capture-refresh');assert.equal(get('company-capture-start').disabled,true);assert.match(get('company-capture-state').textContent,/отключено сервером/);
 get('company-capture-attempt').value='capture-a';change('company-capture-attempt');await click('company-capture-recheck');assert.equal(get('company-capture-result').hidden,false);assert.equal(get('company-attachment-save').disabled,true);get('company-attachment-candidate').value=candidateID;change('company-attachment-candidate');assert.equal(get('company-attachment-read').disabled,false);assert.equal(get('company-attachment-text').disabled,true);assert.equal(get('company-requirement-load').disabled,true);assert.equal(get('company-requirement-panel').hidden,true);
 captureMismatch=true;await click('company-capture-refresh');assert.equal(vm.runInContext('token',ctx),'');assert.equal(get('company-capture-result').textContent,'');assert.equal(get('company-attachment-result').textContent,'');captureMismatch=false;await selectAccount('a');

 assert.equal(get('company-save-panel').hidden,false);await openCase('a');
 assert.equal(get('company-decision-panel').hidden,false);assert.equal(get('company-evidence-panel').hidden,false);
 get('company-evidence').value='binding-a';change('company-evidence');await click('company-read-evidence');
 assert.match(get('company-evidence-state').textContent,/Актуальный правовой статус не подтверждён/);
 get('company-rationale').value='Решение A';await click('company-decide');assert.equal(history.a.length,0);
 get('company-confirm').checked=true;lostResponse=true;await click('company-decide');assert.equal(history.a.length,1);assert.equal(get('company-confirm').checked,false);
 get('company-confirm').checked=true;await click('company-decide');assert.equal(history.a.length,1);assert.match(get('company-history').textContent,/Решение A/);
 const writes=calls.filter(c=>c.method==='POST'&&c.route.endsWith('/decisions'));assert.equal(writes.length,2);assert.equal(writes[0].body.idempotency_key,writes[1].body.idempotency_key);
 history.a.unshift({revision:2,action:'NO_GO',rationale:'other client',decided_at:'2026-11-15T01:00:00Z'});
 get('company-rationale').value='Устаревшее решение';get('company-confirm').checked=true;await click('company-decide');assert.equal(history.a.length,2);assert.equal(get('company-detail').hidden,true);assert.match(get('result').textContent,/Откройте карточку заново/);
 get('keywords').value='privately entered A';get('reference-state').textContent='private A';get('run-id').value='private-run-a';
 await selectAccount('b');assert.match(get('company-identity').textContent,/Компания B/);assert.equal(get('keywords').value,'');assert.equal(get('run-id').value,'');assert.equal(get('reference-state').textContent,'Список пока не загружен');assert.equal(get('company-history').textContent,'');assert.equal(get('company-capture-result').textContent,'');assert.equal(get('company-capture-attempt').children.length,1);assert.equal(get('company-evidence-result').textContent,'');assert.equal(get('company-search-receipts').textContent,'');assert.equal(get('company-search-candidate').children.length,1);
 await openCase('b');assert.equal(get('company-decision-panel').hidden,true);assert.equal(get('company-evidence-panel').hidden,true);assert.equal(get('company-save-panel').hidden,true);assert(!get('company-case').children.some(c=>c.value==='case-a'));
 mismatch=true;await click('company-load');assert.match(get('result').textContent,/другой компании/);assert.equal(get('company-detail').hidden,true);assert.equal(get('company-case').children.length,1);assert.equal(vm.runInContext('token',ctx),'');
 mismatch=false;let release;delayed=new Promise(r=>{release=r});get('saved-token').value='fixture-a';const first=click('use-token');get('saved-token').value='fixture-b';await click('use-token');release();await first;delayed=null;assert.equal(vm.runInContext('token',ctx),'fixture-a');
 console.log('Company cabinet JS flow PASS: bounded discovery, partial coverage, candidate acceptance, role/identity, evidence, explicit decision, uncertain retry, stale conflict, session clearing, request serialization.');
}
main().catch(error=>{console.error(error);process.exitCode=1});
