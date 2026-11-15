"""Self-service invitation, legal, profile and first tender pilot interface."""


def render_saas_html() -> str:
    return """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Арвектум · клиентский пилот</title>
<style>
:root{color-scheme:dark;--bg:#07182d;--panel:#142a40;--ink:#e6f6ff;--muted:#a4b9c9;--mint:#30d4ae}
*{box-sizing:border-box}body{background:linear-gradient(125deg,#08192e,#18182f);color:var(--ink);font:15px/1.5 Arial,sans-serif;margin:0}
main{width:min(990px,calc(100% - 30px));margin:34px auto 90px}
small,h3,label{color:var(--muted)}small{letter-spacing:.14em}h1{font-size:34px;margin:.2em 0}h2{font-size:19px;margin-top:0}
section{background:var(--panel);border:1px solid #3b5067;border-radius:17px;padding:23px;margin:17px 0}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
label{display:block;font-size:13px;margin-bottom:10px}input,textarea,select{width:100%;padding:10px;margin-top:6px;border:1px solid #5e7287;border-radius:8px;background:#08192b;color:#fff;font:inherit}
textarea{min-height:75px}button{padding:11px 18px;border-radius:8px;background:var(--mint);border:0;color:#072a35;font-weight:700;cursor:pointer;margin:8px 7px 0 0}
button:disabled{opacity:.45;cursor:default}pre{padding:17px;background:#081a2a;border:1px solid #304b5b;border-radius:10px;white-space:pre-wrap;overflow-wrap:anywhere;max-height:400px;overflow:auto}
.pill{display:inline-block;color:var(--mint);border:1px solid #496477;padding:4px 9px;border-radius:14px}p{color:var(--muted)}a{color:var(--mint)}
@media(max-width:670px){.grid{grid-template-columns:1fr}section{padding:17px}}
</style></head><body><main><header><small>АРВЕКТУМ · ТЕНДЕРНЫЙ АГЕНТ</small>
<h1>Клиентский пилот</h1><p>Настройте работу своей компании, изучайте закупки и получайте доказательные отчёты.
Это локальная тестовая версия. Участие в закупках и юридически значимые действия подтверждает человек.</p></header>
<section><h2>1. Доступ по приглашению</h2><div class="grid">
<label>Одноразовый код приглашения<input id="invite-code" autocomplete="off" placeholder="invite_…"></label>
<label>Имя участника<input id="display-name" placeholder="Имя сотрудника"></label></div>
<button id="redeem">Принять приглашение</button>
<label>Уже есть токен? Введите в этой сессии<input id="saved-token" type="password" autocomplete="off" placeholder="saas_…"></label>
<button id="use-token">Войти по токену</button><button id="rotate-token">Обновить токен</button><button id="logout">Завершить сессию</button>
<p>Токен показывается только один раз и не сохраняется в браузере. Не пересылайте его посторонним.</p></section>
<section><h2>2. Условия пилота</h2>
<p>Это демонстрационные условия и тестовый контур, не публичная оферта.
Автоматической оплаты и автоматической подачи заявок нет.
Данные компании изолированы по tenant и доступны согласно роли.</p>
<label><input id="legal-agree" type="checkbox" style="width:auto"> Я ознакомился(-лась) с указанными ограничениями пилота и обработкой данных</label>
<button id="accept">Подтвердить ознакомление</button></section>
<section><h2>3. Профиль поставщика</h2>
<p>Создаётся из привязанной к приглашению компании. Только владелец и администратор могут изменять профиль.</p>
<div class="grid"><label>Категории через запятую<input id="categories" placeholder="Разработка ПО, ИТ"></label>
<label>Регионы через запятую<input id="regions" placeholder="Москва"></label>
<label>Ключевые слова через запятую<input id="keywords" placeholder="разработка сайтов"></label>
<label>Минимальная НМЦК, ₽<input id="price-min" type="number" min="0" step=".01"></label>
<label>Максимальная НМЦК, ₽<input id="price-max" type="number" min="0" step=".01"></label>
<label>Целевая маржа, %<input id="margin" type="number" min="0" max="100" value="20"></label>
<label>Лицензии через запятую<input id="licenses"></label>
<label>Допуски СРО через запятую<input id="sro"></label></div>
<button id="read-profile">Показать профиль</button><button id="save-profile">Сохранить новую версию</button></section>
<section><h2>3a. Референс-лист исполненных контрактов</h2>
<p>Версии не удаляются: новая запись замещает предыдущую для будущей оценки. Отсутствие списка — UNKNOWN, а не ноль контрактов. Указывайте только фактически исполненные договоры и ссылки на подписанные акты.</p>
<p id="reference-state" role="status">Список пока не загружен</p>
<button id="load-references">Загрузить мой референс-лист</button>
<div class="grid">
<label>Дата подтверждения владельцем<input id="references-as-of" type="date"></label>
<label>Полнота сведений<select id="references-completeness">
<option value="PARTIAL">Частичный список — NO GO запрещён</option>
<option value="COMPLETE">Полный список — отсутствие контрактов подтверждаю</option>
</select></label>
<label>Основание новой версии<input id="references-source" maxlength="512" placeholder="OWNER_ATTESTATION_2026-10-13"></label>
</div>
<label><input type="checkbox" id="references-confirm" style="width:auto"> Подтверждаю полноту данных о выполненных контрактах своей компании. Это заявление владельца, не юридическая проверка документов.</label>
<div id="references-contracts" aria-live="polite"></div>
<button id="references-add">Добавить договор</button>
<button id="references-save">Сохранить новую версию</button>
<p>Для зачёта договора обязательны номер, закон, предмет, флаг чат-бота, дата подписания последнего акта и ссылки на договор и итоговый акт. Результат конкурентный, не юридический.</p>
</section>
<section><h2>4. Документы и анализ закупок</h2>
<div class="grid"><label>Ключ документа<input id="doc-key" placeholder="license_2026"></label>
<label>Тип документа<select id="doc-type"><option>LICENSE</option><option>STATUTORY</option><option>CERTIFICATE</option><option>EXPERIENCE</option><option>REQUISITES</option><option>TEMPLATE</option></select></label>
<label>Название документа<input id="doc-title"></label><label>PDF<input type="file" id="doc-file" accept=".pdf,application/pdf"></label></div>
<button id="upload-doc">Загрузить PDF</button>
<h3>Предварительный анализ реальной закупки</h3><label>Номер извещения ЕИС (44-ФЗ) или ссылка<input id="reference" placeholder="0372200172326000015"></label>
<button id="screen">Сопоставить с профилем</button>
<button id="import-eis">Скачать документацию ЕИС в мой контур</button>
<h3>Анализ файлов закупки</h3>
<label>Предмет закупки<input id="tender-title" placeholder="Разработка сайта"></label>
<label>Заказчик по документации (необязательно)<input id="procurement-customer" placeholder="Не установлен"></label>
<label>Тендерные документы (.pdf, .docx, .txt и др.)<input id="tender-files" type="file" multiple></label>
<button id="create-run">Загрузить в контур</button><button id="append-files">Дополнить текущий прогон</button><label>ID своего прогона<input id="run-id" placeholder="toa-run-…"></label>
<button id="analyze-run">Анализировать</button><button id="report-run">Посмотреть отчёт</button>
<button id="screen-run">Сопоставить с профилем</button>
<button id="qualify-run">Оценить шансы по оригинальным критериям ЕИС</button>
<div id="qualification-panel" hidden role="status" aria-live="polite" style="border:1px solid #496477;border-radius:10px;padding:12px;margin-top:12px">
<strong id="qualification-verdict"></strong>
<p id="qualification-source-note"></p>
</div></section>
<section><h2>4a. Портфель компании</h2>
<p id="company-identity" role="status">Войдите и загрузите портфель.</p>
<button id="company-load">Загрузить портфель</button><button id="company-more" disabled>Ещё закупки</button>
<div id="company-save-panel" hidden><label>Номер ЕИС<input id="company-registry" inputmode="numeric" maxlength="20" autocomplete="off"></label>
<button id="company-save">Добавить ссылку в портфель</button></div>
<details><summary>Поиск по сохранённому профилю компании</summary>
<p>Пилотный поиск ЕИС 44-ФЗ: до 8 запросов за день и до 10 карточек на запрос. Не заменяет полное исследование рынка.</p>
<button id="company-search-refresh">Состояние поиска</button><button id="company-search-start" disabled>Подготовить поиск</button><button id="company-search-run" disabled>Выполнить оставшиеся шаги</button>
<p id="company-search-state" role="status">Загрузите портфель и состояние поиска.</p>
<pre id="company-search-receipts"></pre>
<label>Найденная закупка<select id="company-search-candidate"><option value="">Выберите кандидата</option></select></label><button id="company-search-accept" disabled>Добавить кандидата в портфель</button>
<p>Добавление сохраняет только ссылку на закупку. Оригиналы и квалификация проверяются отдельно.</p></details>
<p id="company-count" aria-live="polite"></p>
<label>Карточка<select id="company-case"><option value="">Выберите закупку</option></select></label>
<button id="company-open">Открыть карточку</button>
<div id="company-detail" hidden>
<p id="company-case-state"></p><pre id="company-history" aria-live="polite"></pre>
<div id="company-decision-panel" hidden>
<div class="grid"><label>Решение<select id="company-action"><option value="GO">GO</option><option value="NO_GO">NO GO</option><option value="DEFER">Отложить</option></select></label>
<label>Отложить до (местное время браузера)<input id="company-defer" type="datetime-local"></label></div>
<label>Обоснование<textarea id="company-rationale" maxlength="2000"></textarea></label>
<label><input id="company-confirm" type="checkbox" style="width:auto"> Подтверждаю решение для указанной компании и закупки. Это не подача заявки.</label>
<button id="company-decide">Сохранить решение</button></div>
<div id="company-evidence-panel" hidden><h3>Оригиналы и квалификация</h3>
<p id="company-profile-state"></p><label>ID собственного прогона<input id="company-run-id" autocomplete="off"></label>
<button id="company-bind">Привязать оригиналы к текущей версии профиля</button>
<label>Привязка<select id="company-evidence"><option value="">Выберите привязку</option></select></label>
<button id="company-read-evidence">Проверить сохранённые оригиналы и показать оценку</button>
<p id="company-evidence-state" aria-live="polite"></p>
<pre id="company-evidence-result" hidden></pre></div>
</div><p>Сохранённый номер не подтверждает актуальность извещения, квалификацию или право подачи заявки. История решений общая для веб и iOS.</p></section>
<section><h2>5. Мой пакет и лимиты</h2><button id="me">Мой кабинет</button>
<button id="packages">Показать пакеты</button>
<button id="usage">Остатки лимитов</button>
<p>Все цены — на согласовании. Списание средств в этом пилоте не производится.</p></section>
<section><h2>6. Участники компании</h2>
<p>Владелец и администратор могут выдавать одноразовые приглашения другим
сотрудникам в пределах лимита рабочих мест. При отзыве доступа токены участника блокируются.</p>
<label>Роль приглашённого сотрудника<select id="invite-role">
<option value="analyst">Аналитик</option><option value="viewer">Наблюдатель</option>
<option value="admin">Администратор</option></select></label>
<button id="invite-member">Одноразовое приглашение сотрудника</button>
<button id="members-list">Показать участников</button>
<label>ID участника для отзыва<input id="revoke-member-id" placeholder="ID из списка участников"></label>
<button id="revoke-member">Отозвать доступ</button></section>
<section><h2>Результаты</h2><span class="pill" id="state">Ожидание авторизации</span>
<pre id="result" aria-live="polite">Здесь появятся ответы сервера.</pre></section></main>
<script>
"use strict";
let token="";
let legalVersions=null;
let uiBusy=false;
let sessionEpoch=0;
const val=id=>document.getElementById(id).value.trim();
const split=id=>val(id).split(",").map(x=>x.trim()).filter(Boolean);
const num=id=>val(id)===""?null:Number(val(id));
const output=(r)=>{document.getElementById("result").textContent=JSON.stringify(r,null,2)};
async function call(path,{method="GET",body=null,auth=true,upload=false}={}){
 const epoch=sessionEpoch;
 if(auth&&!token)throw Error("Сначала войдите в кабинет");
 const options={method,credentials:"omit",cache:"no-store",redirect:"error",headers:{"Accept":"application/json","Cache-Control":"no-store"}};
 if(auth&&token)options.headers.Authorization="Bearer "+token;
 if(body!==null){options.body=upload?body:JSON.stringify(body);if(!upload)options.headers["Content-Type"]="application/json"}
 const r=await fetch(path,options);const d=await r.json().catch(()=>({error:"Non-JSON server response"}));
 if(epoch!==sessionEpoch)throw Error("Сессия изменена");
 if(!r.ok){const error=Error("HTTP "+r.status+" "+JSON.stringify(d));error.status=r.status;throw error}return d;
}
function showQualification(reply){
 const item=reply?.qualification || (reply?.competitive_recommendation ? reply : null);
 const panel=document.getElementById("qualification-panel");
 if(!item){panel.hidden=true;return}
 panel.hidden=false;
 const rec=item.competitive_recommendation;
 document.getElementById("qualification-verdict").textContent =
   rec==="NO_GO" ? "NO GO по квалификационной конкурентоспособности" :
   rec==="NOT_ASSESSED" ? (item.source_status==="ORIGINAL_EIS_BYTES_CORRELATED_SIGNATURE_NOT_VERIFIED" ? "Оригинал оценки подтверждён — специалисты и опыт требуют проверки" : "Квалификация не оценена — исходных сведений недостаточно") :
   "Квалификация: требуется проверка";
 const c=item.criterion_source || {};
 document.getElementById("qualification-source-note").textContent =
   "Референс-лист исполненных контрактов: " + (item.qualifying_contracts ?? "не подтверждён") +
   ". Вес квалификации: " + (c.qualification_weight_percent ?? "не установлен") +
   "%; вес цены: " + (c.price_weight_percent ?? "не установлен") +
   "%. Источник: " + (item.source_status || "не подтверждён") +
   ". Это не юридический отказ, подпись ЕИС не проверена, подача заявки запрещена без решения человека.";
}
async function run(task){if(uiBusy)return;uiBusy=true;const enabled=[...document.querySelectorAll("button,input,textarea,select")].filter(x=>!x.disabled);for(const el of enabled)el.disabled=true;document.getElementById("state").textContent="Обработка…";try{
 const result=await task();document.getElementById("state").textContent="Готово";output(result);showQualification(result);
}catch(err){if([401,402,403].includes(err.status))clearSession();document.getElementById("state").textContent="Нужна проверка";output({error:err.message});document.getElementById("qualification-panel").hidden=true;}finally{uiBusy=false;for(const el of enabled)el.disabled=false;syncCompanyControls();}}
function bind(id,task){document.getElementById(id).addEventListener("click",()=>run(task))}
bind("redeem",async()=>{
 const body={invitation_code:val("invite-code"),display_name:val("display-name")};clearSession();
 const result=await call("/api/saas/invitations/redeem",{method:"POST",auth:false,body});
 token=result.access_token;return result;
});
bind("use-token",async()=>{const supplied=val("saved-token");clearSession();token=supplied;try{return await call("/api/saas/me")}catch(error){clearSession();throw error}});
bind("rotate-token",async()=>{const rotated=await call("/api/saas/token/rotate",{method:"POST"});clearSession();token=rotated.access_token;return rotated;});
bind("logout",async()=>{try{return await call("/api/saas/logout",{method:"POST"})}finally{clearSession();}});
bind("accept",async()=>{
 if(!document.getElementById("legal-agree").checked)throw Error("Требуется явное ознакомление");
 const info=await call("/api/saas/legal");legalVersions=info;
 return call("/api/saas/legal/accept",{method:"POST",body:{terms_version:info.terms_version,privacy_version:info.privacy_version,confirm_read:true}});
});
let referenceVersion=null;
function referenceField(holder,labelText,id,type,value,choices){
 const label=document.createElement("label");
 label.textContent=labelText;
 let input;
 if(choices){
   input=document.createElement("select");
   for(const [key,title] of choices){
     const opt=document.createElement("option");opt.value=key;opt.textContent=title;
     input.append(opt);
   }
 }else{
   input=document.createElement("input");input.type=type;
 }
 input.dataset.refField=id;
 if(type==="checkbox"){input.checked=Boolean(value);input.style.width="auto"}
 else{input.value=value??""}
 label.append(input);holder.append(label);
 return input;
}
function addReferenceContract(values={}){
 const group=document.createElement("fieldset");
 group.style.cssText="border:1px solid #496477;border-radius:8px;padding:12px;margin-top:12px";
 const legend=document.createElement("legend");legend.textContent="Договор";
 group.append(legend);
 const grid=document.createElement("div");grid.className="grid";group.append(grid);
 referenceField(grid,"Закон","law","select",values.law??"44fz",[["44fz","44-ФЗ"],["223fz","223-ФЗ"]]);
 referenceField(grid,"Номер договора","contract_number","text",values.contract_number);
 referenceField(grid,"Предмет","subject","select",values.subject??"website",[
   ["website","Сайт"],["web_portal","Веб-портал"],
   ["information_system","Информационная система"],["module","Модуль"]]);
 referenceField(grid,"Чат-бот входил в договор","chatbot_in_scope","checkbox",values.chatbot_in_scope);
 referenceField(grid,"Договор полностью исполнен","completed","checkbox",values.completed);
 referenceField(grid,"Дата последнего подписанного акта","acceptance_signed_at","date",values.acceptance_signed_at);
 referenceField(grid,"Ссылка/ключ документа договора","contract_document_ref","text",values.contract_document_ref);
 referenceField(grid,"Ссылка/ключ подписанного итогового акта","signed_final_act_ref","text",values.signed_final_act_ref);
 const remove=document.createElement("button");remove.type="button";
 remove.textContent="Удалить строку договора из новой версии";
 remove.addEventListener("click",()=>group.remove());group.append(remove);
 document.getElementById("references-contracts").append(group);
}
function getReferenceContracts(){
 const fields=["law","contract_number","subject","chatbot_in_scope","completed",
               "acceptance_signed_at","contract_document_ref","signed_final_act_ref"];
 return [...document.getElementById("references-contracts").querySelectorAll("fieldset")].map(group=>{
  const result={};
  for(const field of fields){
    const input=group.querySelector('[data-ref-field="'+field+'"]');
    result[field]=input.type==="checkbox"?input.checked:(input.value||null);
  }
  return result;
 });
}
function displayReferences(data){
 referenceVersion=data.fact_version??0;
 const snapshot=data.snapshot||{};
 document.getElementById("references-state").textContent =
   "Текущее состояние: "+(data.state||"UNKNOWN")+
   "; версия "+referenceVersion+
   "; договоров "+(snapshot.contracts?.length??"неизвестно")+
   ". Без подтверждения владельца вывод UNKNOWN.";
 document.getElementById("references-as-of").value=snapshot.as_of_date??"";
 document.getElementById("references-completeness").value=snapshot.completeness??"PARTIAL";
 document.getElementById("references-confirm").checked=Boolean(snapshot.owner_confirmed);
 document.getElementById("references-source").value="";
 document.getElementById("references-contracts").replaceChildren();
 for(const contract of snapshot.contracts||[])addReferenceContract(contract);
}
bind("load-references",async()=>{
 const result=await call("/api/saas/qualification/references");
 displayReferences(result);return result;
});
bind("references-add",()=>{if(referenceVersion===null)throw Error("Сначала загрузите текущую версию");
 addReferenceContract();return {draft_contracts:getReferenceContracts().length};
});
bind("references-save",async()=>{
 if(referenceVersion===null)throw Error("Перед сохранением загрузите текущую версию");
 const asOf=val("references-as-of");
 const completeness=val("references-completeness");
 const ownerConfirmed=document.getElementById("references-confirm").checked;
 const contracts=getReferenceContracts();
 const sourceRef=val("references-source");
 if(!asOf||!sourceRef)throw Error("Укажите дату подтверждения и основание новой версии");
 if(completeness==="COMPLETE"&&!ownerConfirmed)throw Error("Для полного списка необходимо подтверждение владельца");
 if(completeness==="COMPLETE"&&contracts.length===0&&!ownerConfirmed)
   throw Error("Нулевой список может подтвердить только владелец");
 for(const contract of contracts){
   if(!contract.contract_number)throw Error("У каждого договора должен быть номер");
   if(contract.completed&&(!contract.acceptance_signed_at||
       !contract.contract_document_ref||!contract.signed_final_act_ref))
     throw Error("Для завершённого договора нужны дата, договор и подписанный итоговый акт");
 }
 const payload={
   expected_version:referenceVersion,
   source_ref:sourceRef,
   snapshot:{schema_version:"completed-contract-references-v1",
     as_of_date:asOf,completeness,owner_confirmed:ownerConfirmed,contracts}
 };
 const saved=await call("/api/saas/qualification/references",{method:"POST",body:payload});
 const refreshed=await call("/api/saas/qualification/references");
 displayReferences(refreshed);
 return {saved_version:saved.fact_version,current_snapshot:refreshed};
});
bind("read-profile",async()=>{
 const r=await call("/api/saas/profile"),p=r.profile||{},c=p.criteria||{},q=p.qualification||{},m=p.commercial||{};
 for(const k of ["categories","regions","keywords"])document.getElementById(k).value=(c[k]||[]).join(", ");
 document.getElementById("price-min").value=c.price_min??"";
 document.getElementById("price-max").value=c.price_max??"";
 document.getElementById("licenses").value=(q.licenses||[]).join(", ");
 document.getElementById("sro").value=(q.sro_approvals||[]).join(", ");
 document.getElementById("margin").value=m.target_margin_percent??20;return r;
});
bind("save-profile",()=>call("/api/saas/profile",{method:"PUT",body:{
 criteria:{categories:split("categories"),regions:split("regions"),keywords:split("keywords"),price_min:num("price-min"),price_max:num("price-max")},
 commercial:{target_margin_percent:num("margin")},
 qualification:{licenses:split("licenses"),sro_approvals:split("sro")},risk_preferences:{tolerance:"medium"}
}}));
bind("upload-doc",()=>{
 const file=document.getElementById("doc-file").files[0];if(!file)throw Error("Выберите PDF");
 const body=new FormData();body.set("document_key",val("doc-key"));body.set("document_type",val("doc-type"));body.set("display_name",val("doc-title"));body.set("file",file);
 return call("/api/saas/documents",{method:"POST",body,upload:true});
});
bind("screen",()=>call("/api/saas/screen",{method:"POST",body:{reference:val("reference")}}));
bind("import-eis",async()=>{
 const r=await call("/api/saas/runs/from-eis",{method:"POST",body:{reference:val("reference")}});
 document.getElementById("run-id").value=r.run_id;return r;
});
bind("append-files",()=>{
 const fs=document.getElementById("tender-files").files;if(!fs.length)throw Error("Добавьте документацию");
 const body=new FormData();for(const file of fs)body.append("files",file);
 return call("/api/saas/runs/"+encodeURIComponent(val("run-id"))+"/files",{method:"POST",body,upload:true});
});
bind("create-run",async()=>{
 const fs=document.getElementById("tender-files").files; if(!fs.length)throw Error("Добавьте документацию");
 const body=new FormData();body.set("tender_title",val("tender-title"));body.set("tender_category","Не определена");
 if(val("procurement-customer"))body.set("procurement_customer_name",val("procurement-customer"));
 for(const file of fs)body.append("files",file);
 const r=await call("/api/saas/runs",{method:"POST",body,upload:true});
 document.getElementById("run-id").value=r.run_id;return r;
});
bind("analyze-run",()=>call("/api/saas/runs/"+encodeURIComponent(val("run-id"))+"/analyze",{method:"POST"}));
bind("report-run",()=>call("/api/saas/runs/"+encodeURIComponent(val("run-id"))+"/report"));
bind("qualify-run",()=>call("/api/saas/runs/"+encodeURIComponent(val("run-id"))+"/qualification"));
bind("screen-run",()=>call("/api/saas/runs/"+encodeURIComponent(val("run-id"))+"/screen",{method:"POST"}));
bind("me",()=>call("/api/saas/me"));
bind("packages",()=>call("/api/saas/packages",{auth:false}));
bind("usage",()=>call("/api/saas/usage"));
bind("invite-member",()=>call("/api/saas/invitations",{method:"POST",body:{
 role:val("invite-role"),acquisition_channel:"referral"
}}));
bind("members-list",()=>call("/api/saas/members"));
bind("revoke-member",()=>call("/api/saas/members/"+encodeURIComponent(val("revoke-member-id"))+"/revoke",{method:"POST"}));

// All portfolio state belongs to the current in-memory SaaS session.
let companyIdentity=null, companyItems=[], companyMore=false, companyOffset=0;
let companyCase=null, companyProfile=null, companyEvidence=[], pendingCompanyDecision=null;
let discoveryEnabled=false, discoveryRun=null, discoveryProfile=null;
const el=id=>document.getElementById(id);
function blankSelect(id, label){
 const select=el(id);select.replaceChildren();
 const opt=document.createElement("option");opt.value="";opt.textContent=label;select.append(opt);
}
function resetCompanyDetail(){
 companyCase=null;companyProfile=null;companyEvidence=[];pendingCompanyDecision=null;
 el("company-detail").hidden=true;el("company-case-state").textContent="";
 el("company-history").textContent="";el("company-profile-state").textContent="";
 el("company-evidence-state").textContent="";el("company-evidence-result").textContent="";
 el("company-evidence-result").hidden=true;blankSelect("company-evidence","Выберите привязку");
 el("company-rationale").value="";el("company-defer").value="";el("company-confirm").checked=false;
 el("company-action").value="GO";el("company-run-id").value="";
}
function clearCompany(){
 companyIdentity=null;companyItems=[];companyMore=false;companyOffset=0;
 resetCompanySearch();
 blankSelect("company-case","Выберите закупку");resetCompanyDetail();
 el("company-identity").textContent="Войдите и загрузите портфель.";el("company-count").textContent="";
 el("company-registry").value="";syncCompanyControls();
}
function clearSession(){
 token="";sessionEpoch++;legalVersions=null;referenceVersion=null;
 // Clear also the legacy profile, references, file forms, and report output.
 for(const field of document.querySelectorAll("input,textarea,select")){
   if(field.type==="checkbox"||field.type==="radio")field.checked=field.defaultChecked;
   else if(field.tagName==="SELECT")field.selectedIndex=0;
   else field.value=field.type==="file"?"":field.defaultValue;
 }
 el("references-contracts").replaceChildren();el("reference-state").textContent="Список пока не загружен";
 el("qualification-panel").hidden=true;el("qualification-verdict").textContent="";el("qualification-source-note").textContent="";
 el("result").textContent="Данные предыдущей сессии очищены.";clearCompany();
}
function companyCanWrite(){return companyIdentity?.legal_accepted===true&&["owner","admin","analyst"].includes(companyIdentity.role)}
function companyCanDecide(){return companyIdentity?.legal_accepted===true&&["owner","admin"].includes(companyIdentity.role)}
function syncCompanyControls(){
 const read=Boolean(companyIdentity?.legal_accepted), detail=Boolean(companyCase);
 el("company-more").disabled=uiBusy||!read||!companyMore;
 el("company-save-panel").hidden=!companyCanWrite();el("company-save").disabled=uiBusy||!companyCanWrite();
 el("company-open").disabled=uiBusy||!read||!el("company-case").value;
 el("company-decision-panel").hidden=!detail||!companyCanDecide();
 el("company-decide").disabled=uiBusy||!detail||!companyCanDecide();
 el("company-evidence-panel").hidden=!detail||!companyCanWrite();
 el("company-bind").disabled=uiBusy||!detail||!companyCanWrite()||companyProfile?.profile_state!=="ACTIVE";
 el("company-read-evidence").disabled=uiBusy||!detail||!companyCanWrite()||!el("company-evidence").value;
 syncCompanySearchControls();
}
function requireCompany(){if(!companyIdentity?.legal_accepted)throw Error("Загрузите портфель после подтверждения условий пилота");return companyIdentity}
function casePath(){requireCompany();if(!companyCase)throw Error("Откройте карточку");return "/api/saas/company-portfolio/cases/"+encodeURIComponent(companyCase.case_id)}
function companyCaseText(item){return (item.registry_number||"Номер не указан")+" · "+(item.decision?.action||"Не решено")+" · v"+item.revision}
function renderCompanyItems(){
 blankSelect("company-case","Выберите закупку");
 for(const item of companyItems){const opt=document.createElement("option");opt.value=item.case_id;opt.textContent=companyCaseText(item);el("company-case").append(opt)}
 if(companyCase&&companyItems.some(x=>x.case_id===companyCase.case_id))el("company-case").value=companyCase.case_id;
 el("company-count").textContent="Загружено карточек: "+companyItems.length+(companyMore?" (есть ещё)":"");
}
async function loadCompanyPage({restart=true}={}){
 if(restart){clearCompany();const me=await call("/api/saas/me");
   companyIdentity=me;el("company-identity").textContent=me.company_name+" · "+me.role;
   if(!me.legal_accepted){el("company-count").textContent="Сначала подтвердите условия пилота.";return {portfolio_loaded:false}};
 }
 const identity=requireCompany();const page=await call("/api/saas/company-portfolio/cases?offset="+companyOffset+"&limit=50");
 if(page.customer_id!==identity.customer_id){clearSession();throw Error("Ответ относится к другой компании. Сессия очищена.")}
 const known=new Set(companyItems.map(x=>x.case_id));companyItems.push(...page.items.filter(x=>!known.has(x.case_id)));
 companyOffset+=page.items.length;companyMore=Boolean(page.has_more);renderCompanyItems();return {loaded:companyItems.length,has_more:companyMore};
}
async function loadCompanyEvidence(path){
 const profile=await call("/api/saas/company-portfolio/search-context");
 if(profile.customer_id!==requireCompany().customer_id){clearSession();throw Error("Профиль другой компании. Сессия очищена.")}
 const page=await call(path+"/evidence?limit=50");
 if(page.items.some(x=>x.case_id!==companyCase.case_id)){clearSession();throw Error("Ответ не соответствует карточке. Сессия очищена.")}
 companyProfile=profile;companyEvidence=page.items;el("company-profile-state").textContent="Профиль: "+profile.profile_state+" · версия "+(profile.profile_version??"—");
 blankSelect("company-evidence","Выберите привязку");
 for(const source of companyEvidence){const opt=document.createElement("option");opt.value=source.binding_id;opt.textContent=source.run_id+" · профиль v"+source.profile_version+" · "+source.profile_state;el("company-evidence").append(opt)}
 el("company-evidence-state").textContent=companyEvidence.length===0?"Нет привязок":(page.has_more?"Первые 50 привязок":"Привязок: "+companyEvidence.length);
}
async function loadCompanyCase(id){
 requireCompany();resetCompanyDetail();
 if(!companyItems.some(x=>x.case_id===id))throw Error("Выберите карточку из своего портфеля");
 const path="/api/saas/company-portfolio/cases/"+encodeURIComponent(id);
 const item=await call(path);if(item.case_id!==id)throw Error("Ответ не соответствует карточке");
 const history=await call(path+"/decisions?limit=50");
 companyCase=item;companyItems=companyItems.map(x=>x.case_id===id?item:x);renderCompanyItems();
 el("company-case-state").textContent=requireCompany().company_name+" · "+companyCaseText(item)+" · только внутреннее решение";
 el("company-history").textContent=history.items.map(x=>"v"+x.revision+" · "+x.action+" · "+x.decided_at+"\\n"+x.rationale).join("\\n\\n")+(history.has_more?"\\nПервые 50 решений":"")||"История пуста";
 el("company-detail").hidden=false;
 if(companyCanWrite())await loadCompanyEvidence(path);
 return {case_id:item.case_id,revision:item.revision};
}
bind("company-load",()=>loadCompanyPage());
bind("company-more",()=>loadCompanyPage({restart:false}));
el("company-case").addEventListener("change",()=>{resetCompanyDetail();syncCompanyControls()});
el("company-evidence").addEventListener("change",()=>{el("company-evidence-result").hidden=true;el("company-evidence-result").textContent="";syncCompanyControls()});
bind("company-open",()=>loadCompanyCase(val("company-case")));
bind("company-save",async()=>{
 if(!companyCanWrite())throw Error("Недостаточно прав");
 const number=val("company-registry");if(!/^[0-9]{19,20}$/.test(number))throw Error("Введите 19 или 20 цифр номера ЕИС");
 const saved=await call("/api/saas/company-portfolio/cases",{method:"POST",body:{registry_number:number}});
 el("company-registry").value="";await loadCompanyPage();return {saved_case: saved.case_id};
});
bind("company-decide",async()=>{
 if(!companyCanDecide())throw Error("Недостаточно прав");
 if(!el("company-confirm").checked)throw Error("Подтвердите решение для текущей карточки");
 const path=casePath();const id=companyCase.case_id;
 const action=val("company-action"), rationale=val("company-rationale");
 if(!rationale||!['GO','NO_GO','DEFER'].includes(action))throw Error("Укажите действие и обоснование");
 let deferred=null;
 if(action==="DEFER"){
   const value=val("company-defer");const date=new Date(value);
   if(!value||!Number.isFinite(date.getTime())||date.getTime()<=Date.now())throw Error("Укажите будущую дату отсрочки");
   deferred=date.toISOString();
 }
 const body={action,rationale,deferred_until:deferred,expected_revision:companyCase.revision};
 const signature=JSON.stringify([sessionEpoch,id,body]);
 if(!pendingCompanyDecision||pendingCompanyDecision.signature!==signature){
   if(!globalThis.crypto?.randomUUID)throw Error("Для сохранения решения требуется защищённый HTTPS-контекст");
   pendingCompanyDecision={signature,key:globalThis.crypto.randomUUID()};
 }
 let saved;
 try{saved=await call(path+"/decisions",{method:"POST",body:{...body,idempotency_key:pendingCompanyDecision.key}})}
 catch(error){
   if(error.status===409){resetCompanyDetail();throw Error("Решение изменилось или конфликтует. Откройте карточку заново и подтвердите новое решение.")}
   // An uncertain network result keeps the same key for an explicit identical retry.
   el("company-confirm").checked=false;throw error;
 }
 pendingCompanyDecision=null;el("company-confirm").checked=false;
 // Never silently overwrite a more recent revision or present a successful refresh on failure.
 try{await loadCompanyCase(id)}catch(error){
   resetCompanyDetail();if([401,402,403].includes(error.status))clearSession();
   else el("company-count").textContent="Решение сохранено, откройте карточку заново для обновления.";
   return {saved_revision:saved.revision,refresh_required:true};
 }
 return {saved_revision:saved.revision,action:saved.action,external_submission_allowed:false};
});
bind("company-bind",async()=>{
 if(!companyCanWrite()||companyProfile?.profile_state!=="ACTIVE")throw Error("Нужен действующий профиль компании");
 const runId=val("company-run-id");if(!runId)throw Error("Укажите ID собственного прогона");
 const path=casePath();const result=await call(path+"/evidence",{method:"POST",body:{run_id:runId,expected_profile_version:companyProfile.profile_version}});
 if(result.case_id!==companyCase.case_id)throw Error("Ответ не соответствует карточке");
 el("company-run-id").value="";await loadCompanyEvidence(path);
 return {binding_id:result.binding_id,profile_version:result.profile_version,current_live_notice_status_verified:false};
});
bind("company-read-evidence",async()=>{
 if(!companyCanWrite())throw Error("Недостаточно прав");
 el("company-evidence-result").hidden=true;el("company-evidence-result").textContent="";
 const id=val("company-evidence");if(!companyEvidence.some(x=>x.binding_id===id))throw Error("Выберите привязку из карточки");
 const result=await call(casePath()+"/evidence/"+encodeURIComponent(id));
 if(result.case_id!==companyCase.case_id||result.binding_id!==id)throw Error("Ответ не соответствует привязке");
 el("company-evidence-state").textContent=result.archived_source_snapshot_verified===true?"Сохранённый архив проверен. Актуальный правовой статус не подтверждён.":"Оригиналы не подтверждены";
 el("company-evidence-result").textContent=JSON.stringify({report_status:result.report_status,profile_state:result.profile_state,profile_version:result.profile_version,current_profile_version:result.current_profile_version,qualification_as_of:result.qualification_as_of,screening:result.screening,qualification:result.qualification},null,2);
 el("company-evidence-result").hidden=false;return result;
});
function resetCompanySearch(){
 discoveryRun=null;discoveryProfile=null;discoveryEnabled=false;
 el("company-search-state").textContent="Загрузите портфель и состояние поиска.";
 el("company-search-receipts").textContent="";blankSelect("company-search-candidate","Выберите кандидата");
}
function syncCompanySearchControls(){
 const owner=companyCanDecide(), read=Boolean(companyIdentity?.legal_accepted);
 el("company-search-refresh").disabled=uiBusy||!read;
 el("company-search-start").disabled=uiBusy||!owner||!discoveryEnabled||discoveryProfile?.profile_state!=="ACTIVE";
 el("company-search-run").disabled=uiBusy||!owner||!discoveryEnabled||!discoveryRun||!["PENDING","IN_PROGRESS"].includes(discoveryRun.status)||discoveryRun.plan.profile_version!==discoveryProfile?.profile_version;
 el("company-search-accept").disabled=uiBusy||!companyCanWrite()||!discoveryRun||!el("company-search-candidate").value;
}
function acceptDiscoveryReply(result){
 if(result&&result.customer_id!==requireCompany().customer_id){clearSession();throw Error("Ответ поиска относится к другой компании")}
 discoveryRun=result;blankSelect("company-search-candidate","Выберите кандидата");
 if(!result){el("company-search-state").textContent=discoveryEnabled?"Поиск пока не подготовлен":"Поиск выключен";el("company-search-receipts").textContent="";return}
 const state={PENDING:"Ожидает выполнения",IN_PROGRESS:"Выполняется",COMPLETED:"Выполнен заданный поиск",PARTIAL:"Выдача неполная",STALE_PROFILE:"Профиль изменился",EXPIRED_WINDOW:"Окно поиска истекло"}[result.status]||"Статус требует проверки";
 el("company-search-state").textContent=state+" · "+result.completed_steps+"/"+result.plan.steps.length+" · профиль v"+result.plan.profile_version+" · "+result.run_day+(result.discovery_incomplete?" · полнота не подтверждена":"")+(discoveryEnabled?"":" · новые запросы отключены");
 el("company-search-receipts").textContent=result.step_receipts.map(x=>x.query+" · "+(x.region||"все регионы")+" · "+x.outcome+" · кандидатов "+x.candidates.length+(x.coverage_complete?"":" · неполное покрытие")).join("\\n");
 for(const item of result.candidates){const option=document.createElement("option");option.value=item.registry_number;option.textContent=item.registry_number+" · "+item.title;el("company-search-candidate").append(option)}
}
bind("company-search-refresh",async()=>{
 requireCompany();resetCompanySearch();const current=await call("/api/saas/company-portfolio/discovery/latest");
 discoveryEnabled=current.enabled===true;
 const profile=await call("/api/saas/company-portfolio/search-context");
 if(profile.customer_id!==requireCompany().customer_id){clearSession();throw Error("Ответ профиля относится к другой компании")}
 discoveryProfile=profile;acceptDiscoveryReply(current.run);return {enabled:discoveryEnabled,status:discoveryRun?.status||"NOT_STARTED",profile_version:profile.profile_version};
});
bind("company-search-start",async()=>{
 if(!companyCanDecide()||!discoveryEnabled||discoveryProfile?.profile_state!=="ACTIVE")throw Error("Поиск недоступен");
 const result=await call("/api/saas/company-portfolio/discovery/runs",{method:"POST",body:{expected_profile_version:discoveryProfile.profile_version}});
 acceptDiscoveryReply(result);return {run_id:result.run_id,status:result.status};
});
bind("company-search-run",async()=>{
 if(!companyCanDecide()||!discoveryEnabled||!discoveryRun)throw Error("Поиск недоступен");
 for(let i=0;i<8&&["PENDING","IN_PROGRESS"].includes(discoveryRun.status);i++){
   const old=discoveryRun.completed_steps, id=discoveryRun.run_id;
   const result=await call("/api/saas/company-portfolio/discovery/runs/"+encodeURIComponent(id)+"/step",{method:"POST",body:{expected_step:old}});
   if(result.run_id!==id){clearSession();throw Error("Ответ не соответствует запуску")}
   acceptDiscoveryReply(result);
   if(result.completed_steps<=old)break;
 }
 return {status:discoveryRun.status,completed_steps:discoveryRun.completed_steps,discovery_incomplete:discoveryRun.discovery_incomplete,candidates:discoveryRun.candidates.length};
});
el("company-search-candidate").addEventListener("change",syncCompanySearchControls);
bind("company-search-accept",async()=>{
 const number=val("company-search-candidate");
 if(!companyCanWrite()||!discoveryRun?.candidates.some(x=>x.registry_number===number))throw Error("Выберите кандидата из своего поиска");
 const saved=await call("/api/saas/company-portfolio/cases",{method:"POST",body:{registry_number:number}});
 // Preserve the selected completed discovery while refreshing the same company's portfolio.
 const snapshot={run:discoveryRun,profile:discoveryProfile,enabled:discoveryEnabled,customer:requireCompany().customer_id};
 await loadCompanyPage();
 if(companyIdentity?.customer_id===snapshot.customer){discoveryEnabled=snapshot.enabled;discoveryProfile=snapshot.profile;acceptDiscoveryReply(snapshot.run)}
 return {saved_case:saved.case_id,source_verified:false};
});

syncCompanyControls();
</script></body></html>"""
