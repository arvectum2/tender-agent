'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(
  path.join(__dirname, '../../src/modules/tender_operator_agent_demo/assets/operator_workspace.js'),
  'utf8'
);

class Element {
  constructor(name='div') {
    this.name = name;
    this.children = [];
    this.events = {};
    this.value = '';
    this.hidden = false;
    this.disabled = false;
    this.dataset = {};
    this.files = [];
    this.classList = {toggle() {}};
  }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text || ''; }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = [...items]; }
  addEventListener(name, handler) { this.events[name] = handler; }
  scrollIntoView() {}
}

async function scenario({withFiles}) {
  const ids = new Map();
  const get = id => {
    if (!ids.has(id)) ids.set(id, new Element(id));
    return ids.get(id);
  };
  const buttons = ['new','history','registry'].map(tab => {
    const button = new Element('button');
    button.dataset.tab = tab;
    button.setAttribute = () => {};
    return button;
  });
  let analyzed = false;
  const calls = [];
  const file = {
    file_id:'FILE-01', original_name:'real.docx', display_name:'real.docx',
    extension:'.docx', extracted_text_available:analyzed, size_bytes:100,
  };
  const run = () => ({
    run_id:'run-1', status:analyzed?'completed_with_warnings':withFiles?'ready_to_analyze':'docs_required',
    files:withFiles?[{...file,extracted_text_available:analyzed}]:[],
    created_at:'2026-10-09T08:00:00Z', tender_title:'Реальная закупка',
    procurement_notice_number:'0372200172326000015',procurement_law:'44-ФЗ',
    customer_name:'Заказчик',human_in_the_loop:true,attachments_status:withFiles?'downloaded':'docs_required',
    warnings:[],limitations:[]
  });
  const fetch = async (uri,opts={}) => {
    const route=String(uri), method=opts.method||'GET';
    calls.push(method+' '+route);
    let value;
    if(route.includes('/public-44fz-search')) value={
      outcome:'success_with_results', cards:[{
        reestr_number:'0372200172326000015',title:'Реальная закупка',
        customer_name:'Заказчик', initial_price:100000,law:'44fz'
      }],has_more:false,message:'Найдены реальные карточки'
    };
    else if(route.endsWith('/workspace/import')&&method==='POST'){
      assert.deepEqual(JSON.parse(opts.body),{reference:'0372200172326000015'});
      value={run_id:'run-1',status:withFiles?'ready_to_analyze':'docs_required'};
    }
    else if(route.endsWith('/runs/run-1/analyze')&&method==='POST'){
      analyzed=true;value={status:'completed_with_warnings'};
    }
    else if(route.endsWith('/runs/run-1')) value=run();
    else if(route.endsWith('/runs/run-1/events')) value=[];
    else if(route.endsWith('/runs/run-1/report')) value={
      report_markdown:'Реальный отчёт',recommendation_label:'Проверка человеком',
      sections:[{title:'Требования',items:['Перепроверить документы']}],executive_summary:['Только оценка'],decision_core:{facts:{}}
    };
    else if(route.endsWith('/workspace/runs/run-1/evidence')) value={facts:{},warnings:[]};
    else if(route.endsWith('/workspace/runs/run-1/verify-quote') && method==='POST') {
      const body=JSON.parse(opts.body);
      assert.equal(body.file_id,'FILE-01');
      assert.equal(body.exact_quote,'Оплата производится в течение семи рабочих дней.');
      value={
        status:'literal_quote_found_in_extracted_original_only',
        evidence:{chunk_id:'dp-real-chunk-01',quote_char_start_in_chunk:16,quote_char_end_in_chunk:64}
      };
    }
    else throw new Error('Unexpected route: '+route);
    return {ok:true,status:200,json:async () => value};
  };
  const ctx = {
    document: {
      getElementById:get,createElement:tag=>new Element(tag),
      querySelectorAll:query => query==='[data-tab]'?buttons:[]
    },
    window:{history:{replaceState(){}}},
    location:{hash:'',search:''},
    URL,URLSearchParams,Intl,Date,Number,JSON,Math,Set,Promise,encodeURIComponent,
    fetch,setTimeout,clearTimeout,setInterval:() => 101,clearInterval:() => {},
    FormData,console
  };
  vm.runInNewContext(source,ctx,{filename:'operator_workspace.js'});
  get('search-query').value='сайт';
  get('search-law').value='44fz';
  await get('eis-search-form').events.submit({preventDefault() {}});
  assert.equal(get('search-results').children.length,1,'Expected one grounded search card');
  const card=get('search-results').children[0];
  const submitButton=card.children[1];
  assert.equal(submitButton.disabled,false);
  submitButton.events.click();
  for(let i=0;i<70;i++){
    if(calls.includes('GET /api/demo/tender-agent/runs/run-1/report') || (!withFiles && calls.includes('GET /api/demo/tender-agent/runs/run-1/events'))){
      await new Promise(resolve=>setTimeout(resolve,6));
      break;
    }
    await new Promise(resolve=>setTimeout(resolve,6));
  }
  assert(calls.some(c=>c.startsWith('POST /api/demo/tender-agent/procurement/public-44fz-search?')));
  assert(calls.includes('POST /api/demo/tender-agent/workspace/import'));
  assert.equal(get('run-empty').hidden,true);
  assert.equal(get('run-section').hidden,false);
  if(withFiles){
    assert(calls.includes('POST /api/demo/tender-agent/runs/run-1/analyze'),'One-click flow MUST analyze real files');
    assert(calls.includes('GET /api/demo/tender-agent/runs/run-1/report'));
    assert.equal(get('report-panel').hidden,false);
    assert.equal(get('document-count').textContent,'1');
    assert.equal(get('quote-check').hidden,false,'Proof-check UI visible only for saved original files');
    get('quote-file').value='FILE-01';
    get('quote-text').value='Оплата производится в течение семи рабочих дней.';
    await get('quote-verify-form').events.submit({preventDefault() {}});
    for(let i=0;i<50;i++){
      if(calls.includes('POST /api/demo/tender-agent/workspace/runs/run-1/verify-quote')){
        await new Promise(resolve=>setTimeout(resolve,2));break;
      }
      await new Promise(resolve=>setTimeout(resolve,2));
    }
    assert(calls.includes('POST /api/demo/tender-agent/workspace/runs/run-1/verify-quote'));
    assert(get('quote-check-result').textContent.includes('dp-real-chunk-01'));
  }else{
    assert(!calls.some(c=>c.includes('/runs/run-1/analyze')),'Never analyze a file-less EIS manifest');
    assert.equal(get('append-files-form').hidden,false,'Show manual document recovery');
    assert.equal(get('document-count').textContent,'0');
    assert.equal(get('quote-check').hidden,true,'Proof-check UI must be hidden when no original file exists');
    assert.equal(get('analyze-btn').disabled,true,'Never enable invalid analyze button');
  }
  return calls.length;
}

(async()=>{
  const complete = await scenario({withFiles:true});
  const missing = await scenario({withFiles:false});
  console.log('UNIFIED_UI_E2E_SIMULATION_PASS',complete,missing);
})().catch(error=>{console.error(error);process.exitCode=1;});
