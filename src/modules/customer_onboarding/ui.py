"""Simple first-party operator onboarding console; no third-party assets or JS CDN."""


def render_onboarding_html() -> str:
    return """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Арвектум — настройка компании</title>
<style>
:root{color-scheme:dark;--bg:#081629;--card:#13243b;--ink:#e8f2fc;--muted:#a4b9c9;--mint:#30d4ad;--line:#344964}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(120deg,#0b1b30,#12152d);color:var(--ink);font:15px/1.55 Arial,sans-serif}
main{width:min(960px,calc(100% - 28px));margin:24px auto 70px}
h1{font-size:30px;margin:0}h2{font-size:18px;margin:0 0 14px}
header{margin-bottom:28px}header p,.hint{color:var(--muted)}
mark{background:none;color:var(--mint)}section{background:var(--card);padding:24px;border:1px solid var(--line);border-radius:18px;margin-bottom:18px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}
label{display:block;color:var(--muted);font-size:13px}
input,select,textarea{display:block;width:100%;margin-top:5px;padding:11px;border-radius:8px;border:1px solid #52677c;background:#081627;color:#fff;font:inherit}
button{background:var(--mint);color:#041b27;border:0;border-radius:9px;padding:12px 20px;font-weight:700;margin-top:18px;cursor:pointer}
button:disabled{opacity:.4;cursor:not-allowed}
a{color:var(--mint)}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#071b29;border:1px solid var(--line);border-radius:12px;padding:16px;max-height:480px;overflow:auto}
.pill{display:inline-block;padding:2px 10px;border:1px solid var(--line);border-radius:30px;margin-top:10px}
@media(max-width:650px){.grid{grid-template-columns:1fr}section{padding:17px}}
</style></head><body><main>
<header><small><mark>ARVECTUM</mark> / TENDER AGENT / LOCAL PILOT</small>
<h1>Онбординг компании</h1>
<p>Сначала заполни профиль поставщика, затем приложи подтверждающие документы и проверь подходящую закупку. Оценка не является решением об участии.</p>
<a href="/pilot/tender-agent">Перейти к анализу документации →</a></header>
<section><h2>1. Профиль поставщика</h2>
<div class="grid"><label>Продолжить существующий профиль по ID
<input id="existing-customer" placeholder="CUS-2026-000001"></label>
<div><button id="load-customer" type="button">Открыть профиль</button></div></div>
<form id="onboard"><div class="grid">
<label>Юридическое наименование <input name="legal_name" required minlength="2" placeholder="ООО «Пример»"></label>
<label>ИНН <input name="inn" inputmode="numeric" pattern="([0-9]{10}|[0-9]{12})" placeholder="Необязательно"></label>
<label>КПП <input name="kpp" inputmode="numeric" pattern="[0-9]{9}" placeholder="Необязательно"></label>
<label>Категории через запятую <input name="categories" required placeholder="ИТ, разработка сайтов"></label>
<label>Регионы через запятую <input name="regions" placeholder="Москва, Санкт-Петербург"></label>
<label>Ключевые слова через запятую <input name="keywords" placeholder="Разработка ПО"></label>
<label>НМЦК от, ₽ <input name="price_min" type="number" min="0" step="0.01"></label>
<label>НМЦК до, ₽ <input name="price_max" type="number" min="0" step="0.01"></label>
<label>Целевая маржа, % <input name="margin" type="number" min="0" max="100" step="0.1" value="20"></label>
<label>Допустимый риск <select name="tolerance"><option value="low">Низкий</option><option value="medium" selected>Средний</option><option value="high">Высокий</option></select></label>
<label>Лицензии через запятую <input name="licenses" placeholder="Необязательно"></label>
<label>Допуски СРО через запятую <input name="sro" placeholder="Необязательно"></label>
</div><button>Сохранить профиль</button></form>
<p class="hint" id="company">Компания ещё не создана. Указывайте только подтверждённые вами сведения.</p></section>
<section><h2>2. Подтверждающие документы</h2>
<p class="hint">PDF до 8 МБ. Сведения фиксируются как предоставленные оператором, без автоматической проверки юридической силы.</p>
<form id="document"><div class="grid">
<label>Ключ документа <input name="document_key" required pattern="[a-z0-9][a-z0-9_-]{2,63}" placeholder="license_software"></label>
<label>Вид документа <select name="document_type"><option value="STATUTORY">Учредительный</option><option value="LICENSE">Лицензия</option><option value="CERTIFICATE">Сертификат</option><option value="EXPERIENCE">Опыт</option><option value="REQUISITES">Реквизиты</option><option value="TEMPLATE">Шаблон</option></select></label>
<label>Название <input name="display_name" required placeholder="Лицензия"></label>
<label>Срок действия <input name="expires_at" type="date"></label>
<label>PDF <input name="file" type="file" accept="application/pdf,.pdf" required></label>
</div><button id="upload-btn" disabled>Добавить документ</button></form></section>
<section><h2>3. Персонализированная проверка закупки</h2>
<p class="hint">Номер 44-ФЗ или ссылка на карточку ЕИС. Только цитируемые исходные сведения; лицензии, маржа и юридические риски проверяются человеком.</p>
<form id="screen"><label>Номер / HTTPS-ссылка закупки <input name="reference" minlength="19" placeholder="0123456789026000001"></label>
<label>Либо ID уже проанализированного локального прогона <input name="run_id" placeholder="Из мастера Tender Agent"></label>
<button id="screen-btn" disabled>Проверить по профилю</button></form></section>
<section><h2>4. Доступ клиента к SaaS-пилоту</h2>
<p class="hint">Оператор создаёт отдельный tenant и одноразовое приглашение владельца.
Клиенту передаётся только invitation_code по согласованному приватному каналу,
никогда внутренний пароль Basic Auth. Платежи и публичная оферта отключены.</p>
<label>Черновой пакет <select id="saas-selected-plan"><option value="pilot">Pilot</option><option value="team">Team</option></select></label>
<button type="button" id="saas-bootstrap" disabled>Создать tenant и одноразовое приглашение</button></section>
<section><h2>Результаты и журнал</h2><span class="pill" id="state">Ожидание заполнения</span>
<pre id="result" aria-live="polite">Здесь появится результат шагов.</pre></section>
<script>
"use strict";
let customerId = null;
const $ = (sel)=>document.querySelector(sel);
const split = (s)=>s.split(",").map(x=>x.trim()).filter(Boolean);
const number = (s)=>s === "" ? null : Number(s);
function output(message){$("#result").textContent=JSON.stringify(message,null,2)}
async function api(path,body,upload=false){
 const opts={method:"POST",credentials:"same-origin",body:upload?body:JSON.stringify(body)};
 if(!upload)opts.headers={"Content-Type":"application/json"};
 const response=await fetch(path,opts);let content=await response.json().catch(()=>({detail:"Unexpected response"}));
 if(!response.ok)throw new Error(JSON.stringify(content));return content;
}
async function execute(fn){$("#state").textContent="Обработка…";try{await fn();$("#state").textContent="Шаг выполнен";}catch(e){$("#state").textContent="Требуется исправление";output({error:e.message});}}
$("#saas-bootstrap").addEventListener("click",()=>execute(async()=>{
 if(!customerId)throw Error("Сначала создайте или откройте компанию");
 const result=await api("/api/operator/saas/tenants",{
  customer_id:customerId,plan_code:$("#saas-selected-plan").value
 });
 output(result);
}));
$("#load-customer").addEventListener("click",()=>execute(async()=>{
 const id=String($("#existing-customer").value||"").trim();
 if(!id)throw Error("Укажите ID компании");
 const response=await fetch("/api/onboarding/customers/"+encodeURIComponent(id),{credentials:"same-origin"});
 const data=await response.json();if(!response.ok)throw Error(JSON.stringify(data));
 customerId=data.customer_id;$("#company").textContent="Редактирование компании: "+customerId;
 const f=$("#onboard").elements;
 f.namedItem("legal_name").value=data.legal_name||"";
 f.namedItem("inn").value=data.inn||"";
 f.namedItem("kpp").value=data.kpp||"";
 for(const key of ["legal_name","inn","kpp"])f.namedItem(key).readOnly=true;
 const p=data.profile||{},c=p.criteria||{},m=p.commercial||{},q=p.qualification||{},r=p.risk_preferences||{};
 for(const key of ["categories","regions","keywords"])f.namedItem(key).value=(c[key]||[]).join(", ");
 for(const key of ["price_min","price_max"])f.namedItem(key).value=c[key]??"";
 f.namedItem("margin").value=m.target_margin_percent??"";
 f.namedItem("tolerance").value=r.tolerance||"medium";
 f.namedItem("licenses").value=(q.licenses||[]).join(", ");
 f.namedItem("sro").value=(q.sro_approvals||[]).join(", ");
 $("#upload-btn").disabled=false;$("#screen-btn").disabled=false;$("#saas-bootstrap").disabled=false;output(data);
}));
$("#onboard").addEventListener("submit",e=>{e.preventDefault();execute(async()=>{
 const d=new FormData(e.target);const v=k=>String(d.get(k)||"").trim();
 const payload={legal_name:v("legal_name"),inn:v("inn")||null,kpp:v("kpp")||null,
 criteria:{categories:split(v("categories")),regions:split(v("regions")),keywords:split(v("keywords")),
 price_min:number(v("price_min")),price_max:number(v("price_max"))},
 commercial:{target_margin_percent:number(v("margin"))},
 qualification:{licenses:split(v("licenses")),sro_approvals:split(v("sro"))},
 risk_preferences:{tolerance:v("tolerance")}};
 const updating=Boolean(customerId);
 const endpoint=updating?"/api/onboarding/customers/"+encodeURIComponent(customerId)+"/profile":"/api/onboarding/customers";
 const opts={method:updating?"PUT":"POST",headers:{"Content-Type":"application/json"},credentials:"same-origin",body:JSON.stringify(payload)};
 const resp=await fetch(endpoint,opts),result=await resp.json();
 if(!resp.ok)throw Error(JSON.stringify(result));
 customerId=result.customer_id;$("#company").textContent="Профиль компании: "+customerId;
 for(const key of ["legal_name","inn","kpp"])$("#onboard").elements.namedItem(key).readOnly=true;
 $("#upload-btn").disabled=false;$("#screen-btn").disabled=false;$("#saas-bootstrap").disabled=false;output(result);
});});
$("#document").addEventListener("submit",e=>{e.preventDefault();execute(async()=>{
 if(!customerId)throw Error("Сначала создать профиль");
 const data=new FormData(e.target);
 if(!data.get("expires_at"))data.delete("expires_at");
 output(await api("/api/onboarding/customers/"+encodeURIComponent(customerId)+"/documents",data,true));
});});
$("#screen").addEventListener("submit",e=>{e.preventDefault();execute(async()=>{
 if(!customerId)throw Error("Сначала создать профиль");
 const input=new FormData(e.target);
 const runId=String(input.get("run_id")||"").trim();
 const endpoint="/api/onboarding/customers/"+encodeURIComponent(customerId);
 if(runId)output(await api(endpoint+"/runs/"+encodeURIComponent(runId)+"/screen",{}));
 else output(await api(endpoint+"/screen",{reference:input.get("reference")}));
});});
</script></main></body></html>"""
