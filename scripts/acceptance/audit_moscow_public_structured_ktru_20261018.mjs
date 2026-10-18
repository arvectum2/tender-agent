/** Bounded official public IT quote searches; no login or bidding. */
import { spawn } from 'node:child_process';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { setTimeout as sleep } from 'node:timers/promises';

const URL = 'https://zakupki.mos.ru/';
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const SCRATCH = '/Volumes/ArvectumSSD/Arvectum/tmp';

async function inspect() {
  const profile = await mkdtemp(join(SCRATCH, 'ta-mos-public-'));
  let child; let connection;
  try {
    child = spawn(CHROME, [
      '--headless=new','--disable-gpu','--no-first-run','--disable-extensions',
      '--disable-sync','--disable-background-networking','--no-default-browser-check',
      '--remote-allow-origins=*','--remote-debugging-port=0',
      '--user-data-dir=' + profile,URL,
    ], {stdio:'ignore'});
    let port = 0;
    for (let n=0;n<40 && !port;n++) {
      try {
        const file = await readFile(join(profile,'DevToolsActivePort'),'utf8');
        port = Number(file.split('\n')[0]);
      } catch {await sleep(200);}
    }
    if (!port) throw Error('No isolated CDP browser endpoint');
    const tabs = await (await fetch('http://127.0.0.1:' + port + '/json/list')).json();
    const tab = tabs.find(x=>x.type==='page' && x.url.startsWith(URL));
    if (!tab) throw Error('No first-party page');
    connection = new WebSocket(tab.webSocketDebuggerUrl);
    await new Promise((ok,bad)=>{
      connection.addEventListener('open',ok,{once:true});
      connection.addEventListener('error',bad,{once:true});
    });
    let seq=0; const pending=new Map();
    connection.addEventListener('message',event=>{
      const response=JSON.parse(event.data);
      if (!response.id || !pending.has(response.id)) return;
      const x=pending.get(response.id);pending.delete(response.id);
      response.error ? x.bad(Error(response.error.message)) : x.ok(response.result);
    });
    const send=(method,params={})=>new Promise((ok,bad)=>{
      const id=++seq;pending.set(id,{ok,bad});
      connection.send(JSON.stringify({id,method,params}));
    });
    const evalJs=async expression=>{
      const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true,timeout:6000});
      if(r.exceptionDetails)throw Error('Page script evaluation unavailable');
      return r.result.value;
    };
    await send('Runtime.enable');await sleep(15000);
    const initial = await evalJs("({title:document.title,url:location.href,has_registry_button:[...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='Реестр котировочных сессий')})");
    if (!initial.has_registry_button) return {state:'PUBLIC_REGISTRY_BUTTON_MISSING',initial,verified_current_it_bids:0};
    const click=await evalJs("(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.textContent.trim()==='Реестр котировочных сессий');if(!b)return false;b.click();return true})()");
    if (!click) throw Error('Could not activate first-party registry read-only navigation');
    await sleep(6000);
    const registry=await evalJs("({url:location.href,title:document.title,visible:(document.body.innerText||'').slice(0,1800)})");
    if(!registry.url.startsWith(URL+'purchase/list?'))throw Error('First-party registry navigation not confirmed');
    const show=await evalJs("(()=>{const x=[...document.querySelectorAll('body span')].find(x=>x.textContent?.trim()==='Показать фильтры');if(!x)return false;x.parentElement.click();return true})()");
    await sleep(1200);
    if(!show)throw Error('Observed public filter control not available');
    const extended=await evalJs("(()=>{const x=[...document.querySelectorAll('body span')].find(x=>x.textContent?.trim()==='Показать расширенные фильтры');if(!x)return false;x.parentElement.click();return true})()");
    if(!extended)throw Error('Observed public expanded filter toggle unavailable');
    await sleep(1500);
    const observations=[];
    for(const fieldName of ['КТРУ','Вид продукции']){
      const name=JSON.stringify(fieldName);
      const finder="const f=[...document.querySelectorAll('div.field')].find(x=>[...x.querySelectorAll('label')].some(l=>l.textContent.trim()==="+name+"));";
      const sourceBefore=await evalJs("(()=>{"+finder+"const picker=f?.querySelector('[role=listbox]');return {has_exact_public_label:!!f,has_real_dropdown:!!picker,placeholder:picker?.querySelector('[role=alert]')?.textContent?.trim(),role:picker?.getAttribute('role')};})()");
      if(!sourceBefore.has_exact_public_label || !sourceBefore.has_real_dropdown)throw Error('Original structured field unavailable');
      const clicked=await evalJs("(()=>{"+finder+"const picker=f?.querySelector('[role=listbox]');if(!picker)return false;picker.click();return true;})()");
      if(!clicked)throw Error('Original dropdown click failed');
      await sleep(1800);
      const after=await evalJs("(()=>{"+finder+"const picker=f?.querySelector('[role=listbox]');return {aria_expanded:picker?.getAttribute('aria-expanded'),aria_busy:picker?.getAttribute('aria-busy'),visible_options:[...f.querySelectorAll('.menu .item,[role=option]')].filter(x=>x.getClientRects().length>0).map(x=>x.textContent?.trim()).filter(Boolean).slice(0,12),dropdown_has_search_input:!!picker?.querySelector('input[type=text]'),placeholder:picker?.querySelector('[role=alert]')?.textContent?.trim()};})()");
      observations.push({label:fieldName,sourceBefore,clicked,after,observed_at_utc:new Date().toISOString()});
    }
    return {schema_version:'ta-b2g-moscow-public-structured-ktru-ui-v1',
      official_first_party_source:URL,observation_at_utc:new Date().toISOString(),
      real_ui_registry_navigated:true,real_ui_basic_filters_opened:show,
      real_ui_extended_filters_opened:extended,source_exact_field_observations:observations,
      availability_of_classification_choices_verified:observations.some(x=>x.after.visible_options.length>0),
      class_62_code_selected:false,submitted_structured_ktru_query:false,
      lack_of_options_does_not_prove_no_live_IT_auctions:true,
      company_authenticated:false,company_bids_submitted:0,owner_go:false,
      verified_corporate_b2b_leads:0,
      disposable_browser_profile_saved:false};
  } finally {
    try{connection?.close()}catch{}
    try{child?.kill('SIGTERM')}catch{}
    await sleep(350);
    await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:300});
  }
}
try { console.log(JSON.stringify(await inspect(),null,2)); }
catch(e){ console.error('PUBLIC_READ_ONLY_NAV_FAILED',e.message);process.exitCode=2; }
