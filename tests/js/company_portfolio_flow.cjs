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
const item=key=>({case_id:'case-'+key,registry_number:'0123456789012345678',revision:history[key].length,decision:history[key][0]||null,source_verified:false,external_submission_allowed:false});
async function fetch(route,opts){
 const key=opts.headers.Authorization?.slice(-1), method=opts.method;
 calls.push({route,method,key,body:opts.body?JSON.parse(opts.body):null});
 assert.equal(opts.credentials,'omit');assert.equal(opts.redirect,'error');
 if(!fixture[key])return reply({detail:'invalid'},401);
 if(route==='/api/saas/me'){if(delayed)await delayed;return reply(fixture[key]);}
 if(route.startsWith('/api/saas/company-portfolio/cases?'))return reply({customer_id:mismatch?'foreign':fixture[key].customer_id,items:[item(key)],has_more:false});
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
 await selectAccount('b');assert.match(get('company-identity').textContent,/Компания B/);assert.equal(get('keywords').value,'');assert.equal(get('run-id').value,'');assert.equal(get('reference-state').textContent,'Список пока не загружен');assert.equal(get('company-history').textContent,'');assert.equal(get('company-evidence-result').textContent,'');
 await openCase('b');assert.equal(get('company-decision-panel').hidden,true);assert.equal(get('company-evidence-panel').hidden,true);assert.equal(get('company-save-panel').hidden,true);assert(!get('company-case').children.some(c=>c.value==='case-a'));
 mismatch=true;await click('company-load');assert.match(get('result').textContent,/другой компании/);assert.equal(get('company-detail').hidden,true);assert.equal(get('company-case').children.length,1);assert.equal(vm.runInContext('token',ctx),'');
 mismatch=false;let release;delayed=new Promise(r=>{release=r});get('saved-token').value='fixture-a';const first=click('use-token');get('saved-token').value='fixture-b';await click('use-token');release();await first;delayed=null;assert.equal(vm.runInContext('token',ctx),'fixture-a');
 console.log('Company cabinet JS flow PASS: role/identity, evidence, explicit decision, uncertain retry, stale conflict, session clearing, request serialization.');
}
main().catch(error=>{console.error(error);process.exitCode=1});
