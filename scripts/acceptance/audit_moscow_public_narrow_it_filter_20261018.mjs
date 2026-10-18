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
    const terms=['сайт','интеграция','доработка','автоматизация','CRM','1С','техническая поддержка','информационных систем','программных продуктов','62.01'];
    const searches=[];
    for(const term of terms){
      const focus=await evalJs("(()=>{const x=document.getElementById('filterNameLike');if(!x)return false;x.focus();x.select();return true})()");
      if(!focus)throw Error('Public search input removed');
      await send('Input.dispatchKeyEvent',{type:'rawKeyDown',key:'a',code:'KeyA',windowsVirtualKeyCode:65,modifiers:4});
      await send('Input.dispatchKeyEvent',{type:'keyUp',key:'a',code:'KeyA',windowsVirtualKeyCode:65,modifiers:4});
      await send('Input.insertText',{text:term});
      await sleep(280);
      const didApply=await evalJs("(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.textContent.trim()==='Применить');if(!b)return false;b.click();return true})()");
      if(!didApply)throw Error('Observed public apply button missing');
      await sleep(2900);
      const seen=await evalJs("({url:location.href,visible:(document.body.innerText||'').slice(0,10200),original_links:[...document.querySelectorAll('a[href]')].map(a=>({url:a.href,label:a.textContent.trim().slice(0,180)})).filter(x=>x.url.startsWith('https://zakupki.mos.ru/auction/')).slice(0,36)})");
      const parsedUrl=new globalThis.URL(seen.url);
      if(parsedUrl.origin !== 'https://zakupki.mos.ru' || parsedUrl.pathname !== '/purchase/list'){
        throw Error('Search navigated out of original public quote registry');
      }
      const filter=JSON.parse(parsedUrl.searchParams.get('filter')||'{}');
      searches.push({
        term, exact_applied_query:filter.nameLike?.value===term,
        public_status_gate:filter.auctionSpecificFilter?.stateIdIn,
        first_page_only:true, html_public_visible_text:seen.visible,
        original_detail_links:seen.original_links,
        current_date_observation_utc:new Date().toISOString()
      });
    }
    return {state:'PUBLIC_FIRST_PARTY_NARROW_IT_SEARCH_COMPLETED',source:URL,
      registry_title:registry.title,searches,
      company_authenticated:false,company_bids_submitted:0,
      company_eligibility_verified:false,verified_b2b_corporate_leads:0};
  } finally {
    try{connection?.close()}catch{}
    try{child?.kill('SIGTERM')}catch{}
    await sleep(350);
    await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:300});
  }
}
try { console.log(JSON.stringify(await inspect(),null,2)); }
catch(e){ console.error('PUBLIC_READ_ONLY_NAV_FAILED',e.message);process.exitCode=2; }
