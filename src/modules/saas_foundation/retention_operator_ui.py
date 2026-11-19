"""Internal console; proposal recording only."""


def render_console() -> str:
    return r"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Арвектум — хранение документов</title>
<style>
*{box-sizing:border-box}body{font:15px system-ui;background:#f5f7f8;color:#263238;max-width:1000px;margin:auto;padding:20px}
h1{font-size:25px}h2{font-size:19px}section{background:white;border:1px solid #dce3e4;padding:18px;margin:14px 0;border-radius:8px}
label{display:grid;gap:5px;margin:10px 0}input,select,button{font:inherit;padding:9px;border:1px solid #aabbbe;border-radius:5px;min-width:0}
button{background:#116c69;color:white;border:0;cursor:pointer}button:disabled{opacity:.5}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,230px),1fr));gap:0 14px}
.check{display:flex;align-items:center}.warn{background:#fff4e5;padding:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere}
fieldset{border:0;padding:0;min-width:0}
</style></head><body>
<header><small>ARVECTUM / TENDER AGENT / ОПЕРАТОР</small><h1>Хранение документов</h1>
<p class="warn">Только предложения. Не разрешает удаление и не изменяет доступ.</p></header>
<section><label>Идентификатор клиента<input id="tenant" maxlength="128" autocomplete="off"></label>
<button id="load" type="button">Загрузить</button><p id="status" role="status" aria-live="polite"></p></section>
<div id="workspace" hidden><section><h2>Учёт хранилища</h2><p>Логический объём файлов, без резервных копий и индексов.</p><pre id="metrics"></pre></section>
<section><h2>Условия хранения</h2><label>Существующая версия<select id="existing"></select></label>
<form id="schedule"><fieldset id="schedule-fields"><div class="grid">
<label>Ссылка на заказ<input id="order" required maxlength="128"></label>
<label>Ссылка на политику<input id="policy" required maxlength="128"></label>
<label>Дата окончания<input id="ended" type="date"></label>
<label>Основание окончания<input id="endref" maxlength="128"></label>
<label>Рабочие копии, дней<input id="working" type="number" min="0" max="3650" value="30" required></label>
<label>Резервные копии, дней<input id="backup" type="number" min="0" max="3650" value="90" required></label>
<label>Ограничение удаления<select id="hold"><option value="UNKNOWN">Не установлено</option><option value="ACTIVE">Действует</option><option value="CLEAR">Предложено отсутствие</option></select></label>
<label>Основание ограничения<input id="holdref" maxlength="128"></label>
<label>Дата пересмотра<input id="review" type="date"></label></div>
<p id="revision"></p><p id="planning"></p>
<label class="check"><input id="confirm-schedule" type="checkbox" required>Подтверждаю запись предложения</label>
<button type="submit">Записать новую версию</button></fieldset></form></section>
<section><h2>Первичная привязка документа</h2><p>Существующие связи неизменяемы; исправление требует отдельной процедуры.</p>
<form id="link"><fieldset id="link-fields"><div class="grid">
<label>Документ без связи<select id="document" required></select></label>
<label>Версия условий<select id="proposal" required></select></label>
<label>Основание связи<input id="evidence" maxlength="128" required></label></div>
<label class="check"><input id="confirm-link" type="checkbox" required>Подтверждаю только предлагаемую связь</label>
<button type="submit">Записать привязку</button></fieldset></form></section></div>
<script>
'use strict';
const by=id=>document.getElementById(id), val=id=>by(id).value.trim(), nullable=id=>val(id)||null;
let active='', state=null, busy=false, revision=0;
const status=s=>by('status').textContent=s;
function clear(){active='';state=null;by('workspace').hidden=true;status('')}
function path(t){return '/api/operator/saas/tenants/'+encodeURIComponent(t)+'/retention'}
async function api(url,body){
 const init={credentials:'same-origin',cache:'no-store'};
 if(body!==undefined)Object.assign(init,{method:'POST',headers:{'Content-Type':'application/json','X-Retention-Intent':'proposal-only'},body:JSON.stringify(body)});
 const r=await fetch(url,init);if(!r.ok)throw Error('Ошибка HTTP '+r.status);return r.json()
}
function option(id,v,l){const o=document.createElement('option');o.value=v;o.textContent=l;by(id).append(o)}
function reset(id,l){by(id).replaceChildren();option(id,'',l)}
function fill(){
 const p=state.proposals.find(p=>p.proposal_id===val('existing')),s=p?.schedule||{};
 revision=p?.revision||0;by('order').readOnly=!!p;
 for(const [id,key,fallback] of [['order','order_ref',''],['policy','policy_ref',''],['ended','order_ended_on',''],['endref','end_evidence_ref',''],['working','working_days',30],['backup','backup_days',90],['hold','hold_state','UNKNOWN'],['holdref','hold_evidence_ref',''],['review','hold_review_on','']])by(id).value=s[key]??fallback;
 by('revision').textContent='Текущая версия: '+revision;by('confirm-schedule').checked=false;
 by('planning').textContent=p?'Предлагаемые даты: рабочие '+(p.planning.proposed_working_until||'—')+'; резервные '+(p.planning.proposed_backup_until||'—'):''
}
function render(d){
 state=d;const lines=[];
 for(const [k,label] of [['archives','Комплекты'],['forms','Формы']]){
 const r=d.accounting[k];lines.push(label+': '+r.count+' шт. / '+r.payload_bytes+' байт','  Истекли: '+r.expired+'; без связи: '+r.unlinked+'; ограничения: '+r.hold_active+'; устарели: '+r.proposal_superseded)}
 by('metrics').textContent=lines.join('\n');
 reset('existing','Новое предложение');reset('proposal','Выберите условия');reset('document','Выберите документ');
 for(const p of d.proposals){const title=p.schedule.order_ref+' / версия '+p.revision;option('existing',p.proposal_id,title);option('proposal',p.proposal_id,title)}
 for(const f of d.documents.filter(f=>!f.proposed_link))option('document',f.kind+':'+f.id,(f.kind==='archive'?'Комплект ':'Форма ')+f.id);
 by('confirm-link').checked=false;by('evidence').value='';fill();by('workspace').hidden=false
}
function lock(v){busy=v;for(const id of ['tenant','load','schedule-fields','link-fields','existing'])by(id).disabled=v}
async function load(){
 if(busy)return;clear();const t=val('tenant');
 if(!/^[A-Za-z0-9_-]{1,128}$/.test(t)){status('Укажите идентификатор клиента');return}
 lock(true);status('Загрузка…');try{const d=await api(path(t));active=t;render(d);status('Данные загружены')}
 catch(e){clear();status(e.message)}finally{lock(false)}
}
async function write(suffix,body){
 if(busy||!active||active!==val('tenant'))return;
 const t=active;lock(true);status('Запись…');
 try{await api(path(t)+suffix,body);render(await api(path(t)));status('Предложение записано. Разрешения не изменены.')}
 catch(e){clear();status(e.message+'. Снова загрузите клиента.')}finally{lock(false)}
}
by('tenant').addEventListener('input',clear);by('load').addEventListener('click',load);by('existing').addEventListener('change',fill);
by('schedule').addEventListener('submit',e=>{
 e.preventDefault();if(!by('confirm-schedule').checked)return;
 write('/proposals',{expected_revision:revision,confirm_proposal_only:true,schedule:{
 order_ref:val('order'),policy_ref:val('policy'),order_ended_on:nullable('ended'),end_evidence_ref:nullable('endref'),
 working_days:Number(val('working')),backup_days:Number(val('backup')),hold_state:val('hold'),hold_evidence_ref:nullable('holdref'),hold_review_on:nullable('review')}})
});
by('link').addEventListener('submit',e=>{
 e.preventDefault();if(!by('confirm-link').checked)return;const i=val('document').indexOf(':');if(i<1)return;
 write('/links',{proposal_id:val('proposal'),document_kind:val('document').slice(0,i),document_id:val('document').slice(i+1),evidence_ref:val('evidence'),confirm_proposal_only:true})
});
</script></body></html>"""
