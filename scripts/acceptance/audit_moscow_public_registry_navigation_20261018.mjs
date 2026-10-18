/** Read-only isolated headless Chrome probe of one observed official button. */
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
    const shown=await evalJs("({url:location.href,title:document.title,text_prefix:(document.body?.innerText||'').slice(0,2400),text_length:(document.body?.innerText||'').length,public_links:[...document.querySelectorAll('a[href]')].map(a=>a.href).filter(x=>x.startsWith('https://zakupki.mos.ru/')).slice(0,25)})");
    if (!shown.url.startsWith(URL))return {state:'NAV_OUTSIDE_APPROVED_HOST_NO_FOLLOWUP',initial,host:new URL(shown.url).hostname,verified_current_it_bids:0};
    return {state:'PUBLIC_QUOTE_REGISTRY_BUTTON_NAVIGATED',initial,shown,verified_current_it_bids:0,authenticated:false,sent_reply:false};
  } finally {
    try{connection?.close()}catch{}
    try{child?.kill('SIGTERM')}catch{}
    await sleep(350);
    await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:300});
  }
}
try { console.log(JSON.stringify(await inspect(),null,2)); }
catch(e){ console.error('PUBLIC_READ_ONLY_NAV_FAILED',e.message);process.exitCode=2; }
