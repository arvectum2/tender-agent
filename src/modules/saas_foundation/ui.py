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
<label>Очередь руководителя<select id="company-inbox-filter"><option value="attention">Требуют внимания</option><option value="undecided">Без решения</option><option value="deferred_due">Пора вернуться к решению</option><option value="deferred_future">Отложены</option><option value="go">GO</option><option value="no_go">NO GO</option><option value="all">Все сохранённые</option></select></label><button id="company-inbox-load" disabled>Показать очередь</button><p id="company-inbox-summary" aria-live="polite"></p><p>Только сохранённые закупки и внутренние решения. Срок возврата к решению не является сроком подачи заявки.</p>
<button id="company-metrics-load" disabled>Коммерческая статистика</button><pre id="company-metrics-result" hidden></pre>
<div id="company-save-panel" hidden><label>Номер ЕИС<input id="company-registry" inputmode="numeric" maxlength="20" autocomplete="off"></label>
<button id="company-save">Добавить ссылку в портфель</button><label>Оригинальная ссылка B2B-Center / Workspace<input id="company-commercial-url" type="url" maxlength="650" autocomplete="off"></label><button id="company-commercial-save">Добавить коммерческую закупку</button></div>
<details><summary>Поиск по сохранённому профилю компании</summary>
<p>Пилотный поиск ЕИС 44-ФЗ и выбранных публичных коммерческих индексов: до 8 шагов за день и до 10 карточек на шаг. Не заменяет полное исследование рынка.</p>
<label><input id="company-search-eis" type="checkbox" checked style="width:auto"> ЕИС 44-ФЗ</label><label>Коммерческий индекс (необязательно)<select id="company-search-index"><option value="">Не подключать</option></select></label><button id="company-search-refresh">Состояние поиска</button><button id="company-search-start" disabled>Подготовить поиск</button><button id="company-search-run" disabled>Выполнить оставшиеся шаги</button>
<p id="company-search-state" role="status">Загрузите портфель и состояние поиска.</p>
<pre id="company-search-receipts"></pre>
<label>Найденная закупка<select id="company-search-candidate"><option value="">Выберите кандидата</option></select></label><button id="company-search-accept" disabled>Добавить кандидата в портфель</button>
<p>Добавление сохраняет только ссылку на закупку. Оригиналы и квалификация проверяются отдельно.</p>
<h3>Ежедневный поиск</h3><button id="company-schedule-refresh">Проверить расписание</button><p id="company-schedule-state" aria-live="polite"></p>
<label>Час запуска (Москва)<input id="company-schedule-hour" type="number" min="0" max="23" step="1" value="8"></label>
<label><input id="company-schedule-confirm" type="checkbox" style="width:auto"> Разрешаю ежедневный публичный поиск по текущей версии профиля и выбранным выше источникам. Выход из кабинета не отключает расписание.</label>
<button id="company-schedule-enable" disabled>Сохранить и разрешить поиск</button><button id="company-schedule-disable" disabled>Отключить расписание</button>
<p>Без автоматической подачи заявок. Изменение профиля требует нового подтверждения. Фактическое время зависит от серверного планировщика.</p></details>
<p id="company-count" aria-live="polite"></p>
<label>Карточка<select id="company-case"><option value="">Выберите закупку</option></select></label>
<button id="company-open">Открыть карточку</button>
<section id="cost-norm-panel" hidden><h3>Корпоративные нормативы</h3><p>Внутренние решения руководителя. Не применяются автоматически в сметах. Источники — заявленные фактические затраты, не подтверждённая бухгалтерская отчётность.</p>
<button id="cost-norm-load" disabled>Загрузить каталог</button><button id="cost-norm-prev" disabled>Назад</button><button id="cost-norm-next" disabled>Далее</button><div id="cost-norm-catalog"></div>
<label>Норматив<select id="cost-norm-select"></select></label><button id="cost-norm-history" disabled>История версий</button><button id="cost-norm-history-prev" disabled>Назад по истории</button><button id="cost-norm-history-next" disabled>Далее по истории</button><div id="cost-norm-history-result"></div>
<div id="cost-norm-manager" hidden><label>Причина отзыва<textarea id="cost-norm-withdraw-note" maxlength="2000"></textarea></label><label><input type="checkbox" id="cost-norm-withdraw-confirm"> Подтверждаю отзыв выбранного действующего норматива.</label><button id="cost-norm-withdraw" disabled>Отозвать норматив</button></div>
<p id="cost-norm-status" aria-live="polite"></p></section><div id="company-detail" hidden>
<p id="company-case-state"></p><p id="company-case-url"></p><pre id="company-history" aria-live="polite"></pre>
<div id="company-decision-panel" hidden>
<div class="grid"><label>Решение<select id="company-action"><option value="GO">GO</option><option value="NO_GO">NO GO</option><option value="DEFER">Отложить</option></select></label>
<label>Отложить до (местное время браузера)<input id="company-defer" type="datetime-local"></label></div>
<label>Обоснование<textarea id="company-rationale" maxlength="2000"></textarea></label>
<label><input id="company-confirm" type="checkbox" style="width:auto"> Подтверждаю решение для указанной компании и закупки. Это не подача заявки.</label>
<button id="company-decide">Сохранить решение</button></div>
<section><h3>Подготовка, подача и результат</h3><button id="company-lifecycle-load" disabled>Обновить состояние заявки</button><p id="company-lifecycle-state" aria-live="polite"></p><div id="company-lifecycle-panel" hidden><pre id="company-lifecycle-current"></pre><div id="company-lifecycle-editor" hidden><label>Состояние<select id="company-lifecycle-stage"></select></label><label>Обоснование<textarea id="company-lifecycle-rationale" maxlength="2000"></textarea></label><div id="company-lifecycle-external" hidden><label>Номер квитанции или ссылка на протокол<input id="company-lifecycle-ref" maxlength="500"></label><label>Дата события (местное время браузера)<input id="company-lifecycle-date" type="datetime-local"></label></div><label><input type="checkbox" id="company-lifecycle-confirm" style="width:auto"> Подтверждаю запись сведений для этой компании и закупки. Это не действие на ЭТП.</label><button id="company-lifecycle-save" disabled>Записать состояние</button></div><button id="company-lifecycle-history" disabled>История событий</button><pre id="company-lifecycle-history-result" hidden></pre><section id="company-readiness-panel" hidden><h4>Документальное подтверждение READY</h4><button id="company-readiness-load" disabled>Проверить матрицу готовности</button><p id="company-readiness-state" aria-live="polite"></p><pre id="company-readiness-result" hidden></pre><label><input type="checkbox" id="company-readiness-confirm" style="width:auto"> Подтверждаю частичное покрытие требований, не полную квалификацию.</label><button id="company-readiness-bind" disabled>Связать проверку с READY</button></section><section id="company-event-file-panel" hidden><h4>Квитанции и протоколы</h4><label>Событие<select id="company-event-file-event"></select></label><button id="company-event-file-load" disabled>Проверить файл</button><p id="company-event-file-state" aria-live="polite"></p><pre id="company-event-file-result" hidden></pre><div id="company-event-file-editor" hidden><label>Файл (PDF, DOCX, XLSX; до 2 МБ)<input id="company-event-file-input" type="file" accept=".pdf,.docx,.xlsx"></label><label><input id="company-event-file-confirm" type="checkbox" style="width:auto"> Копия предоставлена сотрудником; происхождение на ЭТП не проверено.</label><button id="company-event-file-save" disabled>Сохранить файл события</button></div><button id="company-event-file-download" disabled>Скачать проверенную копию</button></section><p>Готовность и результаты указываются сотрудником. Оригиналы квитанций и протоколов независимо не проверены.</p></div></section>
<section id="company-price-panel" hidden><h3>Экономика предложения · PRICE-01</h3><p>Явные допущения. Укажите ноль, если расход отсутствует. Не учитывайте одну статью дважды. Не налоговый расчёт, не рекомендация ставки и не прогноз победы.</p><label>Режим расчёта<select id="price-mode"><option value="aggregate">Итоговые суммы</option><option value="itemized">Постатейная смета</option></select></label><div id="price-itemized-panel" hidden><p>До 60 строк. Укажите источник каждой ставки. Отсутствующие категории отметьте нулём.</p><label>Строка<select id="price-line-select"></select></label><button id="price-line-edit">Редактировать выбранную</button><button id="price-line-remove">Удалить выбранную</button><div id="price-line-list"></div><label>Категория<select id="price-line-category"><option value="external_direct_rub">Прямые расходы</option><option value="own_labor_rub">Собственный труд</option><option value="cash_overhead_rub">Накладные расходы</option><option value="reserve_rub">Резерв</option><option value="fixed_platform_fees_rub">Сборы ЭТП</option><option value="guarantee_financing_cost_rub">Финансирование</option></select></label><label>Наименование<input id="price-line-title" maxlength="160"></label><label>Единица<input id="price-line-unit" maxlength="24"></label><label>Количество<input id="price-line-quantity" inputmode="decimal" maxlength="14"></label><label>Ставка, ₽<input id="price-line-rate_rub" inputmode="decimal" maxlength="15"></label><label>Источник<select id="price-line-source_kind"><option value="ASSUMPTION">Допущение</option><option value="USER_REPORTED_QUOTE">КП со слов сотрудника</option><option value="USER_REPORTED_ACTUAL">Фактические расходы со слов сотрудника</option></select></label><label>Обоснование<input id="price-line-source_note" maxlength="500"></label><button id="price-line-add">Добавить строку</button><button id="price-line-cancel">Отменить редактирование</button><p id="price-line-status"></p><label><input type="checkbox" id="price-zero-external_direct_rub" style="width:auto"> Прямые расходы: 0 ₽</label><label><input type="checkbox" id="price-zero-own_labor_rub" style="width:auto"> Собственный труд: 0 ₽</label><label><input type="checkbox" id="price-zero-cash_overhead_rub" style="width:auto"> Накладные расходы: 0 ₽</label><label><input type="checkbox" id="price-zero-reserve_rub" style="width:auto"> Резерв: 0 ₽</label><label><input type="checkbox" id="price-zero-fixed_platform_fees_rub" style="width:auto"> Сборы ЭТП: 0 ₽</label><label><input type="checkbox" id="price-zero-guarantee_financing_cost_rub" style="width:auto"> Финансирование: 0 ₽</label><label><input type="checkbox" id="price-no-double" style="width:auto"> Подтверждаю отсутствие двойного учёта.</label><div id="price-itemized-result"></div></div><div id="price-aggregate-panel" class="grid"><label>Прямые расходы, ₽ (включая оплачиваемый труд)<input id="price-external_direct_rub" inputmode="decimal" maxlength="15" autocomplete="off"></label><label>Дополнительная стоимость собственного труда, ₽<input id="price-own_labor_rub" inputmode="decimal" maxlength="15" autocomplete="off"></label><label>Денежные накладные расходы, ₽<input id="price-cash_overhead_rub" inputmode="decimal" maxlength="15" autocomplete="off"></label><label>Резерв риска, ₽<input id="price-reserve_rub" inputmode="decimal" maxlength="15" autocomplete="off"></label><label>Фиксированные сборы ЭТП, ₽<input id="price-fixed_platform_fees_rub" inputmode="decimal" maxlength="15" autocomplete="off"></label><label>Стоимость финансирования и гарантий, ₽ (не сумма обеспечения)<input id="price-guarantee_financing_cost_rub" inputmode="decimal" maxlength="15" autocomplete="off"></label></div><div class="grid"><label>Предполагаемый налог от выручки, %<input id="price-revenue_tax_percent" inputmode="decimal" maxlength="15" autocomplete="off"></label><label>Переменная комиссия от выручки, %<input id="price-variable_platform_fee_percent" inputmode="decimal" maxlength="15" autocomplete="off"></label><label>Минимальная прибыль, ₽<input id="price-minimum_profit_rub" inputmode="decimal" maxlength="15" autocomplete="off"></label><label>Целевая прибыль, ₽<input id="price-target_profit_rub" inputmode="decimal" maxlength="15" autocomplete="off"></label><label>Ручной предел цены, ₽ (необязательно)<input id="price-reference_ceiling_rub" inputmode="decimal" maxlength="15" autocomplete="off"></label></div><label>Дополнительные цены, ₽ (до 8, каждая с новой строки)<textarea id="price-manual" maxlength="160"></textarea></label><label>Обоснование расходов, источники и допущения<textarea id="price-note" maxlength="2000"></textarea></label><label><input id="price-confirm" type="checkbox" style="width:auto"> Подтверждаю, что это сценарные допущения, а не утверждённая цена заявки.</label><button id="price-preview" disabled>Рассчитать</button><button id="price-history" disabled>Загрузить историю</button><p id="price-status" aria-live="polite"></p><p id="price-totals"></p><div id="price-results"></div><label id="price-save-confirm-label" hidden><input id="price-save-confirm" type="checkbox" style="width:auto"> Сохранить расчёт как новую версию для этой компании и закупки.</label><button id="price-save" disabled>Сохранить версию</button><label>Версия<select id="price-version"></select></label><button id="price-show-version" disabled>Показать сохранённую версию</button><pre id="price-version-detail" hidden></pre><section id="actual-panel" hidden><h4>План-факт сохранённой сметы</h4><p>Накопленные затраты на дату, не журнал платежей. Не суммируйте версии. Незаявленные строки не равны нулю; суммы и оплата независимо не проверены.</p><button id="actual-load" disabled>Загрузить план и историю факта</button><div id="actual-editor" hidden><label>Дата среза<input id="actual-date" type="date"></label><label>Плановая строка<select id="actual-line"></select></label><p id="actual-line-plan"></p><label>Фактическое количество (в единицах плана)<input id="actual-quantity" inputmode="decimal" maxlength="14"></label><label>Фактическая ставка, ₽<input id="actual-rate" inputmode="decimal" maxlength="15"></label><label>Источник факта<input id="actual-source" maxlength="500"></label><button id="actual-line-save">Записать факт строки</button><button id="actual-line-clear">Снять наблюдение</button><div id="actual-observations"></div><h4>Внеплановые расходы</h4><label>Категория<select id="actual-extra-category"><option value="external_direct_rub">Прямые расходы</option><option value="own_labor_rub">Собственный труд</option><option value="cash_overhead_rub">Накладные расходы</option><option value="reserve_rub">Резерв</option><option value="fixed_platform_fees_rub">Сборы ЭТП</option><option value="guarantee_financing_cost_rub">Финансирование</option></select></label><label>Название<input id="actual-extra-title" maxlength="160"></label><label>Единица<input id="actual-extra-unit" maxlength="24"></label><label>Количество<input id="actual-extra-quantity" inputmode="decimal" maxlength="14"></label><label>Ставка, ₽<input id="actual-extra-rate_rub" inputmode="decimal" maxlength="15"></label><label>Источник<input id="actual-extra-source_note" maxlength="500"></label><button id="actual-extra-add">Добавить расход</button><button id="actual-extra-cancel">Очистить черновик</button><label>Внеплановая строка<select id="actual-extra-select"></select></label><button id="actual-extra-remove">Удалить расход</button><div id="actual-extra-list"></div><label>Обоснование среза<textarea id="actual-note" maxlength="2000"></textarea></label><label><input type="checkbox" id="actual-confirm" style="width:auto"> Подтверждаю накопленный пользовательский факт, не декларацию оплаты.</label><label><input type="checkbox" id="actual-no-double" style="width:auto"> Подтверждаю отсутствие двойного учёта.</label><button id="actual-preview">Рассчитать отклонения</button><div id="actual-result"></div><label id="actual-save-label" hidden><input type="checkbox" id="actual-save-confirm" style="width:auto"> Сохранить новую неизменяемую версию факта.</label><button id="actual-save" disabled>Сохранить факт</button><label>Сохранённый срез<select id="actual-history"></select></label><button id="actual-show" disabled>Просмотреть срез</button><div id="actual-history-result"></div><section id="actual-evidence-panel" hidden><h4>Документы фактических затрат</h4><p>Одна пользовательская копия на строку сохранённого среза. Сумма, подлинность, оплата и исполнение договора независимо не подтверждаются.</p><label>Заявленная позиция<select id="actual-evidence-row"></select></label><button id="actual-evidence-load" disabled>Проверить документ</button><p id="actual-evidence-status" aria-live="polite"></p><pre id="actual-evidence-result" hidden></pre><div id="actual-evidence-editor" hidden><label>Вид документа<select id="actual-evidence-kind"><option value="">Выберите вид</option><option value="INVOICE">Счёт</option><option value="CONTRACT">Договор</option><option value="TIMESHEET">Табель трудозатрат</option><option value="ACCEPTANCE_ACT">Акт выполненных работ</option><option value="PAYMENT_RECORD">Платёжный документ</option><option value="OTHER">Прочее</option></select></label><label>Копия PDF, DOCX или XLSX до 2 МБ<input type="file" id="actual-evidence-file" accept=".pdf,.docx,.xlsx"></label><label><input type="checkbox" id="actual-evidence-confirm" style="width:auto"> Привязать пользовательскую копию без возможности замены к выбранному срезу и строке. Источник, сумма и оплата не проверены.</label><button id="actual-evidence-save" disabled>Прикрепить документ</button></div><button id="actual-evidence-download" disabled>Скачать проверенные байты</button></section></div><p id="actual-status" aria-live="polite"></p></section><section id="actual-sample-panel" hidden><h4>Сопоставимые фактические затраты</h4><p>Выберите последнюю сохранённую строку факта в карточке, затем добавьте строки из других закупок. До 20 закупок; одинаковая работа, категория и единица. Это описательная статистика, не утверждённый норматив.</p><button id="actual-sample-add" disabled>Добавить выбранную строку факта</button><p id="actual-sample-status" aria-live="polite"></p><div id="actual-sample-list"></div><label>Исключить закупку<select id="actual-sample-remove-select"></select></label><button id="actual-sample-remove" disabled>Исключить</button><button id="actual-sample-clear" disabled>Очистить выборку</button><label><input type="checkbox" id="actual-sample-comparable" style="width:auto"> Подтверждаю сопоставимость заявленных строк.</label><label><input type="checkbox" id="actual-sample-distinct" style="width:auto"> Одна накопительная строка на закупку; без повторного учёта.</label><button id="actual-sample-preview" disabled>Сравнить фактические затраты</button><div id="actual-sample-result" aria-live="polite"></div></section><section id="cost-norm-proposal-panel" hidden><h4>Проект корпоративного норматива по выбранной выборке</h4><p>Количество и ставку задаёт человек, а не модель. Выберите сопоставимые строки выше и подтвердите их ограничения.</p><label>Нормативное количество<input id="cost-norm-quantity" inputmode="decimal"></label><label>Нормативная ставка, ₽<input id="cost-norm-rate" inputmode="decimal"></label><label>Обоснование<textarea id="cost-norm-note" maxlength="2000"></textarea></label><label><input type="checkbox" id="cost-norm-limits"> Понимаю, что фактические данные заявлены пользователями и не проверены независимо.</label><button id="cost-norm-preview" disabled>Предварительный просмотр</button><div id="cost-norm-preview-result"></div><div id="cost-norm-approval-panel" hidden><label><input type="checkbox" id="cost-norm-approve-confirm"> Утверждаю именно этот проект как внутренний норматив компании.</label><button id="cost-norm-approve" disabled>Утвердить норматив</button></div></section><section id="price-cost-evidence-panel" hidden><h4>Документы сохранённой сметы</h4><p>Одна копия на строку; без замены. Подлинность, стоимость и оплату система не подтверждает.</p><label>Позиция сметы<select id="price-cost-line"></select></label><button id="price-cost-load" disabled>Проверить документ</button><p id="price-cost-status" aria-live="polite"></p><pre id="price-cost-result" hidden></pre><div id="price-cost-editor" hidden><label>Вид документа<select id="price-cost-kind"><option value="">Выберите вид</option><option value="QUOTE">Коммерческое предложение</option><option value="INVOICE">Счёт</option><option value="CONTRACT">Договор</option><option value="TIMESHEET">Табель трудозатрат</option><option value="OTHER">Прочее</option></select></label><label>Копия PDF, DOCX или XLSX до 2 МБ<input type="file" id="price-cost-file" accept=".pdf,.docx,.xlsx"></label><label><input id="price-cost-confirm" type="checkbox" style="width:auto"> Привязать пользовательскую копию к этой строке и версии без возможности замены; источник и сумма не проверены.</label><button id="price-cost-save" disabled>Прикрепить документ</button></div><button id="price-cost-download" disabled>Скачать проверенные байты</button></section></section>
<div id="company-evidence-panel" hidden><h3>Оригиналы и квалификация</h3>
<p id="company-profile-state"></p><label>ID собственного прогона<input id="company-run-id" autocomplete="off"></label>
<button id="company-bind">Привязать оригиналы к текущей версии профиля</button>
<label>Привязка<select id="company-evidence"><option value="">Выберите привязку</option></select></label>
<button id="company-read-evidence">Проверить сохранённые оригиналы и показать оценку</button>
<p id="company-evidence-state" aria-live="polite"></p>
<pre id="company-evidence-result" hidden></pre></div>
<div id="company-commercial-evidence-panel" hidden><h3>Снимки коммерческой карточки</h3>
<p id="company-capture-state" aria-live="polite"></p>
<button id="company-capture-refresh" disabled>Обновить историю</button>
<label><input id="company-capture-confirm" type="checkbox" style="width:auto"> Подтверждаю получение публичной карточки по сохранённой ссылке указанной компании. Не подача заявки.</label>
<button id="company-capture-start" disabled>Получить оригинал карточки</button>
<label>Сохранённая попытка<select id="company-capture-attempt"><option value="">Выберите попытку</option></select></label>
<label>Сравнить с более ранним снимком (необязательно)<select id="company-capture-previous"><option value="">Без сравнения</option></select></label>
<button id="company-capture-recheck" disabled>Проверить сохранённый снимок</button>
<pre id="company-capture-result" hidden></pre>
<button id="company-case-matrix" disabled>Общая матрица закупки</button><button id="company-case-matrix-prev" disabled>Предыдущие документы</button><button id="company-case-matrix-next" disabled>Следующие документы</button><pre id="company-case-matrix-result" hidden></pre>
<div id="company-attachment-panel" hidden><h4>Файлы, переданные компанией</h4><p id="company-attachment-state" aria-live="polite"></p>
<label>Обнаруженная ссылка<select id="company-attachment-candidate"><option value="">Выберите ссылку</option></select></label>
<label>Файл (PDF, DOCX, XLSX, PPTX, до 2 МБ)<input id="company-attachment-file" type="file" accept=".pdf,.docx,.xlsx,.pptx"></label>
<label><input id="company-attachment-confirm" type="checkbox" style="width:auto"> Подтверждаю, что передаю собственную копию. Её происхождение с ЭТП не проверено.</label>
<button id="company-attachment-save" disabled>Сохранить копию</button><button id="company-attachment-read" disabled>Проверить и сравнить копии</button><button id="company-attachment-text" disabled>Извлечь фрагменты требований</button>
<pre id="company-attachment-result" hidden></pre>
<button id="company-requirement-load" disabled>Матрица требований</button>
<div id="company-requirement-panel" hidden><p>Ручная оценка фрагмента, не подтверждение допуска или полноты ТЗ.</p><pre id="company-requirement-summary"></pre>
<label>Фрагмент<select id="company-requirement-fragment"></select></label><pre id="company-requirement-source"></pre>
<label>Оценка<select id="company-requirement-assessment"><option value="NEEDS_EVIDENCE">Нужны доказательства</option><option value="HUMAN_SUPPORT_RECORDED">Специалист указал подтверждение</option><option value="HUMAN_GAP_RECORDED">Специалист указал несоответствие</option><option value="NOT_REQUIREMENT">Не требование</option></select></label>
<label>Документ компании<select id="company-requirement-document"></select></label><label><input type="checkbox" id="company-requirement-reference" style="width:auto"> Сослаться на текущий референс-лист</label>
<label>Обоснование<textarea id="company-requirement-rationale" maxlength="2000"></textarea></label>
<button id="company-requirement-save" disabled>Записать оценку</button><button id="company-requirement-history" disabled>История оценок</button><pre id="company-requirement-result"></pre></div><p>Извлечение DOCX, XLSX и PDF ограничено; найденные фрагменты не являются проверенными требованиями. Скачивание с ЭТП не включено.</p></div>
<p>Не более одной попытки на закупку в сутки по Москве. Снимок не подтверждает текущий статус конкурса, полный комплект документов, квалификацию или допуск.</p></div>
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
let companyIdentity=null, companyItems=[], companyMore=false, companyOffset=0, companyInboxView=null;
let companyCase=null, companyProfile=null, companyEvidence=[], pendingCompanyDecision=null;
let captureEnabled=false, captureAttempts=[];
let attachmentParent=null, attachmentCandidates=[], attachmentRecords=[], attachmentIntakeEnabled=false, textProjectionEnabled=false;
let requirementEnabled=false, requirementMatrix=null, pendingRequirement=null;
let caseMatrixPage=null;
let lifecycleState=null, pendingLifecycle=null;
let pricePreview=null, priceHistory=null, pendingPrice=null;
let priceLines=[], priceEditing=null;
let costBinding=null, costEvidence=null;
let actualEvidenceBinding=null, actualEvidence=null;
let actualSamples=[];
let normDraft=null,normPending=null,normCatalog=[],normOffset=0,normMore=false,normHistory=null;
let actualSelectedLine='', actualHistory=null, actualDigest=null, actualObservations=[], actualExtras=[], actualPreview=null, actualPending=null;
let readinessState=null, lifecycleEvents=[], eventArtifact=null, eventArtifactMissing=false;
let discoveryEnabled=false, discoveryRun=null, discoveryProfile=null, companySchedule=null;
const el=id=>document.getElementById(id);
function blankSelect(id, label){
 const select=el(id);select.replaceChildren();
 const opt=document.createElement("option");opt.value="";opt.textContent=label;select.append(opt);
}
function resetCompanyDetail(){
 invalidateNormDraft();
 resetPrice();
 resetLifecycle();
 companyCase=null;companyProfile=null;companyEvidence=[];pendingCompanyDecision=null;
 resetCommercialCaptures();
 el("company-detail").hidden=true;el("company-case-state").textContent="";el("company-case-url").textContent="";
 el("company-history").textContent="";el("company-profile-state").textContent="";
 el("company-evidence-state").textContent="";el("company-evidence-result").textContent="";
 el("company-evidence-result").hidden=true;blankSelect("company-evidence","Выберите привязку");
 el("company-rationale").value="";el("company-defer").value="";el("company-confirm").checked=false;
 el("company-action").value="GO";el("company-run-id").value="";
}
function clearCompany(){
 resetActualSamples();resetNormCatalog();clearMetrics();
 companyIdentity=null;companyItems=[];companyMore=false;companyOffset=0;companyInboxView=null;
 el("company-inbox-summary").textContent="";el("company-inbox-filter").value="attention";
 resetCompanySearch();
 blankSelect("company-case","Выберите закупку");resetCompanyDetail();
 el("company-identity").textContent="Войдите и загрузите портфель.";el("company-count").textContent="";
 el("company-registry").value="";el("company-commercial-url").value="";syncCompanyControls();
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
 el("company-inbox-load").disabled=uiBusy||!read;
 el("company-inbox-filter").disabled=uiBusy||!read;
 el("company-save-panel").hidden=!companyCanWrite();el("company-save").disabled=uiBusy||!companyCanWrite();
 el("company-open").disabled=uiBusy||!read||!el("company-case").value;
 el("company-decision-panel").hidden=!detail||!companyCanDecide();
 el("company-decide").disabled=uiBusy||!detail||!companyCanDecide();
 syncLifecycleControls(read,detail);
 syncEvidenceControls(read,detail);
 syncPriceControls(detail);
 el("company-evidence-panel").hidden=!detail||!companyCanWrite()||companyCase?.source_kind==="commercial_reference";
 el("company-bind").disabled=uiBusy||!detail||!companyCanWrite()||companyProfile?.profile_state!=="ACTIVE";
 el("company-read-evidence").disabled=uiBusy||!detail||!companyCanWrite()||!el("company-evidence").value;
 const commercial=Boolean(detail&&companyCanWrite()&&companyCase?.source_kind==="commercial_reference"&&companyCase.source_url);
 el("company-commercial-evidence-panel").hidden=!commercial;
 el("company-capture-refresh").disabled=uiBusy||!commercial;
 el("company-capture-confirm").disabled=uiBusy||!commercial||!captureEnabled;
 el("company-capture-start").disabled=uiBusy||!commercial||!captureEnabled||!el("company-capture-confirm").checked;
 el("company-capture-recheck").disabled=uiBusy||!commercial||!captureAttempts.some(x=>x.attempt_id===el("company-capture-attempt").value);
 const attachmentReady=Boolean(commercial&&attachmentParent===el("company-capture-attempt").value);
 const selected=attachmentCandidates.find(x=>x.candidate_id===el("company-attachment-candidate").value);
 el("company-attachment-panel").hidden=!attachmentReady;
 el("company-attachment-save").disabled=uiBusy||!attachmentReady||!attachmentIntakeEnabled||!selected||!el("company-attachment-confirm").checked||!el("company-attachment-file").files?.length;
 el("company-attachment-read").disabled=uiBusy||!attachmentReady||!attachmentRecords.some(x=>x.candidate_id===selected?.candidate_id);
 el("company-attachment-text").disabled=el("company-attachment-read").disabled||!textProjectionEnabled;
 el("company-case-matrix").disabled=uiBusy||!attachmentReady||!requirementEnabled;
 el("company-case-matrix-prev").disabled=el("company-case-matrix").disabled||!(caseMatrixPage?.offset>0);
 el("company-case-matrix-next").disabled=el("company-case-matrix").disabled||caseMatrixPage?.has_more!==true;
 el("company-requirement-load").disabled=el("company-attachment-read").disabled||!requirementEnabled||!["docx","xlsx"].includes(selected?.format_hint);
 const req=Boolean(requirementMatrix&&requirementMatrix.candidate_id===selected?.candidate_id&&attachmentReady);
 el("company-requirement-panel").hidden=!req;
 const frag=req?requirementMatrix.items.find(x=>x.fragment_key===el("company-requirement-fragment").value):null;
 el("company-requirement-save").disabled=uiBusy||!frag||requirementMatrix?.profile?.state!=="ACTIVE";
 el("company-requirement-history").disabled=uiBusy||!frag;
 syncCompanySearchControls();syncNormControls();
}
function requireCompany(){if(!companyIdentity?.legal_accepted)throw Error("Загрузите портфель после подтверждения условий пилота");return companyIdentity}
function casePath(){requireCompany();if(!companyCase)throw Error("Откройте карточку");return "/api/saas/company-portfolio/cases/"+encodeURIComponent(companyCase.case_id)}
function companyCaseText(item){return ((item.source_platform&&item.source_platform!=="eis"?item.source_platform+":"+item.external_id:item.registry_number)||"Номер не указан")+" · "+(item.decision?.action||"Не решено")+" · v"+item.revision+(item.inbox_state==="deferred_due"?" · пора вернуться":"")}
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
async function loadCompanyInbox({restart=true}={}){
 if(restart)clearMetrics();
 const identity=requireCompany();const selected=restart?val("company-inbox-filter"):companyInboxView;
 if(!["attention","undecided","deferred_due","deferred_future","go","no_go","all"].includes(selected))throw Error("Выберите очередь");
 if(restart){companyItems=[];companyOffset=0;companyMore=false;companyInboxView=null;resetCompanyDetail();renderCompanyItems();el("company-inbox-summary").textContent=""}
 const page=await call("/api/saas/company-portfolio/manager-inbox?view="+encodeURIComponent(selected)+"&offset="+companyOffset+"&limit=50");
 if(page.customer_id!==identity.customer_id||page.view!==selected||page.offset!==companyOffset||page.external_submission_allowed!==false||page.scope!=="SAVED_COMPANY_REFERENCES_AND_HUMAN_DECISIONS"){clearSession();throw Error("Ответ очереди относится к другой компании или выборке")}
 companyInboxView=selected;const known=new Set(companyItems.map(x=>x.case_id));companyItems.push(...page.items.filter(x=>!known.has(x.case_id)));companyOffset+=page.items.length;companyMore=Boolean(page.has_more);
 const c=page.summary;el("company-inbox-summary").textContent="Сохранено: "+c.all+" · Требуют внимания: "+c.attention+" · Без решения: "+c.undecided+" · Пора вернуться: "+c.deferred_due+" · Отложены: "+c.deferred_future+" · GO: "+c.go+" · NO GO: "+c.no_go+". На "+page.as_of+". Обновите очередь после изменений.";
 renderCompanyItems();return {loaded:companyItems.length,has_more:companyMore};
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
function resetCommercialCaptures(){
 resetAttachments();
 captureEnabled=false;captureAttempts=[];blankSelect("company-capture-attempt","Выберите попытку");blankSelect("company-capture-previous","Без сравнения");
 el("company-capture-state").textContent="";el("company-capture-confirm").checked=false;
 el("company-capture-result").hidden=true;el("company-capture-result").textContent="";
}
function requireCommercialCase(){
 if(!companyCanWrite()||companyCase?.source_kind!=="commercial_reference"||!companyCase.source_url)throw Error("Откройте коммерческую карточку с сохранённой ссылкой");
 return companyCase;
}
function captureIdentity(result,attemptId=null){
 const item=requireCommercialCase();
 if(result.case_id!==item.case_id||result.source_url!==item.source_url||(attemptId!==null&&result.attempt_id!==attemptId)){
   clearSession();throw Error("Снимок не соответствует карточке. Сессия очищена.");
 }
}
function captureLabel(outcome){return ({CAPTURED:"Сохранён снимок",SOURCE_UNAVAILABLE:"Источник недоступен",UNSUPPORTED_CARD:"Неподдерживаемая карточка",UNCONFIRMED_ATTEMPT:"Попытка без подтверждения"})[outcome]||"Неизвестный результат"}
async function loadCommercialCaptures(){
 const item=requireCommercialCase();resetCommercialCaptures();
 const page=await call(casePath()+"/commercial-captures?limit=20");
 if(page.customer_id!==requireCompany().customer_id||page.case_id!==item.case_id){clearSession();throw Error("История другой компании или карточки")}
 for(const attempt of page.items)captureIdentity(attempt);
 captureEnabled=page.capture_enabled===true;captureAttempts=page.items;
 for(const attempt of captureAttempts){const opt=document.createElement("option");opt.value=attempt.attempt_id;opt.textContent=attempt.capture_day+" · "+captureLabel(attempt.outcome);el("company-capture-attempt").append(opt)}
 el("company-capture-state").textContent=(captureEnabled?"Получение разрешено сервером.":"Получение отключено сервером.")+" Сохранённых попыток: "+captureAttempts.length+(page.has_more?" (первые 20)":"");
 return {attempts:captureAttempts.length,capture_enabled:captureEnabled};
}
el("company-capture-confirm").addEventListener("change",syncCompanyControls);
el("company-capture-attempt").addEventListener("change",()=>{
 resetAttachments();el("company-capture-result").hidden=true;el("company-capture-result").textContent="";blankSelect("company-capture-previous","Без сравнения");
 const chosen=captureAttempts.find(x=>x.attempt_id===el("company-capture-attempt").value);
 if(chosen?.outcome==="CAPTURED")for(const old of captureAttempts){if(old.outcome==="CAPTURED"&&old.capture_day<chosen.capture_day){const opt=document.createElement("option");opt.value=old.attempt_id;opt.textContent=old.capture_day;el("company-capture-previous").append(opt)}}
 syncCompanyControls();
});
el("company-capture-previous").addEventListener("change",()=>{resetAttachments();el("company-capture-result").hidden=true;el("company-capture-result").textContent="";syncCompanyControls()});
bind("company-capture-refresh",loadCommercialCaptures);
bind("company-capture-start",async()=>{
 requireCommercialCase();if(!captureEnabled||!el("company-capture-confirm").checked)throw Error("Подтвердите получение оригинала");
 el("company-capture-confirm").checked=false;el("company-capture-result").hidden=true;el("company-capture-result").textContent="";
 const result=await call(casePath()+"/commercial-captures",{method:"POST",body:{confirm_public_capture:true}});captureIdentity(result);
 await loadCommercialCaptures();el("company-capture-state").textContent=captureLabel(result.outcome)+". Для проверки выберите сохранённую попытку.";
 return {attempt_id:result.attempt_id,outcome:result.outcome};
});
bind("company-capture-recheck",async()=>{
 requireCommercialCase();const id=val("company-capture-attempt");if(!captureAttempts.some(x=>x.attempt_id===id))throw Error("Выберите попытку из карточки");
 resetAttachments();
 el("company-capture-result").hidden=true;el("company-capture-result").textContent="";
 const previous=val("company-capture-previous");
 const chosen=captureAttempts.find(x=>x.attempt_id===id);
 if(previous&&!captureAttempts.some(x=>x.attempt_id===previous&&x.outcome==="CAPTURED"&&x.capture_day<chosen.capture_day))throw Error("Выберите более ранний снимок этой карточки");
 const result=await call(casePath()+"/commercial-captures/"+encodeURIComponent(id)+(previous?"?previous_attempt_id="+encodeURIComponent(previous):""));captureIdentity(result,id);
 if(previous&&result.comparison?.previous_attempt_id!==previous){clearSession();throw Error("Сравнение не соответствует выбранному снимку")}
 el("company-capture-state").textContent=result.original_reverified===true?"Сохранённый оригинал повторно проверен. Актуальный статус не подтверждён.":captureLabel(result.outcome)+". Оригинал не подтверждён.";
 if(result.original_reverified===true){el("company-capture-result").textContent=JSON.stringify({receipt:result.receipt,attachment_inventory:result.attachment_inventory,comparison:result.comparison},null,2);el("company-capture-result").hidden=false;await loadAttachments(result)}
 return {attempt_id:id,original_reverified:result.original_reverified===true};
});
function clearCaseMatrix(){resetReadiness();caseMatrixPage=null;el("company-case-matrix-result").hidden=true;el("company-case-matrix-result").textContent=""}
function resetAttachments(){
 clearCaseMatrix();
 attachmentParent=null;attachmentCandidates=[];attachmentRecords=[];attachmentIntakeEnabled=false;textProjectionEnabled=false;requirementEnabled=false;resetRequirements();
 blankSelect("company-attachment-candidate","Выберите ссылку");el("company-attachment-file").value="";el("company-attachment-confirm").checked=false;
 el("company-attachment-panel").hidden=true;el("company-attachment-state").textContent="";el("company-attachment-result").hidden=true;el("company-attachment-result").textContent="";
}
function attachmentPath(){requireCommercialCase();if(!attachmentParent||attachmentParent!==el("company-capture-attempt").value)throw Error("Сначала проверьте снимок");return casePath()+"/commercial-captures/"+encodeURIComponent(attachmentParent)+"/attachments"}
function attachmentIdentity(result,id){
 const candidate=attachmentCandidates.find(x=>x.candidate_id===id);
 if(!candidate||result.case_id!==companyCase.case_id||result.attempt_id!==attachmentParent||result.candidate_id!==id||result.source_url!==candidate.source_url||result.origin!=="USER_SUPPLIED_UNATTESTED"){clearSession();throw Error("Несоответствие файла выбранной карточке")}
}
async function refreshAttachmentRecords(){
 const page=await call(attachmentPath());if(page.customer_id!==requireCompany().customer_id||page.case_id!==companyCase.case_id||page.attempt_id!==attachmentParent){clearSession();throw Error("История файлов другой компании")}
 for(const item of page.items)attachmentIdentity(item,item.candidate_id);attachmentRecords=page.items;
 el("company-attachment-state").textContent=(attachmentIntakeEnabled?"Приём копий разрешён.":"Приём копий отключён.")+" Сохранено: "+attachmentRecords.length+". Происхождение не подтверждено.";
}
async function loadAttachments(result){
 attachmentParent=result.attempt_id;attachmentIntakeEnabled=result.attachment_intake_enabled===true;textProjectionEnabled=result.text_projection_enabled===true;requirementEnabled=result.requirement_review_enabled===true;
 attachmentCandidates=(result.attachment_inventory?.candidates||[]).filter(x=>["pdf","docx","xlsx","pptx"].includes(x.format_hint)&&typeof x.candidate_id==="string");
 for(const item of attachmentCandidates){const opt=document.createElement("option");opt.value=item.candidate_id;opt.textContent=(item.display_label||item.source_url)+" · "+item.format_hint;el("company-attachment-candidate").append(opt)}
 await refreshAttachmentRecords();
}
el("company-attachment-candidate").addEventListener("change",()=>{resetRequirements();el("company-attachment-file").value="";el("company-attachment-confirm").checked=false;el("company-attachment-result").hidden=true;el("company-attachment-result").textContent="";syncCompanyControls()});
el("company-attachment-file").addEventListener("change",syncCompanyControls);el("company-attachment-confirm").addEventListener("change",syncCompanyControls);
bind("company-attachment-save",async()=>{
 const path=attachmentPath(),id=val("company-attachment-candidate"),file=el("company-attachment-file").files?.[0];
 if(!attachmentIntakeEnabled||!attachmentCandidates.some(x=>x.candidate_id===id)||!el("company-attachment-confirm").checked||!file||file.size<=0||file.size>2097152)throw Error("Выберите файл до 2 МБ и подтвердите происхождение");
 el("company-attachment-confirm").checked=false;const result=await call(path+"/"+encodeURIComponent(id)+"?confirm_user_supplied=true",{method:"POST",body:file,upload:true});attachmentIdentity(result,id);
 clearCaseMatrix();el("company-attachment-file").value="";await refreshAttachmentRecords();el("company-attachment-result").textContent=JSON.stringify(result,null,2);el("company-attachment-result").hidden=false;return {evidence_id:result.evidence_id};
});
bind("company-attachment-read",async()=>{
 const path=attachmentPath(),id=val("company-attachment-candidate"),previous=val("company-capture-previous");if(!attachmentRecords.some(x=>x.candidate_id===id))throw Error("Сначала сохраните копию");
 el("company-attachment-result").hidden=true;el("company-attachment-result").textContent="";
 const result=await call(path+"/"+encodeURIComponent(id)+(previous?"?previous_attempt_id="+encodeURIComponent(previous):""));attachmentIdentity(result,id);
 if(previous&&result.comparison?.previous_attempt_id!==previous){clearSession();throw Error("Несоответствие версии копии")}
 el("company-attachment-result").textContent=JSON.stringify(result,null,2);el("company-attachment-result").hidden=false;return {stored_bytes_reverified:result.stored_bytes_reverified};
});
bind("company-attachment-text",async()=>{
 const path=attachmentPath(),id=val("company-attachment-candidate");if(!textProjectionEnabled||!attachmentRecords.some(x=>x.candidate_id===id))throw Error("Сохраните копию и проверьте разрешение извлечения");
 el("company-attachment-result").hidden=true;el("company-attachment-result").textContent="";
 const result=await call(path+"/"+encodeURIComponent(id)+"/text-evidence");attachmentIdentity(result,id);
 if(result.text_projection?.source_sha256!==result.inspection?.sha256||result.text_projection?.requirements_verified!==false){clearSession();throw Error("Несоответствие текстового доказательства")}
 el("company-attachment-result").textContent=JSON.stringify({text_projection:result.text_projection,supplier_profile_context:result.supplier_profile_context},null,2);el("company-attachment-result").hidden=false;
 return {status:result.text_projection.status,candidates:result.text_projection.requirement_candidates.length};
});
async function loadCaseMatrix(offset){
 if(!requirementEnabled||!attachmentParent||attachmentParent!==val("company-capture-attempt"))throw Error("Сначала проверьте снимок закупки");
 const result=await call(casePath()+"/commercial-captures/"+encodeURIComponent(attachmentParent)+"/requirement-matrix?offset="+offset+"&limit=3");
 if(result.customer_id!==requireCompany().customer_id||result.case_id!==companyCase.case_id||result.attempt_id!==attachmentParent||result.offset!==offset||result.coverage_complete!==false||result.qualification_verified!==false){clearSession();throw Error("Несоответствие сводной матрицы")}
 caseMatrixPage=result;el("company-case-matrix-result").hidden=false;el("company-case-matrix-result").textContent=JSON.stringify(result,null,2);
 return {candidate_count:result.candidate_count,missing_copy_count:result.missing_copy_count,page_summary:result.page_summary};
}
bind("company-case-matrix",()=>loadCaseMatrix(0));
bind("company-case-matrix-prev",()=>loadCaseMatrix(Math.max(0,(caseMatrixPage?.offset||0)-3)));
bind("company-case-matrix-next",()=>loadCaseMatrix((caseMatrixPage?.offset||0)+3));
function resetRequirements(){
 requirementMatrix=null;pendingRequirement=null;blankSelect("company-requirement-fragment","Выберите фрагмент");blankSelect("company-requirement-document","Без документа");
 for(const id of ["company-requirement-summary","company-requirement-source","company-requirement-result"])el(id).textContent="";
 el("company-requirement-rationale").value="";el("company-requirement-reference").checked=false;el("company-requirement-assessment").value="NEEDS_EVIDENCE";el("company-requirement-panel").hidden=true;
}
function requirementPath(){return attachmentPath()+"/"+encodeURIComponent(val("company-attachment-candidate"))+"/requirements"}
function reqScope(result){
 if(result.customer_id!==requireCompany().customer_id||result.case_id!==companyCase.case_id||result.attempt_id!==attachmentParent||result.candidate_id!==val("company-attachment-candidate")||result.qualification_verified!==false){clearSession();throw Error("Несоответствие матрицы компании")}
}
function reqFragment(){return requirementMatrix?.items.find(x=>x.fragment_key===val("company-requirement-fragment"))}
function showReqFragment(){const item=reqFragment();el("company-requirement-source").textContent=item?JSON.stringify(item,null,2):"";el("company-requirement-result").textContent="";el("company-requirement-rationale").value="";el("company-requirement-document").value="";el("company-requirement-reference").checked=false;el("company-requirement-assessment").value="NEEDS_EVIDENCE";pendingRequirement=null;syncCompanyControls()}
async function loadRequirementMatrix(){
 if(!requirementEnabled)throw Error("Реестр отключён");
 const result=await call(requirementPath());reqScope(result);resetRequirements();requirementMatrix=result;
 for(const item of result.items){const opt=document.createElement("option");opt.value=item.fragment_key;opt.textContent=(item.review?.assessment||"Не проверено")+" · "+item.fragment.text.slice(0,100);el("company-requirement-fragment").append(opt)}
 for(const doc of result.document_options.filter(x=>x.state==="ACTIVE")){const opt=document.createElement("option");opt.value=doc.document_version_id;opt.textContent=doc.display_name+" · v"+doc.version;el("company-requirement-document").append(opt)}
 el("company-requirement-reference").disabled=!result.reference_list?.selectable;
 el("company-requirement-summary").textContent=JSON.stringify({profile:result.profile,reference_list:result.reference_list,summary:result.summary,coverage_complete:false},null,2);
 return {items:result.items.length};
}
bind("company-requirement-load",loadRequirementMatrix);
el("company-requirement-fragment").addEventListener("change",showReqFragment);
bind("company-requirement-save",async()=>{
 const item=reqFragment(),profile=requirementMatrix?.profile;if(!item||profile?.state!=="ACTIVE")throw Error("Выберите фрагмент и актуальный профиль");
 const body={fragment_key:item.fragment_key,expected_revision:item.revision,profile_fact_id:profile.fact_id,reference_fact_id:el("company-requirement-reference").checked?requirementMatrix.reference_list?.fact_id:null,document_version_id:val("company-requirement-document")||null,assessment:val("company-requirement-assessment"),rationale:val("company-requirement-rationale").trim()};
 if(!body.rationale)throw Error("Введите обоснование");
 const signature=JSON.stringify(body);if(pendingRequirement?.signature!==signature){if(!globalThis.crypto?.randomUUID)throw Error("Требуется защищённый HTTPS");pendingRequirement={signature,key:globalThis.crypto.randomUUID()}}
 const saved=await call(requirementPath(),{method:"POST",body:{...body,idempotency_key:pendingRequirement.key}});
 if(saved.fragment_key!==item.fragment_key||saved.revision!==item.revision+1||saved.qualification_verified!==false){clearSession();throw Error("Несоответствие результата оценки")}
 clearCaseMatrix();await loadRequirementMatrix();el("company-requirement-result").textContent=JSON.stringify(saved,null,2);return {revision:saved.revision};
});
bind("company-requirement-history",async()=>{
 const item=reqFragment();if(!item)throw Error("Выберите фрагмент");
 const result=await call(requirementPath()+"/"+encodeURIComponent(item.fragment_key));
 if(result.qualification_verified!==false||!result.items.every(x=>x.fragment_key===item.fragment_key)){clearSession();throw Error("Несоответствие истории")}
 el("company-requirement-result").textContent=JSON.stringify(result.items,null,2);return {items:result.items.length};
});
const lifecycleLabels={PREPARING:"Подготовка",BLOCKED:"Заблокирована",READY:"Готовность подтверждена сотрудником",SUBMITTED:"Подача зарегистрирована",WON:"Победа",LOST:"Проигрыш",REJECTED:"Отклонена",WITHDRAWN:"Отозвана",CANCELLED:"Отменена"};
const lifecyclePre=["PREPARING","BLOCKED","READY"], lifecycleOutcomes=["WON","LOST","REJECTED","WITHDRAWN","CANCELLED"];
function clearMetrics(){el("company-metrics-result").hidden=true;el("company-metrics-result").textContent=""}
function resetLifecycle(){
 resetReadiness();resetEventFiles();
 lifecycleState=null;pendingLifecycle=null;el("company-lifecycle-state").textContent="";el("company-lifecycle-panel").hidden=true;el("company-lifecycle-current").textContent="";el("company-lifecycle-history-result").hidden=true;el("company-lifecycle-history-result").textContent="";
 blankSelect("company-lifecycle-stage","Выберите состояние");for(const id of ["company-lifecycle-rationale","company-lifecycle-ref","company-lifecycle-date"])el(id).value="";el("company-lifecycle-confirm").checked=false;
}
function lifecycleOptions(){
 const st=lifecycleState;if(!st||!companyCanDecide()||!companyCase||st.decision_revision!==companyCase.revision||st.revision>=50)return [];
 const latest=st.latest?.stage;
 if(latest==="SUBMITTED")return lifecycleOutcomes;
 if(lifecycleOutcomes.includes(latest))return lifecycleOutcomes.filter(x=>x!==latest);
 if(st.decision_action!=="GO")return [];
 return [...lifecyclePre,...(latest==="READY"&&!st.latest.readiness_stale?["SUBMITTED"]:[])];
}
function syncLifecycleControls(read,detail){
 const options=lifecycleOptions(),stage=val("company-lifecycle-stage"), canEdit=Boolean(detail&&options.length);
 el("company-metrics-load").disabled=uiBusy||!read;
 el("company-lifecycle-load").disabled=uiBusy||!read||!detail;
 el("company-lifecycle-history").disabled=uiBusy||!detail||!lifecycleState;
 el("company-lifecycle-editor").hidden=!canEdit;
 el("company-lifecycle-external").hidden=!options.includes(stage)||lifecyclePre.includes(stage);
 el("company-lifecycle-save").disabled=uiBusy||!canEdit||!options.includes(stage)||!el("company-lifecycle-confirm").checked;
}
function lifecycleEventMatches(event,caseId){return event?.case_id===caseId&&event.origin==="HUMAN_ATTESTATION"&&event.external_fact_verified===false&&event.external_submission_allowed===false&&Object.hasOwn(lifecycleLabels,event.stage)&&Number.isSafeInteger(event.revision)&&event.revision>0&&event.revision<=50}
async function loadLifecycle(){
 const path=casePath(),id=companyCase.case_id;resetLifecycle();let st;
 try{st=await call(path+"/lifecycle")}catch(error){if(error.status===404){el("company-lifecycle-state").textContent="Журнал недоступен или отключён сервером.";return {available:false}}throw error}
 if(st.customer_id!==requireCompany().customer_id||st.case_id!==id||st.external_submission_allowed!==false||!Number.isSafeInteger(st.revision)||st.revision<0||st.revision>50||(st.revision===0?st.latest!==null:!lifecycleEventMatches(st.latest,id)||st.latest.revision!==st.revision)){clearSession();throw Error("Ответ журнала относится к другой компании или карточке")}
 if(st.decision_revision!==companyCase.revision||st.decision_action!==(companyCase.decision?.action??null)){resetCompanyDetail();throw Error("Решение изменилось. Откройте карточку заново.")}
 lifecycleState=st;setEventFileEvents(st.latest?[st.latest]:[]);el("company-lifecycle-panel").hidden=false;el("company-lifecycle-state").textContent=st.latest?lifecycleLabels[st.latest.stage]+(st.latest.readiness_stale?" · готовность устарела":"")+" · v"+st.revision:"Записей пока нет";
 el("company-lifecycle-current").textContent=st.latest?JSON.stringify(st.latest,null,2):"";
 for(const stage of lifecycleOptions()){const opt=document.createElement("option");opt.value=stage;opt.textContent=lifecycleLabels[stage]+(lifecycleOutcomes.includes(st.latest?.stage)?" (исправление результата)":"");el("company-lifecycle-stage").append(opt)}
 return {available:true,revision:st.revision};
}
bind("company-lifecycle-load",loadLifecycle);
el("company-lifecycle-stage").addEventListener("change",()=>{el("company-lifecycle-confirm").checked=false;syncCompanyControls()});
el("company-lifecycle-confirm").addEventListener("change",syncCompanyControls);
bind("company-lifecycle-save",async()=>{
 const path=casePath(),id=companyCase.case_id,st=lifecycleState,stage=val("company-lifecycle-stage"),rationale=val("company-lifecycle-rationale");
 if(!companyCanDecide()||!st||!lifecycleOptions().includes(stage)||!el("company-lifecycle-confirm").checked||!rationale)throw Error("Укажите состояние, обоснование и подтвердите запись");
 const external=!lifecyclePre.includes(stage),source=external?val("company-lifecycle-ref"):null;let occurred=null;
 if(external){const date=new Date(val("company-lifecycle-date"));if(!source||!Number.isFinite(date.getTime())||date.getTime()>Date.now())throw Error("Укажите квитанцию/протокол и дату события");occurred=date.toISOString()}
 const body={stage,rationale,source_ref:source,occurred_at:occurred,expected_revision:st.revision,expected_decision_revision:st.decision_revision,correct_outcome:lifecycleOutcomes.includes(st.latest?.stage)};
 const signature=JSON.stringify([sessionEpoch,id,body]);if(pendingLifecycle?.signature!==signature){if(!globalThis.crypto?.randomUUID)throw Error("Требуется защищённый HTTPS");pendingLifecycle={signature,key:globalThis.crypto.randomUUID()}}
 clearMetrics();let saved;try{saved=await call(path+"/lifecycle",{method:"POST",body:{...body,idempotency_key:pendingLifecycle.key}})}catch(err){el("company-lifecycle-confirm").checked=false;if(err.status===409)resetLifecycle();throw err}
 if(!lifecycleEventMatches(saved,id)||saved.stage!==stage||saved.revision!==st.revision+1){clearSession();throw Error("Несоответствие записи журнала")}
 clearMetrics();pendingLifecycle=null;el("company-lifecycle-confirm").checked=false;
 try{await loadLifecycle()}catch(err){if(!token||[401,402,403].includes(err.status))throw err;resetLifecycle();el("company-lifecycle-state").textContent="Запись сохранена; обновите состояние журнала.";return {saved_revision:saved.revision,refresh_required:true}}
 return {saved_revision:saved.revision,stage:saved.stage,external_fact_verified:false};
});
bind("company-lifecycle-history",async()=>{
 const id=companyCase?.case_id;if(!lifecycleState||!id)throw Error("Откройте журнал");
 const result=await call(casePath()+"/lifecycle/history?limit=50");
 if(result.customer_id!==requireCompany().customer_id||result.case_id!==id||result.external_submission_allowed!==false||!Array.isArray(result.items)||result.items.length>50||!result.items.every(x=>lifecycleEventMatches(x,id))){clearSession();throw Error("Несоответствие истории событий")}
 setEventFileEvents(result.items);el("company-lifecycle-history-result").textContent=JSON.stringify(result.items,null,2);el("company-lifecycle-history-result").hidden=false;return {events:result.items.length,has_more:result.has_more};
});
bind("company-metrics-load",async()=>{
 clearMetrics();let m;try{m=await call("/api/saas/company-portfolio/lifecycle-metrics")}catch(err){if(err.status===404){el("company-metrics-result").hidden=false;el("company-metrics-result").textContent="Статистика отключена сервером.";return {available:false}}throw err}
 const count=x=>Number.isSafeInteger(x)&&x>=0;const validRate=x=>x&&count(x.numerator)&&count(x.denominator)&&x.numerator<=x.denominator&&(x.denominator===0?x.rate===null:Number.isFinite(x.rate)&&Math.abs(x.rate-x.numerator/x.denominator)<1e-9);
 if(m.customer_id!==requireCompany().customer_id||m.scope!=="ALL_TIME_SAVED_CASES_HUMAN_ATTESTATIONS"||m.external_facts_verified!==false||m.market_coverage_complete!==false||m.contract_revenue_verified!==false||![m.saved_cases,m.ever_go_cases,m.recorded_submissions].every(count)||!validRate(m.go_to_submission)||!validRate(m.win_rate)||!m.stage_counts||![m.stage_counts.SUBMITTED,m.stage_counts.WITHDRAWN,m.stage_counts.CANCELLED].every(count)){clearSession();throw Error("Несоответствие статистики компании")}
 const rate=x=>x.denominator===0?"нет данных":(100*x.rate).toFixed(1)+"% ("+x.numerator+"/"+x.denominator+")";
 el("company-metrics-result").hidden=false;el("company-metrics-result").textContent="За всё время, по сведениям сотрудников.\\nСохранено: "+m.saved_cases+"\\nКогда-либо GO: "+m.ever_go_cases+"\\nЗарегистрировано заявок: "+m.recorded_submissions+"\\nGO → подача: "+rate(m.go_to_submission)+"\\nWin rate (победы / (победы + проигрыши + отклонения)): "+rate(m.win_rate)+"\\nВ ожидании: "+m.stage_counts.SUBMITTED+"; отозваны: "+m.stage_counts.WITHDRAWN+"; отменены: "+m.stage_counts.CANCELLED+"\\nНа "+m.as_of+". Не подтверждённая выручка и не полная статистика рынка.";
 return {available:true,saved_cases:m.saved_cases,recorded_submissions:m.recorded_submissions};
});
const readinessIssues={ACTIVE_PROFILE_REQUIRED:'Нет активного профиля',DOCUMENT_BOUND_EXCEEDED:'Документов больше лимита проверки',NO_DISCOVERED_DOCUMENTS:'Документы не обнаружены',MISSING_USER_COPIES:'Не все копии загружены',TRUNCATED_LINK_SCAN:'Поиск ссылок неполный',DOCUMENT_NOT_REVIEWABLE:'Документ не поддерживается для оценки',UNREVIEWED_FRAGMENT:'Есть непроверенные фрагменты',STALE_REVIEW:'Оценка устарела',UNRESOLVED_REQUIREMENT:'Есть нерешённые требования',NO_RECORDED_SUPPORT:'Нет записанного подтверждения'};
const digestPattern=/^[0-9a-f]{64}$/;
function resetReadiness(){readinessState=null;el('company-readiness-state').textContent='';el('company-readiness-result').textContent='';el('company-readiness-result').hidden=true;el('company-readiness-confirm').checked=false}
function resetEventArtifact(){eventArtifact=null;eventArtifactMissing=false;el('company-event-file-state').textContent='';el('company-event-file-result').textContent='';el('company-event-file-result').hidden=true;el('company-event-file-input').value='';el('company-event-file-confirm').checked=false}
function resetEventFiles(){lifecycleEvents=[];blankSelect('company-event-file-event','Выберите событие');resetEventArtifact()}
function setEventFileEvents(events){resetEventFiles();lifecycleEvents=events.filter(e=>e.stage==='SUBMITTED'||lifecycleOutcomes.includes(e.stage));for(const e of lifecycleEvents){const opt=document.createElement('option');opt.value=e.event_id;opt.textContent='v'+e.revision+' · '+lifecycleLabels[e.stage];el('company-event-file-event').append(opt)}}
function selectedEvent(){return lifecycleEvents.find(e=>e.event_id===val('company-event-file-event'))}
function readinessAvailable(){return companyCanWrite()&&companyCase?.source_kind==='commercial_reference'&&lifecycleState?.latest?.stage==='READY'&&!lifecycleState.latest.readiness_stale&&companyCase.revision===lifecycleState.decision_revision}
function canBindReadiness(){return readinessAvailable()&&companyCanDecide()&&readinessState?.projection.partial_review_resolved===true&&!readinessState.binding_id}
function syncEvidenceControls(read,detail){
 const ready=Boolean(detail&&readinessAvailable()), e=selectedEvent(), eventReady=Boolean(detail&&read&&e), canUpload=eventReady&&companyCanDecide()&&eventArtifactMissing&&!eventArtifact;
 el('company-readiness-panel').hidden=!ready;el('company-readiness-load').disabled=uiBusy||!ready;
 el('company-readiness-confirm').disabled=uiBusy||!canBindReadiness();el('company-readiness-bind').disabled=uiBusy||!canBindReadiness()||!el('company-readiness-confirm').checked;
 el('company-event-file-panel').hidden=!detail||!read||!lifecycleEvents.length;el('company-event-file-load').disabled=uiBusy||!eventReady;
 el('company-event-file-editor').hidden=!canUpload;el('company-event-file-save').disabled=uiBusy||!canUpload||!el('company-event-file-confirm').checked||!el('company-event-file-input').files?.length;
 el('company-event-file-download').disabled=uiBusy||!eventReady||!eventArtifact;
}
function applyReadiness(r){const p=r?.projection,id=companyCase.case_id;
 if(r?.ready_event_id!==lifecycleState.latest.event_id||p?.customer_id!==requireCompany().customer_id||p.case_id!==id||p.schema!=='commercial_readiness_partial_v1'||!digestPattern.test(r.projection_sha256)||!digestPattern.test(p.card_sha256)||p.coverage_complete!==false||p.qualification_verified!==false||p.platform_original_verified!==false||p.external_submission_allowed!==false||r.qualification_verified!==false||r.external_submission_allowed!==false||!Array.isArray(p.issues)||!Array.isArray(p.documents)||p.documents.length>3||p.partial_review_resolved!==(p.issues.length===0)||typeof r.binding_current!=='boolean'||(r.binding_id? !digestPattern.test(r.bound_projection_sha256):r.bound_projection_sha256!==null)||r.binding_current!==Boolean(r.binding_id&&r.bound_projection_sha256===r.projection_sha256&&p.partial_review_resolved)){clearSession();throw Error('Несоответствие снимка готовности')}
 readinessState=r;el('company-readiness-confirm').checked=false;el('company-readiness-result').hidden=false;el('company-readiness-result').textContent=JSON.stringify(p,null,2);
 el('company-readiness-state').textContent=r.binding_current?'Снимок актуален (частичная проверка)':r.binding_id?'Снимок устарел. Создайте новую запись READY.':p.partial_review_resolved?'Частичная матрица проверена. Можно связать с READY.':p.issues.map(x=>readinessIssues[x]||x).join('; ');
}
bind('company-readiness-load',async()=>{if(!readinessAvailable())throw Error('Требуется актуальный READY коммерческой закупки');resetReadiness();try{applyReadiness(await call(casePath()+'/readiness-evidence'))}catch(e){if(e.status===404||e.status===409){el('company-readiness-state').textContent=e.status===404?'Проверка недоступна или отключена.':'Нет актуального снимка. Обновите журнал и документацию.';return {available:false}}throw e}return {binding_current:readinessState.binding_current}});
bind('company-readiness-bind',async()=>{if(!canBindReadiness()||!el('company-readiness-confirm').checked)throw Error('Подтвердите частичное покрытие');const state=readinessState;resetReadiness();applyReadiness(await call(casePath()+'/readiness-evidence',{method:'POST',body:{ready_event_id:state.ready_event_id,projection_sha256:state.projection_sha256,acknowledge_partial_coverage:true}}));if(!readinessState.binding_current||readinessState.projection_sha256!==state.projection_sha256){resetReadiness();throw Error('Снимок изменился, перепроверьте матрицу')}return {binding_current:true}});
el('company-readiness-confirm').addEventListener('change',syncCompanyControls);
el('company-event-file-event').addEventListener('change',()=>{resetEventArtifact();syncCompanyControls()});
for(const id of ['company-event-file-input','company-event-file-confirm'])el(id).addEventListener('change',syncCompanyControls);
function eventArtifactPath(e){return casePath()+'/lifecycle/'+encodeURIComponent(e.event_id)+'/artifact'}
function applyEventArtifact(r,e){if(r?.customer_id!==requireCompany().customer_id||r.case_id!==companyCase.case_id||r.event_id!==e.event_id||r.event_revision!==e.revision||r.event_stage!==e.stage||r.artifact_kind!==(e.stage==='SUBMITTED'?'SUBMISSION_RECEIPT':'OUTCOME_PROTOCOL')||r.origin!=='USER_SUPPLIED_UNATTESTED'||r.stored_bytes_reverified!==true||r.platform_original_verified!==false||r.external_fact_verified!==false||r.external_submission_allowed!==false||!['pdf','docx','xlsx'].includes(r.format_hint)||r.inspection?.format_hint!==r.format_hint||!digestPattern.test(r.inspection?.sha256)||!Number.isSafeInteger(r.inspection.size_bytes)||r.inspection.size_bytes<1||r.inspection.size_bytes>2097152){clearSession();throw Error('Несоответствие файла события')}
 eventArtifact=r;eventArtifactMissing=false;el('company-event-file-state').textContent='Сохранённая копия; байты проверены, подлинность не подтверждена.';el('company-event-file-result').hidden=false;el('company-event-file-result').textContent=JSON.stringify(r,null,2);
}
async function sha256Bytes(bytes){if(!globalThis.crypto?.subtle)throw Error('Требуется защищённый HTTPS');return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('')}
bind('company-event-file-load',async()=>{const e=selectedEvent();if(!e)throw Error('Выберите событие');resetEventArtifact();try{applyEventArtifact(await call(eventArtifactPath(e)),e)}catch(err){if(err.status!==404)throw err;eventArtifactMissing=true;el('company-event-file-state').textContent='Копия не найдена или функция отключена сервером.'}return {available:Boolean(eventArtifact)}});
bind('company-event-file-save',async()=>{const e=selectedEvent(),file=el('company-event-file-input').files?.[0];if(!e||!file||!companyCanDecide()||!eventArtifactMissing||!el('company-event-file-confirm').checked)throw Error('Выберите файл и подтвердите происхождение');const format=file.name.split('.').pop().toLowerCase();if(!['pdf','docx','xlsx'].includes(format)||file.size<1||file.size>2097152)throw Error('Допустимы PDF/DOCX/XLSX до 2 МБ');const sha=await sha256Bytes(await file.arrayBuffer());el('company-event-file-confirm').checked=false;const r=await call(eventArtifactPath(e)+'?format_hint='+format+'&confirm_user_supplied=true',{method:'POST',body:file,upload:true});applyEventArtifact(r,e);if(r.inspection.sha256!==sha||r.inspection.size_bytes!==file.size){clearSession();throw Error('Сохранённые байты не совпадают с файлом')}el('company-event-file-input').value='';return {artifact_id:r.artifact_id,stored_bytes_reverified:true}});
bind('company-event-file-download',async()=>{const e=selectedEvent(),artifact=eventArtifact,epoch=sessionEpoch;if(!e||!artifact||!token)throw Error('Сначала проверьте сохранённую копию');const r=await fetch(eventArtifactPath(e)+'/download',{method:'GET',credentials:'omit',cache:'no-store',redirect:'error',headers:{Authorization:'Bearer '+token,Accept:'application/octet-stream','Cache-Control':'no-store'}});if(!r.ok){const error=Error('HTTP '+r.status);error.status=r.status;throw error}if(r.headers.get('x-artifact-sha256')!==artifact.inspection.sha256||!r.body)throw Error('Нет подтверждения контрольной суммы');const reader=r.body.getReader(),bytes=new Uint8Array(artifact.inspection.size_bytes);let offset=0;try{while(true){const {value,done}=await reader.read();if(done)break;if(offset+value.length>bytes.length)throw Error('Размер файла не совпадает');bytes.set(value,offset);offset+=value.length}}finally{await reader.cancel().catch(()=>{});reader.releaseLock()}
 if(epoch!==sessionEpoch||offset!==bytes.length||await sha256Bytes(bytes)!==artifact.inspection.sha256)throw Error('Контрольная сумма или сессия не совпадает');const url=URL.createObjectURL(new Blob([bytes],{type:'application/octet-stream'}));try{const link=document.createElement('a');link.href=url;link.download='lifecycle-'+artifact.inspection.sha256.slice(0,16)+'.'+artifact.format_hint;link.click()}finally{setTimeout(()=>URL.revokeObjectURL(url),1000)}return {downloaded_bytes:offset,sha256:artifact.inspection.sha256}});
const priceFields=['external_direct_rub','own_labor_rub','cash_overhead_rub','reserve_rub','fixed_platform_fees_rub','guarantee_financing_cost_rub','revenue_tax_percent','variable_platform_fee_percent','minimum_profit_rub','target_profit_rub','reference_ceiling_rub'];
const priceKinds=['CASH_BREAK_EVEN','FULL_BREAK_EVEN','STRATEGIC_MINIMUM_PROFIT','COMMERCIAL_TARGET_PROFIT'];
const priceLabels={CASH_BREAK_EVEN:'Денежная безубыточность',FULL_BREAK_EVEN:'Полная безубыточность',STRATEGIC_MINIMUM_PROFIT:'Минимальная прибыль',COMMERCIAL_TARGET_PROFIT:'Целевая прибыль',MANUAL_PRICE:'Ручная цена'};
function clearPricePreview(){el('price-itemized-result').replaceChildren();pricePreview=null;pendingPrice=null;el('price-save-confirm').checked=false;el('price-totals').textContent='';el('price-results').replaceChildren();el('price-status').textContent=''}
function resetPrice(){resetCostVersion();resetItemized();clearPricePreview();priceHistory=null;for(const f of priceFields)el('price-'+f).value='';el('price-manual').value='';el('price-note').value='';el('price-confirm').checked=false;blankSelect('price-version','Выберите версию');el('price-version-detail').hidden=true;el('price-version-detail').textContent=''}
function syncPriceControls(detail){const read=Boolean(detail&&companyCanWrite()), write=read&&companyCanDecide();el('company-price-panel').hidden=!read;syncItemizedControls(read);syncCostEvidence(read);syncActual(read);syncActualEvidence(read);syncActualSamples(read);el('price-preview').disabled=uiBusy||!read||!el('price-confirm').checked;el('price-history').disabled=uiBusy||!read;el('price-save-confirm-label').hidden=!write;el('price-save-confirm').disabled=uiBusy||!write||!pricePreview||priceHistory===null;el('price-save').disabled=uiBusy||!write||!pricePreview||priceHistory===null||!el('price-save-confirm').checked||(priceHistory[0]?.revision??0)>=30;el('price-show-version').disabled=uiBusy||!read||!priceHistory?.some(x=>x.scenario_id===val('price-version'))}
function priceInput(itemized=false){const p={};for(const name of (itemized?priceFields.slice(6):priceFields)){const v=val('price-'+name).replace(',','.');if(name==='reference_ceiling_rub'&&!v){p[name]=null;continue}const percent=name.endsWith('_percent');if(!(percent?/^[0-9]{1,3}(\\.[0-9]{1,4})?$/:/^[0-9]{1,12}(\\.[0-9]{1,2})?$/).test(v))throw Error('Заполните все обязательные суммы и ставки; ноль допускается явно.');p[name]=v}p.manual_bid_prices_rub=val('price-manual').split(/\\r?\\n/).map(x=>x.trim().replace(',','.')).filter(Boolean);if(p.manual_bid_prices_rub.length>8||p.manual_bid_prices_rub.some(x=>!/^[0-9]{1,12}(\\.[0-9]{1,2})?$/.test(x)))throw Error('До 8 дополнительных цен, каждая с новой строки.');p.assumption_note=val('price-note');p.accept_hypothetical_assumptions_only=el('price-confirm').checked;if(!p.assumption_note||!p.accept_hypothetical_assumptions_only)throw Error('Укажите обоснование и подтвердите допущения');return p}
function samePriceValue(a,b){if(Array.isArray(a))return Array.isArray(b)&&a.length===b.length&&a.every((x,i)=>samePriceValue(x,b[i]));if(a&&typeof a==='object')return b&&typeof b==='object'&&Object.keys(a).length===Object.keys(b).length&&Object.keys(a).every(k=>Object.hasOwn(b,k)&&samePriceValue(a[k],b[k]));return a===b}
function validPriceResult(r){const money=x=>typeof x==='string'&&/^-?[0-9]{1,21}\\.[0-9]{2}$/.test(x);return r?.schema==='company_price_scenario_v1'&&r.currency==='RUB'&&[r.cash_fixed_and_reserved_rub,r.own_labor_rub,r.full_economic_cost_before_revenue_rates_rub].every(money)&&r.thresholds_rounded_up_to_kopecks===true&&r.profits_rounded_down_to_kopecks===true&&['assumptions_independently_verified','tax_model_verified','market_comparables_used','probability_of_winning_estimated','is_procurement_bid_recommendation','commercial_owner_go','external_submission_allowed'].every(k=>r[k]===false)&&Array.isArray(r.scenarios)&&r.scenarios.length>=4&&r.scenarios.length<=12&&r.scenarios.every((x,i)=>x.kind===(priceKinds[i]??'MANUAL_PRICE')&&[x.price_rub,x.cash_surplus_rub,x.economic_profit_rub].every(money)&&(x.economic_margin_percent===null||typeof x.economic_margin_percent==='string'&&/^-?[0-9]{1,24}\\.[0-9]{4}$/.test(x.economic_margin_percent))&&['cash_break_even_met','full_break_even_met','minimum_profit_met','target_profit_met'].every(k=>typeof x[k]==='boolean')&&(x.within_user_reference_ceiling===null||typeof x.within_user_reference_ceiling==='boolean'))}
function checkPriceScope(r){if(r?.customer_id!==requireCompany().customer_id||r.case_id!==companyCase?.case_id){clearSession();throw Error('Расчёт относится к другой компании или закупке')}}
function renderPrice(r){el('price-totals').textContent='Денежные затраты и резерв: '+r.cash_fixed_and_reserved_rub+' ₽; полная себестоимость до налога и комиссии: '+r.full_economic_cost_before_revenue_rates_rub+' ₽.';const table=document.createElement('table');const header=document.createElement('tr');for(const title of ['Сценарий','Цена, ₽','Денежный остаток, ₽','Экономическая прибыль, ₽','Маржа, %','Предел цены']){const th=document.createElement('th');th.textContent=title;header.append(th)}table.append(header);for(const x of r.scenarios){const tr=document.createElement('tr');for(const v of [priceLabels[x.kind],x.price_rub,x.cash_surplus_rub,x.economic_profit_rub,x.economic_margin_percent??'—',x.within_user_reference_ceiling===null?'Не задан':x.within_user_reference_ceiling?'В пределах':'Выше предела']){const td=document.createElement('td');td.textContent=v;tr.append(td)}table.append(tr)}el('price-results').replaceChildren(table)}
function validPriceRecord(r){return r&&r.customer_id===requireCompany().customer_id&&r.case_id===companyCase.case_id&&r.origin==='EXPLICIT_USER_ASSUMPTIONS'&&r.external_submission_allowed===false&&typeof r.scenario_id==='string'&&r.scenario_id&&Number.isInteger(r.revision)&&r.revision>=1&&r.revision<=30&&r.inputs?.accept_hypothetical_assumptions_only===true&&validPriceResult(r.result)&&(!Object.hasOwn(r,'itemized_estimate')||validItemizedProjection(r.itemized_estimate,r.inputs))}
function showPriceHistory(items){resetCostVersion();priceHistory=items;blankSelect('price-version','Выберите версию');el('price-version-detail').hidden=true;el('price-version-detail').textContent='';for(const x of items){const o=document.createElement('option');o.value=x.scenario_id;o.textContent='v'+x.revision+' · '+(x.itemized_estimate?'Смета':'Итоги')+' · '+x.created_at;el('price-version').append(o)}}
async function loadPriceHistory(){resetCostVersion();priceHistory=null;pendingPrice=null;el('price-save-confirm').checked=false;blankSelect('price-version','Выберите версию');el('price-version-detail').hidden=true;el('price-version-detail').textContent='';const r=await call(casePath()+'/price-scenarios?limit=30');checkPriceScope(r);if(r.external_submission_allowed!==false||r.has_more!==false||!Array.isArray(r.items)||r.items.length>30||!r.items.every((x,i)=>validPriceRecord(x)&&x.revision===r.items.length-i)||new Set(r.items.map(x=>x.scenario_id)).size!==r.items.length){clearSession();throw Error('Несоответствие истории расчётов')}showPriceHistory(r.items);return {versions:r.items.length}}
bind('price-history',async()=>{if(!companyCanWrite())throw Error('Недостаточно прав');return loadPriceHistory()});
bind('price-preview',async()=>{if(!companyCanWrite())throw Error('Недостаточно прав');clearPricePreview();const itemized=isItemized(),p=itemized?estimateInput():priceInput(),r=await call(casePath()+'/price-scenarios'+(itemized?'/itemized':'')+'/preview',{method:'POST',body:p});checkPriceScope(r);if(r.inputs_stored!==false||!validPriceResult(r.result)||r.result.scenarios.length!==4+(itemized?p.terms:p).manual_bid_prices_rub.length||(itemized&&!validItemizedProjection(r.itemized_estimate,r.inputs,p))){clearSession();throw Error('Некорректный расчёт')}pricePreview={inputs:p,result:r.result,itemized,aggregate:itemized?r.inputs:p,projection:itemized?r.itemized_estimate:null};renderPrice(r.result);if(itemized)renderItemized(r.itemized_estimate);el('price-status').textContent='Предварительный расчёт, не сохранён. Для записи загрузите историю и подтвердите сохранение.';return {calculated:true,inputs_stored:false}});
bind('price-save',async()=>{if(!companyCanDecide()||!pricePreview||priceHistory===null||!el('price-save-confirm').checked)throw Error('Рассчитайте сценарий, загрузите историю и подтвердите сохранение');const itemized=isItemized(),p=itemized?estimateInput():priceInput(),rev=priceHistory[0]?.revision??0;if(itemized!==pricePreview.itemized||!samePriceValue(p,pricePreview.inputs)||rev>=30){clearPricePreview();throw Error('Расчёт изменился или достигнут лимит версий')};if(!pendingPrice){if(!globalThis.crypto?.randomUUID)throw Error('Требуется HTTPS');pendingPrice={expected_revision:rev,idempotency_key:crypto.randomUUID(),...(itemized?{estimate:p}:{scenario:p})}}const draft=pendingPrice;el('price-save-confirm').checked=false;let r;try{r=await call(casePath()+'/price-scenarios'+(itemized?'/itemized':''),{method:'POST',body:draft})}catch(e){if(e.status===409){resetPrice();throw Error('Версия изменилась. Загрузите историю и пересчитайте.')}el('price-status').textContent='Запись не подтверждена. Повторите тот же сценарий или проверьте историю.';throw e}checkPriceScope(r);if(!validPriceRecord(r)||r.member_id!==requireCompany().member_id||r.revision!==draft.expected_revision+1||!samePriceValue(r.inputs,pricePreview.aggregate)||!samePriceValue(r.result,pricePreview.result)||(itemized?!samePriceValue(r.itemized_estimate,pricePreview.projection):Object.hasOwn(r,'itemized_estimate'))){clearSession();throw Error('Сохранённый расчёт не совпадает с предварительным')}showPriceHistory([r,...priceHistory]);pendingPrice=null;pricePreview=null;el('price-status').textContent='Версия v'+r.revision+' сохранена. Это не утверждение ставки.';return {saved_revision:r.revision}});
bind('price-show-version',async()=>{if(!companyCanWrite())throw Error('Недостаточно прав');const r=priceHistory?.find(x=>x.scenario_id===val('price-version'));if(!r)throw Error('Выберите версию');el('price-version-detail').textContent=JSON.stringify({revision:r.revision,created_at:r.created_at,inputs:r.inputs,result:r.result,...(r.itemized_estimate?{itemized_estimate:r.itemized_estimate}:{})},null,2);el('price-version-detail').hidden=false;return {viewed_revision:r.revision}});
for(const id of [...priceFields.map(x=>'price-'+x),'price-manual','price-note','price-confirm']){const change=()=>{clearPricePreview();syncCompanyControls()};el(id).addEventListener('input',change);el(id).addEventListener('change',change)}
el('price-save-confirm').addEventListener('change',syncCompanyControls);
el('price-version').addEventListener('change',()=>{el('price-version-detail').hidden=true;el('price-version-detail').textContent='';setCostVersion();syncCompanyControls()});
const costCategories=priceFields.slice(0,6), costLabels=['Прямые расходы','Собственный труд','Накладные расходы','Резерв','Сборы ЭТП','Финансирование'];
const lineKeys=['category','title','unit','quantity','rate_rub','source_kind','source_note'];
const sourceLabels={ASSUMPTION:'Допущение',USER_REPORTED_QUOTE:'КП со слов сотрудника',USER_REPORTED_ACTUAL:'Расходы со слов сотрудника'};
function isItemized(){return val('price-mode')==='itemized'}
function resetLineEditor(){priceEditing=null;for(const k of lineKeys)el('price-line-'+k).value=k==='category'?costCategories[0]:k==='source_kind'?'ASSUMPTION':'';el('price-line-status').textContent='';el('price-line-add').textContent='Добавить строку'}
function resetItemized(){priceLines=[];el('price-mode').value='aggregate';resetLineEditor();for(const k of costCategories)el('price-zero-'+k).checked=false;el('price-no-double').checked=false;renderLines()}
function renderLines(){blankSelect('price-line-select','Выберите строку');const table=document.createElement('table');for(const [idx,line] of priceLines.entries()){const o=document.createElement('option');o.value=String(idx);o.textContent=(idx+1)+'. '+line.title;el('price-line-select').append(o);const tr=document.createElement('tr');for(const v of [String(idx+1),costLabels[costCategories.indexOf(line.category)],line.title,line.quantity+' '+line.unit,line.rate_rub+' ₽',sourceLabels[line.source_kind],line.source_note]){const td=document.createElement('td');td.textContent=v;tr.append(td)}table.append(tr)}el('price-line-list').replaceChildren(table)}
function selectedLine(){const v=val('price-line-select');return v!==''&&Number.isInteger(Number(v))&&priceLines[Number(v)]?Number(v):null}
function lineDraftDirty(){return priceEditing!==null||['title','unit','quantity','rate_rub','source_note'].some(k=>val('price-line-'+k))}
function syncItemizedControls(read){const active=isItemized();el('price-aggregate-panel').hidden=active;el('price-itemized-panel').hidden=!active;const no=uiBusy||!read||!active;el('price-line-add').disabled=no||(priceEditing===null&&priceLines.length>=60);el('price-line-edit').disabled=no||selectedLine()===null||lineDraftDirty();el('price-line-remove').disabled=no||selectedLine()===null||lineDraftDirty();el('price-line-cancel').disabled=no||!lineDraftDirty();for(const k of costCategories){const used=priceLines.some(l=>l.category===k);el('price-zero-'+k).disabled=no||used;if(used)el('price-zero-'+k).checked=false}}
function readLine(){const line=Object.fromEntries(lineKeys.map(k=>[k,val('price-line-'+k)]));line.quantity=line.quantity.replace(',','.');line.rate_rub=line.rate_rub.replace(',','.');if(!validLine(line))throw Error('Заполните строку: положительные количество и ставка, единица, источник и обоснование');return line}
function validLine(l){return l&&costCategories.includes(l.category)&&typeof l.title==='string'&&l.title.trim()===l.title&&l.title.length>0&&l.title.length<=160&&typeof l.unit==='string'&&l.unit.trim()===l.unit&&l.unit.length>0&&l.unit.length<=24&&typeof l.quantity==='string'&&/^[0-9]{1,9}(\\.[0-9]{1,4})?$/.test(l.quantity)&&Number(l.quantity)>0&&typeof l.rate_rub==='string'&&/^[0-9]{1,12}(\\.[0-9]{1,2})?$/.test(l.rate_rub)&&Number(l.rate_rub)>0&&Object.hasOwn(sourceLabels,l.source_kind)&&typeof l.source_note==='string'&&l.source_note.trim()===l.source_note&&l.source_note.length>0&&l.source_note.length<=500}
function estimateInput(){if(lineDraftDirty())throw Error('Сначала сохраните или отмените редактирование строки');const zeros=costCategories.filter(k=>el('price-zero-'+k).checked);if(!priceLines.length||priceLines.length>60||!el('price-no-double').checked||costCategories.some(k=>priceLines.some(l=>l.category===k)===zeros.includes(k)))throw Error('Для каждой категории нужны строки или явный ноль. Подтвердите отсутствие двойного учёта.');return {lines:priceLines.map(l=>({...l})),zero_cost_categories:zeros,terms:priceInput(true),confirm_no_double_count:true}}
function scaledInt(s,digits){const [a,b='']=s.split('.');return BigInt(a)*10n**BigInt(digits)+BigInt(b.padEnd(digits,'0'))}
function asRub(cents){return (cents/100n).toString()+'.'+(cents%100n).toString().padStart(2,'0')}
function validItemizedProjection(p,aggregate,expected){try{
 if(!p||p.schema!=='company_price_itemized_v1'||p.rounding_policy!=='CEIL_EACH_LINE_TO_KOPECKS_THEN_SUM'||p.source_notes_independently_verified!==false||p.double_count_independently_checked!==false||p.external_submission_allowed!==false)return false;
 const input=p.inputs;if(!input||input.confirm_no_double_count!==true||!Array.isArray(input.lines)||input.lines.length<1||input.lines.length>60||!input.lines.every(validLine)||!Array.isArray(input.zero_cost_categories)||new Set(input.zero_cost_categories).size!==input.zero_cost_categories.length||input.zero_cost_categories.some(k=>!costCategories.includes(k))||costCategories.some(k=>input.lines.some(l=>l.category===k)===input.zero_cost_categories.includes(k))||!input.terms||input.terms.accept_hypothetical_assumptions_only!==true)return false;
 if(expected&&!samePriceValue(input,expected))return false;
 if(!Array.isArray(p.lines)||p.lines.length!==input.lines.length)return false;
 const totals=Object.fromEntries(costCategories.map(k=>[k,0n]));for(const [i,l] of input.lines.entries()){const cost=(scaledInt(l.quantity,4)*scaledInt(l.rate_rub,2)+9999n)/10000n;totals[l.category]+=cost;if(!samePriceValue(p.lines[i],{ordinal:i+1,...l,amount_rub:asRub(cost)}))return false}
 const sums=Object.fromEntries(costCategories.map(k=>[k,asRub(totals[k])]));return samePriceValue(p.category_totals_rub,sums)&&samePriceValue(aggregate,{...input.terms,...sums});
 }catch{return false}}
function renderItemized(p){const table=document.createElement('table');const head=document.createElement('tr');for(const v of ['Позиция','Количество','Ставка, ₽','Сумма, ₽','Источник']){const th=document.createElement('th');th.textContent=v;head.append(th)}table.append(head);for(const l of p.lines){const tr=document.createElement('tr');for(const v of [l.title,l.quantity+' '+l.unit,l.rate_rub,l.amount_rub,sourceLabels[l.source_kind]+': '+l.source_note]){const td=document.createElement('td');td.textContent=v;tr.append(td)}table.append(tr)}const totals=document.createElement('p');totals.textContent=costCategories.map((k,i)=>costLabels[i]+': '+p.category_totals_rub[k]+' ₽').join('; ');el('price-itemized-result').replaceChildren(table,totals)}
function lineChange(){clearPricePreview();el('price-no-double').checked=false;syncCompanyControls()}
bind('price-line-add',async()=>{if(!companyCanWrite()||!isItemized())throw Error('Недостаточно прав');const l=readLine();if(priceEditing===null){if(priceLines.length>=60)throw Error('До 60 строк');priceLines.push(l)}else{priceLines[priceEditing]=l}resetLineEditor();renderLines();lineChange();return {lines:priceLines.length}});
bind('price-line-edit',async()=>{if(!companyCanWrite()||!isItemized()||selectedLine()===null||lineDraftDirty())throw Error('Выберите строку и завершите текущий черновик');priceEditing=selectedLine();for(const k of lineKeys)el('price-line-'+k).value=priceLines[priceEditing][k];el('price-line-add').textContent='Сохранить строку';el('price-line-status').textContent='Редактируется строка '+(priceEditing+1);lineChange();return {editing:priceEditing+1}});
bind('price-line-remove',async()=>{if(!companyCanWrite()||!isItemized()||selectedLine()===null||lineDraftDirty())throw Error('Выберите строку и завершите текущий черновик');priceLines.splice(selectedLine(),1);resetLineEditor();renderLines();lineChange();return {lines:priceLines.length}});
bind('price-line-cancel',async()=>{if(!companyCanWrite()||!isItemized())throw Error('Недостаточно прав');resetLineEditor();lineChange();return {cancelled:true}});
el('price-mode').addEventListener('change',()=>{clearPricePreview();syncCompanyControls()});el('price-line-select').addEventListener('change',syncCompanyControls);
for(const id of [...lineKeys.map(k=>'price-line-'+k),...costCategories.map(k=>'price-zero-'+k)]){el(id).addEventListener('input',lineChange);el(id).addEventListener('change',lineChange)}
el('price-no-double').addEventListener('change',()=>{clearPricePreview();syncCompanyControls()});
const costDocumentKinds=['QUOTE','INVOICE','CONTRACT','TIMESHEET','OTHER'];
function costVersion(){return priceHistory?.find(x=>x.scenario_id===val('price-version')&&x.itemized_estimate)}
function costLine(){return costVersion()?.itemized_estimate.lines.find(x=>String(x.ordinal)===val('price-cost-line'))}
function resetCostBinding(){costBinding=null;costEvidence=null;el('price-cost-file').value='';el('price-cost-kind').value='';el('price-cost-confirm').checked=false;el('price-cost-status').textContent='';el('price-cost-result').textContent='';el('price-cost-result').hidden=true}
function resetCostVersion(){resetActual();resetCostBinding();blankSelect('price-cost-line','Выберите строку')}
function setCostVersion(){resetCostVersion();const r=costVersion();if(r)for(const line of r.itemized_estimate.lines){const o=document.createElement('option');o.value=String(line.ordinal);o.textContent='v'+r.revision+' · '+line.ordinal+'. '+line.title+' · '+line.amount_rub+' ₽';el('price-cost-line').append(o)}}
function syncCostEvidence(read){const version=costVersion(),line=costLine(),active=Boolean(read&&version),selected=Boolean(active&&line),write=selected&&companyCanDecide()&&costBinding&&!costEvidence;el('price-cost-evidence-panel').hidden=!active;el('price-cost-load').disabled=uiBusy||!selected;el('price-cost-editor').hidden=!write;el('price-cost-save').disabled=uiBusy||!write||!costDocumentKinds.includes(val('price-cost-kind'))||!el('price-cost-file').files?.length||!el('price-cost-confirm').checked;el('price-cost-download').disabled=uiBusy||!selected||!costEvidence;el('price-cost-line').disabled=uiBusy||!active}
function costPath(version,line){return casePath()+'/price-scenarios/'+encodeURIComponent(version.scenario_id)+'/lines/'+line.ordinal+'/evidence'}
function canonicalCostJSON(value){if(Array.isArray(value))return '['+value.map(canonicalCostJSON).join(',')+']';if(value&&typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonicalCostJSON(value[k])).join(',')+'}';return JSON.stringify(value)}
async function costDigest(version,line){return sha256Bytes(new TextEncoder().encode(canonicalCostJSON({scenario_id:version.scenario_id,revision:version.revision,line})))}
function sameCostScope(r,version,line,digest){return r&&r.customer_id===requireCompany().customer_id&&r.case_id===companyCase.case_id&&r.scenario_id===version.scenario_id&&r.scenario_revision===version.revision&&r.line_ordinal===line.ordinal&&r.line_title===line.title&&r.line_amount_rub===line.amount_rub&&r.line_sha256===digest&&r.external_submission_allowed===false}
function validCostInspection(i,format){return ['pdf','docx','xlsx'].includes(format)&&i?.schema==='commercial_attachment_inspection_v1'&&i.format_hint===format&&i.format_check===(format==='pdf'?'PDF_HEADER_AND_EOF_ONLY':'BOUNDED_OOXML_PACKAGE_CHECK')&&typeof i.sha256==='string'&&digestPattern.test(i.sha256)&&Number.isSafeInteger(i.size_bytes)&&i.size_bytes>0&&i.size_bytes<=2097152&&i.text_preview_complete===false&&i.requirements_verified===false&&i.malware_free_verified===false&&i.digital_signature_verified===false&&!Object.hasOwn(i,'text_preview')}
function validCostEvidence(r,version,line,digest){return sameCostScope(r,version,line,digest)&&typeof r.evidence_id==='string'&&r.evidence_id.length>0&&typeof r.member_id==='string'&&r.member_id.length>0&&r.origin==='USER_SUPPLIED_UNATTESTED'&&r.stored_bytes_reverified===true&&r.document_origin_verified===false&&r.cost_amount_verified===false&&r.payment_verified===false&&costDocumentKinds.includes(r.document_kind)&&validCostInspection(r.inspection,r.format_hint)}
function costMismatch(){clearSession();throw Error('Несоответствие документа или привязки строки сметы')}
function showCostEvidence(r){costEvidence=r;el('price-cost-result').textContent=JSON.stringify(r,null,2);el('price-cost-result').hidden=false;el('price-cost-status').textContent='Копия сохранена; проверена целостность байтов, не источник, сумма или оплата.';el('price-cost-file').value='';el('price-cost-confirm').checked=false}
el('price-cost-line').addEventListener('change',()=>{resetCostBinding();syncCompanyControls()});
for(const id of ['price-cost-file','price-cost-kind'])el(id).addEventListener('change',()=>{el('price-cost-confirm').checked=false;syncCompanyControls()});el('price-cost-confirm').addEventListener('change',syncCompanyControls);
bind('price-cost-load',async()=>{const v=costVersion(),l=costLine();if(!companyCanWrite()||!v||!l)throw Error('Выберите сохранённую строку');resetCostBinding();const digest=await costDigest(v,l);let r;try{r=await call(costPath(v,l))}catch(e){if(e.status!==404)throw e;el('price-cost-status').textContent='Функция недоступна или строка не найдена.';return {available:false}}if(!sameCostScope(r,v,l,digest)||!Object.hasOwn(r,'evidence')||(r.evidence!==null&&!validCostEvidence(r.evidence,v,l,digest)))costMismatch();costBinding=r;if(r.evidence)showCostEvidence(r.evidence);else el('price-cost-status').textContent='Документ пока не приложен к этой версии и строке.';return {available:Boolean(costEvidence)}});
bind('price-cost-save',async()=>{const v=costVersion(),l=costLine(),binding=costBinding,file=el('price-cost-file').files?.[0],kind=val('price-cost-kind');if(!companyCanDecide()||!v||!l||!binding||costEvidence||!file||!costDocumentKinds.includes(kind)||!el('price-cost-confirm').checked)throw Error('Проверьте строку, выберите вид документа и подтвердите привязку');const format=file.name.split('.').pop().toLowerCase();if(!['pdf','docx','xlsx'].includes(format)||!Number.isSafeInteger(file.size)||file.size<1||file.size>2097152)throw Error('Допустимы PDF/DOCX/XLSX до 2 МБ');const digest=await costDigest(v,l);if(!sameCostScope(binding,v,l,digest))costMismatch();const sha=await sha256Bytes(await file.arrayBuffer());el('price-cost-confirm').checked=false;const query=new URLSearchParams({format_hint:format,document_kind:kind,line_sha256:digest,confirm_user_supplied:'true'});let r;try{r=await call(costPath(v,l)+'?'+query.toString(),{method:'POST',body:file,upload:true})}catch(e){if(e.status===409){resetCostBinding();el('price-cost-status').textContent='Привязка изменилась или документ уже приложен. Проверьте строку заново.'}else el('price-cost-status').textContent='Запись не подтверждена. Можно проверить строку или повторить тот же файл и вид документа.';throw e}if(!validCostEvidence(r,v,l,digest)||r.member_id!==requireCompany().member_id||r.document_kind!==kind||r.format_hint!==format||r.inspection.sha256!==sha||r.inspection.size_bytes!==file.size)costMismatch();showCostEvidence(r);return {attached:true,stored_bytes_reverified:true}});
async function verifiedCostDownload(path,artifact,prefix,stillCurrent){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);let bytes,offset=0;try{const r=await fetch(path,{method:'GET',credentials:'omit',cache:'no-store',redirect:'error',signal:controller.signal,headers:{Authorization:'Bearer '+token,Accept:'application/octet-stream','Cache-Control':'no-store'}});if(!r.ok){const e=Error('HTTP '+r.status);e.status=r.status;throw e}if(r.headers.get('x-artifact-sha256')!==artifact.inspection.sha256||!r.body)throw Error('Нет контрольной суммы документа');const size=artifact.inspection.size_bytes;bytes=new Uint8Array(size);const reader=r.body.getReader();try{while(true){const {value,done}=await reader.read();if(done)break;if(offset+value.length>size)throw Error('Размер файла не совпадает');bytes.set(value,offset);offset+=value.length}}finally{await reader.cancel().catch(()=>{});reader.releaseLock()}if(offset!==size||await sha256Bytes(bytes)!==artifact.inspection.sha256||!stillCurrent())throw Error('Контрольная сумма или привязка не совпадает')}finally{controller.abort();clearTimeout(timer)}const url=URL.createObjectURL(new Blob([bytes],{type:'application/octet-stream'}));try{const link=document.createElement('a');link.href=url;link.download=prefix+'-'+artifact.inspection.sha256.slice(0,16)+'.'+artifact.format_hint;link.click()}finally{setTimeout(()=>URL.revokeObjectURL(url),1000)}return {downloaded_bytes:offset,sha256:artifact.inspection.sha256}}
bind('price-cost-download',async()=>{const v=costVersion(),l=costLine(),artifact=costEvidence,epoch=sessionEpoch;if(!companyCanWrite()||!v||!l||!artifact||!token)throw Error('Сначала проверьте документ');if(!validCostEvidence(artifact,v,l,await costDigest(v,l)))costMismatch();return verifiedCostDownload(costPath(v,l)+'/download',artifact,'cost',()=>epoch===sessionEpoch&&costVersion()===v&&costLine()===l&&costEvidence===artifact)});
const actualExtraKeys=['category','title','unit','quantity','rate_rub','source_note'];
function invalidateActual(){actualPreview=null;actualPending=null;el('actual-save-confirm').checked=false;el('actual-result').replaceChildren();el('actual-status').textContent=''}
function clearActualLine(){for(const id of ['quantity','rate','source'])el('actual-'+id).value=''}
function clearActualExtra(){for(const k of actualExtraKeys)el('actual-extra-'+k).value=k==='category'?costCategories[0]:''}
function resetActual(){resetActualEvidenceVersion();actualSelectedLine='';actualHistory=null;actualDigest=null;actualObservations=[];actualExtras=[];invalidateActual();clearActualLine();clearActualExtra();for(const id of ['actual-date','actual-note'])el(id).value='';for(const id of ['actual-confirm','actual-no-double'])el(id).checked=false;for(const id of ['actual-line','actual-history','actual-extra-select'])blankSelect(id,'Выберите строку');for(const id of ['actual-observations','actual-extra-list','actual-history-result'])el(id).replaceChildren();el('actual-line-plan').textContent=''}
function actualLine(){return costVersion()?.itemized_estimate.lines.find(x=>String(x.ordinal)===val('actual-line'))}
function actualPath(v){return casePath()+'/price-scenarios/'+encodeURIComponent(v.scenario_id)+'/actual-costs'}
function actualMismatch(){clearSession();throw Error('Несоответствие плана или фактического среза')}
function actualScope(r,v,d){return r&&r.customer_id===requireCompany().customer_id&&r.case_id===companyCase.case_id&&r.scenario_id===v.scenario_id&&r.scenario_revision===v.revision&&r.baseline_sha256===d&&r.external_submission_allowed===false}
function actualTable(headers,rows){const t=document.createElement('table');for(const [i,row] of [headers,...rows].entries()){const tr=document.createElement('tr');for(const value of row){const c=document.createElement(i?'td':'th');c.textContent=value??'—';tr.append(c)}t.append(tr)}return t}
function renderActualInputs(){const v=costVersion();el('actual-observations').replaceChildren(actualTable(['Строка','План, ₽','Количество факта','Ставка, ₽','Источник'],(v?.itemized_estimate.lines??[]).map(l=>{const x=actualObservations.find(o=>o.ordinal===l.ordinal);return [l.title,l.amount_rub,x?.quantity??'Не заявлено',x?.rate_rub,x?.source_note]})));blankSelect('actual-extra-select','Выберите расход');for(const [i,l] of actualExtras.entries()){const o=document.createElement('option');o.value=String(i);o.textContent=l.title;el('actual-extra-select').append(o)}el('actual-extra-list').replaceChildren(actualTable(['Внеплановая позиция','Количество','Ставка','Источник'],actualExtras.map(l=>[l.title,l.quantity+' '+l.unit,l.rate_rub,l.source_note])))}
function actualChanged(){invalidateActual();el('actual-no-double').checked=false;syncCompanyControls()}
function actualLineDirty(){const l=actualLine(),x=actualObservations.find(o=>o.ordinal===l?.ordinal);return val('actual-quantity')!==(x?.quantity??'')||val('actual-rate')!==(x?.rate_rub??'')||val('actual-source')!==(x?.source_note??'')}
function actualExtraDirty(){return actualExtraKeys.slice(1).some(k=>val('actual-extra-'+k))}
function syncActual(read){const active=Boolean(read&&costVersion()),open=active&&actualHistory!==null,write=open&&companyCanDecide();el('actual-panel').hidden=!active;el('actual-editor').hidden=!open;el('actual-load').disabled=uiBusy||!active;el('actual-line-save').disabled=uiBusy||!open||!actualLine();el('actual-line-clear').disabled=uiBusy||!open||!actualLine();el('actual-extra-add').disabled=uiBusy||!open||actualExtras.length>=30;el('actual-extra-remove').disabled=uiBusy||!open||val('actual-extra-select')===''||actualExtraDirty();el('actual-preview').disabled=uiBusy||!open||!el('actual-confirm').checked||!el('actual-no-double').checked;el('actual-save-label').hidden=!write;el('actual-save').disabled=uiBusy||!write||!actualPreview||!el('actual-save-confirm').checked||(actualHistory?.[0]?.revision??0)>=30;el('actual-show').disabled=uiBusy||!open||!actualHistory?.some(x=>x.snapshot_id===val('actual-history'))}
function validObservation(o){return o&&Number.isInteger(o.ordinal)&&typeof o.quantity==='string'&&/^[0-9]{1,9}(\\.[0-9]{1,4})?$/.test(o.quantity)&&typeof o.rate_rub==='string'&&/^[0-9]{1,12}(\\.[0-9]{1,2})?$/.test(o.rate_rub)&&(Number(o.quantity)!==0||Number(o.rate_rub)===0)&&typeof o.source_note==='string'&&o.source_note.length>0&&o.source_note.length<=500&&o.source_note.trim()===o.source_note}
function actualInput(){if(actualLineDirty()||actualExtraDirty())throw Error('Сначала сохраните или очистите черновик строки');const p={baseline_sha256:actualDigest,as_of:val('actual-date'),observations:actualObservations.map(x=>({...x})),unplanned_costs:actualExtras.map(x=>({...x})),note:val('actual-note'),confirm_cumulative_user_report:el('actual-confirm').checked,confirm_no_double_count:el('actual-no-double').checked};if(!validActualInput(p,costVersion(),actualDigest))throw Error('Заполните дату, источники, наблюдения и подтверждения');return p}
function validActualInput(p,v,d){return p&&p.baseline_sha256===d&&typeof p.as_of==='string'&&/^\\d{4}-\\d{2}-\\d{2}$/.test(p.as_of)&&typeof p.note==='string'&&p.note.trim()===p.note&&p.note.length>0&&p.note.length<=2000&&p.confirm_cumulative_user_report===true&&p.confirm_no_double_count===true&&Array.isArray(p.observations)&&p.observations.length<=60&&p.observations.every(o=>validObservation(o)&&v.itemized_estimate.lines.some(l=>l.ordinal===o.ordinal))&&new Set(p.observations.map(o=>o.ordinal)).size===p.observations.length&&Array.isArray(p.unplanned_costs)&&p.unplanned_costs.length<=30&&p.unplanned_costs.every(l=>validLine(l)&&l.source_kind==='USER_REPORTED_ACTUAL')&&p.observations.length+p.unplanned_costs.length>0}
function signedRub(n){return n<0n?'-'+asRub(-n):asRub(n)}
function actualPercent(delta,base){if(!base)return null;const neg=delta<0n,n=(neg?-delta:delta)*1000000n,q=(n*2n+base)/(2n*base);return (neg?'-':'')+(q/10000n).toString()+'.'+(q%10000n).toString().padStart(4,'0')}
function validActualResult(r,p,v,d){try{
 if(!validActualInput(p,v,d)||r?.schema!=='company_actual_cost_snapshot_v1'||r.currency!=='RUB'||r.baseline_sha256!==d||r.as_of!==p.as_of||r.rounding_policy!=='CEIL_EACH_LINE_TO_KOPECKS_THEN_SUM'||r.basis!=='CUMULATIVE_USER_REPORTED_COSTS_BEFORE_REVENUE_RATES'||r.origin!=='USER_REPORTED_UNVERIFIED'||!['payment_verified','actual_amounts_independently_verified','contract_cost_coverage_complete','contract_execution_verified','revenue_or_profit_verified','external_submission_allowed'].every(k=>r[k]===false))return false;
 const empty=()=>({plan:0n,matched:0n,observed:0n,extra:0n,missing:0});const sums=Object.fromEntries(costCategories.map(k=>[k,empty()])),total=empty();const amount=(q,rate)=>(scaledInt(q,4)*scaledInt(rate,2)+9999n)/10000n;
 const lines=v.itemized_estimate.lines.map(l=>{const plan=scaledInt(l.amount_rub,2),t=sums[l.category],o=p.observations.find(x=>x.ordinal===l.ordinal);t.plan+=plan;const base={ordinal:l.ordinal,title:l.title,category:l.category,unit:l.unit,planned_quantity:l.quantity,planned_rate_rub:l.rate_rub,planned_amount_rub:l.amount_rub};if(!o){t.missing++;return {...base,status:'NOT_REPORTED',actual_quantity:null,actual_rate_rub:null,actual_amount_rub:null,variance_rub:null,variance_percent:null,source_note:null}}const a=amount(o.quantity,o.rate_rub);t.matched+=plan;t.observed+=a;return {...base,status:'USER_REPORTED_ACTUAL',actual_quantity:o.quantity,actual_rate_rub:o.rate_rub,actual_amount_rub:signedRub(a),variance_rub:signedRub(a-plan),variance_percent:actualPercent(a-plan,plan),source_note:o.source_note}});
 const extras=p.unplanned_costs.map((l,i)=>{const a=amount(l.quantity,l.rate_rub);sums[l.category].extra+=a;return {ordinal:i+1,...l,actual_amount_rub:asRub(a)}});if(!samePriceValue(r.lines,lines)||!samePriceValue(r.unplanned_costs,extras))return false;
 const report=t=>({planned_rub:asRub(t.plan),matched_planned_rub:asRub(t.matched),reported_planned_line_actual_rub:asRub(t.observed),reported_unplanned_rub:asRub(t.extra),reported_total_rub:asRub(t.observed+t.extra),missing_planned_lines:t.missing,matched_variance_rub:t.matched?signedRub(t.observed-t.matched):null,matched_variance_percent:actualPercent(t.observed-t.matched,t.matched),all_planned_lines_reported:t.missing===0,reported_vs_full_plan_rub:t.missing===0?signedRub(t.observed+t.extra-t.plan):null});
 for(const t of Object.values(sums)){if(t.observed+t.extra>99999999999999n)return false;for(const k of Object.keys(total))total[k]+=t[k]}
 return samePriceValue(r.category_totals,Object.fromEntries(costCategories.map(k=>[k,report(sums[k])])))&&samePriceValue(r.totals,report(total));
 }catch{return false}}
function validActualRecord(x,v,d){return actualScope(x,v,d)&&typeof x.snapshot_id==='string'&&x.snapshot_id.length>0&&Number.isInteger(x.revision)&&x.revision>=1&&x.revision<=30&&typeof x.member_id==='string'&&x.member_id.length>0&&validActualResult(x.result,x.inputs,v,d)}
function renderActualResult(container,r){const h=document.createElement('p');h.textContent='На '+r.as_of+': заявлено '+r.totals.reported_total_rub+' ₽, внеплановые '+r.totals.reported_unplanned_rub+' ₽. Незаявленных строк: '+r.totals.missing_planned_lines+'. '+(r.totals.reported_vs_full_plan_rub===null?'Отклонение от всей сметы не рассчитано.':'Отклонение заявленного факта от всей сметы: '+r.totals.reported_vs_full_plan_rub+' ₽; полнота затрат договора не подтверждена.');const table=actualTable(['Позиция','План, ₽','Факт, ₽','Отклонение, ₽','Отклонение, %','Источник'],r.lines.map(l=>[l.title,l.planned_amount_rub,l.actual_amount_rub??'Не заявлено',l.variance_rub,l.variance_percent,l.source_note]));const extra=actualTable(['Внеплановая позиция','Факт, ₽','Источник'],r.unplanned_costs.map(l=>[l.title,l.actual_amount_rub,l.source_note]));const cats=actualTable(['Категория','План, ₽','Заявлено, ₽','Внеплановые, ₽','Незаявлено строк','Отклонение сопоставимых строк, ₽'],costCategories.map((k,i)=>{const t=r.category_totals[k];return [costLabels[i],t.planned_rub,t.reported_total_rub,t.reported_unplanned_rub,String(t.missing_planned_lines),t.matched_variance_rub]}));el(container).replaceChildren(h,table,extra,cats)}
function renderActualHistory(rows){resetActualEvidenceVersion();actualHistory=rows;blankSelect('actual-history','Выберите срез');el('actual-history-result').replaceChildren();for(const x of rows){const o=document.createElement('option');o.value=x.snapshot_id;o.textContent='v'+x.revision+' · '+x.inputs.as_of;el('actual-history').append(o)}}
bind('actual-load',async()=>{const v=costVersion();if(!companyCanWrite()||!v)throw Error('Выберите сохранённую смету');resetActual();const d=await sha256Bytes(new TextEncoder().encode(canonicalCostJSON({scenario_id:v.scenario_id,revision:v.revision,estimate:v.itemized_estimate})));const rows=[];let more=true;while(more){let r;try{r=await call(actualPath(v)+'?offset='+rows.length+'&limit=10')}catch(e){if(e.status===404){el('actual-status').textContent='Функция недоступна или смета не найдена.';return {available:false}}throw e}if(costVersion()!==v||!actualScope(r,v,d)||!samePriceValue(r.planned_lines,v.itemized_estimate.lines)||typeof r.has_more!=='boolean'||!Array.isArray(r.items)||r.items.length>10||r.has_more&&r.items.length!==10||rows.length+r.items.length>30||!r.items.every(x=>validActualRecord(x,v,d)))actualMismatch();rows.push(...r.items);more=r.has_more;if(more&&rows.length>=30)actualMismatch()}if(!rows.every((x,i)=>x.revision===rows.length-i)||new Set(rows.map(x=>x.snapshot_id)).size!==rows.length)actualMismatch();actualDigest=d;for(const l of v.itemized_estimate.lines){const o=document.createElement('option');o.value=String(l.ordinal);o.textContent=l.ordinal+'. '+l.title+' · '+l.amount_rub+' ₽';el('actual-line').append(o)}renderActualHistory(rows);renderActualInputs();el('actual-status').textContent='Введите новый накопительный срез. Прошлые значения не переносятся автоматически.';return {versions:rows.length}});
function updateActualLine(){clearActualLine();const l=actualLine();el('actual-line-plan').textContent=l?l.quantity+' '+l.unit+' × '+l.rate_rub+' ₽ = '+l.amount_rub+' ₽':'';const x=actualObservations.find(o=>o.ordinal===l?.ordinal);if(x){el('actual-quantity').value=x.quantity;el('actual-rate').value=x.rate_rub;el('actual-source').value=x.source_note}}

el('actual-line').addEventListener('change',()=>{const next=val('actual-line');el('actual-line').value=actualSelectedLine;if(actualLineDirty()){el('actual-status').textContent='Сохраните или снимите наблюдение перед сменой строки.';return}el('actual-line').value=next;actualSelectedLine=next;updateActualLine();syncCompanyControls()});
bind('actual-line-save',async()=>{const l=actualLine();if(!companyCanWrite()||actualHistory===null||!l)throw Error('Выберите строку');const o={ordinal:l.ordinal,quantity:val('actual-quantity').replace(',','.'),rate_rub:val('actual-rate').replace(',','.'),source_note:val('actual-source')};if(!validObservation(o))throw Error('Укажите количество, ставку и источник. Для нулевого количества ставка должна быть 0.');actualObservations=actualObservations.filter(x=>x.ordinal!==o.ordinal).concat(o).sort((a,b)=>a.ordinal-b.ordinal);updateActualLine();renderActualInputs();actualChanged();return {observed:actualObservations.length}});
bind('actual-line-clear',async()=>{const l=actualLine();if(!companyCanWrite()||actualHistory===null||!l)throw Error('Выберите строку');actualObservations=actualObservations.filter(x=>x.ordinal!==l.ordinal);updateActualLine();renderActualInputs();actualChanged();return {observed:actualObservations.length}});
bind('actual-extra-add',async()=>{if(!companyCanWrite()||actualHistory===null||actualExtras.length>=30)throw Error('Недоступно');const l=Object.fromEntries(actualExtraKeys.map(k=>[k,val('actual-extra-'+k)]));l.quantity=l.quantity.replace(',','.');l.rate_rub=l.rate_rub.replace(',','.');l.source_kind='USER_REPORTED_ACTUAL';if(!validLine(l))throw Error('Заполните внеплановую позицию и источник');actualExtras.push(l);clearActualExtra();renderActualInputs();actualChanged();return {extras:actualExtras.length}});
bind('actual-extra-cancel',async()=>{clearActualExtra();actualChanged();return {cancelled:true}});
bind('actual-extra-remove',async()=>{const value=val('actual-extra-select'),i=Number(value);if(!companyCanWrite()||actualHistory===null||actualExtraDirty()||value===''||!Number.isInteger(i)||!actualExtras[i])throw Error('Выберите расход');actualExtras.splice(i,1);renderActualInputs();actualChanged();return {extras:actualExtras.length}});
for(const id of ['actual-date','actual-note','actual-quantity','actual-rate','actual-source',...actualExtraKeys.map(k=>'actual-extra-'+k)]){el(id).addEventListener('input',actualChanged);el(id).addEventListener('change',actualChanged)}
for(const id of ['actual-confirm','actual-no-double'])el(id).addEventListener('change',()=>{invalidateActual();syncCompanyControls()});for(const id of ['actual-save-confirm','actual-history','actual-extra-select'])el(id).addEventListener('change',syncCompanyControls);
bind('actual-preview',async()=>{const v=costVersion();if(!companyCanWrite()||!v||actualHistory===null)throw Error('Загрузите историю');invalidateActual();const p=actualInput(),r=await call(actualPath(v)+'/preview',{method:'POST',body:p});if(costVersion()!==v||!actualScope(r,v,actualDigest)||r.inputs_stored!==false||!validActualResult(r.result,p,v,actualDigest))actualMismatch();actualPreview={inputs:p,result:r.result};renderActualResult('actual-result',r.result);el('actual-status').textContent='Предварительный расчёт. Не сохранён.';return {preview:true}});
bind('actual-save',async()=>{const v=costVersion();if(!companyCanDecide()||!v||actualHistory===null||!actualPreview||!el('actual-save-confirm').checked)throw Error('Рассчитайте и подтвердите сохранение');const p=actualInput(),rev=actualHistory[0]?.revision??0;if(!samePriceValue(p,actualPreview.inputs)||rev>=30){invalidateActual();throw Error('Расчёт изменился или достигнут лимит')}if(!actualPending){if(!globalThis.crypto?.randomUUID)throw Error('Требуется HTTPS');actualPending={expected_revision:rev,idempotency_key:crypto.randomUUID(),snapshot:p}}const draft=actualPending;el('actual-save-confirm').checked=false;let r;try{r=await call(actualPath(v),{method:'POST',body:draft})}catch(e){if(e.status===409){resetActual();el('actual-status').textContent='Версия или дата конфликтует. Загрузите историю и пересчитайте.'}else el('actual-status').textContent='Запись не подтверждена. Повторите тот же срез или проверьте историю.';throw e}if(costVersion()!==v||!validActualRecord(r,v,actualDigest)||r.member_id!==requireCompany().member_id||r.revision!==rev+1||!samePriceValue(r.inputs,p)||!samePriceValue(r.result,actualPreview.result))actualMismatch();renderActualHistory([r,...actualHistory]);invalidateActual();el('actual-status').textContent='Срез v'+r.revision+' сохранён. Не подтверждение оплаты.';return {saved_revision:r.revision}});
bind('actual-show',async()=>{if(!companyCanWrite())throw Error('Недостаточно прав');const r=actualHistory?.find(x=>x.snapshot_id===val('actual-history'));if(!r)throw Error('Выберите срез');renderActualResult('actual-history-result',r.result);const note=document.createElement('p');note.textContent='Обоснование: '+r.inputs.note;el('actual-history-result').append(note);return {viewed_revision:r.revision}});
const actualDocumentKinds=['INVOICE','CONTRACT','TIMESHEET','ACCEPTANCE_ACT','PAYMENT_RECORD','OTHER'];
function selectedActualSnapshot(){return actualHistory?.find(x=>x.snapshot_id===val('actual-history'))}
function actualEvidenceRows(snapshot){return snapshot?[...snapshot.result.lines.filter(l=>l.status==='USER_REPORTED_ACTUAL').map(line=>({kind:'PLANNED',line})),...snapshot.result.unplanned_costs.map(line=>({kind:'UNPLANNED',line}))]:[]}
function actualEvidenceRow(s=selectedActualSnapshot()){return actualEvidenceRows(s).find(x=>x.kind+':'+x.line.ordinal===val('actual-evidence-row'))}
function resetActualEvidence(){actualEvidenceBinding=null;actualEvidence=null;el('actual-evidence-file').value='';el('actual-evidence-kind').value='';el('actual-evidence-confirm').checked=false;el('actual-evidence-status').textContent='';el('actual-evidence-result').textContent='';el('actual-evidence-result').hidden=true}
function resetActualEvidenceVersion(){resetActualEvidence();blankSelect('actual-evidence-row','Выберите заявленную строку')}
function setActualEvidenceVersion(){resetActualEvidenceVersion();for(const x of actualEvidenceRows(selectedActualSnapshot())){const o=document.createElement('option');o.value=x.kind+':'+x.line.ordinal;o.textContent=(x.kind==='PLANNED'?'Плановая':'Внеплановая')+' · '+x.line.ordinal+'. '+x.line.title+' · '+x.line.actual_amount_rub+' ₽';el('actual-evidence-row').append(o)}}
function syncActualEvidence(read){const s=selectedActualSnapshot(),active=Boolean(read&&costVersion()&&s),selected=Boolean(active&&actualEvidenceRow(s)),write=selected&&companyCanDecide()&&actualEvidenceBinding&&!actualEvidence;el('actual-evidence-panel').hidden=!active;el('actual-evidence-row').disabled=uiBusy||!active;el('actual-evidence-load').disabled=uiBusy||!selected;el('actual-evidence-editor').hidden=!write;el('actual-evidence-save').disabled=uiBusy||!write||!actualDocumentKinds.includes(val('actual-evidence-kind'))||!el('actual-evidence-file').files?.length||!el('actual-evidence-confirm').checked;el('actual-evidence-download').disabled=uiBusy||!selected||!actualEvidence}
function actualEvidencePath(v,s,x){return actualPath(v)+'/'+encodeURIComponent(s.snapshot_id)+'/rows/'+x.kind+'/'+x.line.ordinal+'/evidence'}
async function actualEvidenceDigest(v,s,x){return sha256Bytes(new TextEncoder().encode(canonicalCostJSON({scenario_id:v.scenario_id,scenario_revision:v.revision,baseline_sha256:actualDigest,snapshot_id:s.snapshot_id,snapshot_revision:s.revision,as_of:s.inputs.as_of,row_kind:x.kind,line:x.line})))}
function actualEvidenceScope(r,v,s,x,digest){return actualScope(r,v,actualDigest)&&r.snapshot_id===s.snapshot_id&&r.snapshot_revision===s.revision&&r.as_of===s.inputs.as_of&&r.row_kind===x.kind&&r.line_ordinal===x.line.ordinal&&r.line_title===x.line.title&&r.actual_amount_rub===x.line.actual_amount_rub&&r.line_sha256===digest}
function validActualEvidence(r,v,s,x,digest){return actualEvidenceScope(r,v,s,x,digest)&&typeof r.evidence_id==='string'&&r.evidence_id.length>0&&typeof r.member_id==='string'&&r.member_id.length>0&&r.origin==='USER_SUPPLIED_UNATTESTED'&&r.stored_bytes_reverified===true&&['document_origin_verified','actual_amount_verified','payment_verified','contract_execution_verified'].every(k=>r[k]===false)&&actualDocumentKinds.includes(r.document_kind)&&validCostInspection(r.inspection,r.format_hint)}
function sameActualEvidenceSelection(v,s,x){const current=actualEvidenceRow();return costVersion()===v&&selectedActualSnapshot()===s&&current?.kind===x.kind&&current.line===x.line}
function actualEvidenceMismatch(){clearSession();throw Error('Несоответствие документа факта или привязки среза')}
function showActualEvidence(r){actualEvidence=r;el('actual-evidence-result').textContent=JSON.stringify(r,null,2);el('actual-evidence-result').hidden=false;el('actual-evidence-file').value='';el('actual-evidence-confirm').checked=false;el('actual-evidence-status').textContent='Копия сохранена; целостность байтов проверена. Подлинность, сумма и оплата не подтверждены.'}
el('actual-history').addEventListener('change',()=>{el('actual-history-result').replaceChildren();setActualEvidenceVersion();syncCompanyControls()});
el('actual-evidence-row').addEventListener('change',()=>{resetActualEvidence();syncCompanyControls()});
for(const id of ['actual-evidence-kind','actual-evidence-file'])el(id).addEventListener('change',()=>{el('actual-evidence-confirm').checked=false;syncCompanyControls()});el('actual-evidence-confirm').addEventListener('change',syncCompanyControls);
bind('actual-evidence-load',async()=>{const v=costVersion(),s=selectedActualSnapshot(),x=actualEvidenceRow(s);if(!companyCanWrite()||!v||!s||!x)throw Error('Выберите сохранённый срез и заявленную строку');resetActualEvidence();const digest=await actualEvidenceDigest(v,s,x);let r;try{r=await call(actualEvidencePath(v,s,x))}catch(e){if(e.status!==404)throw e;el('actual-evidence-status').textContent='Функция недоступна или строка не найдена.';return {available:false}}if(!sameActualEvidenceSelection(v,s,x)||!actualEvidenceScope(r,v,s,x,digest)||!Object.hasOwn(r,'evidence')||(r.evidence!==null&&!validActualEvidence(r.evidence,v,s,x,digest)))actualEvidenceMismatch();actualEvidenceBinding=r;if(r.evidence)showActualEvidence(r.evidence);else el('actual-evidence-status').textContent='Документ пока не приложен к этому срезу и строке.';return {available:Boolean(actualEvidence)}});
bind('actual-evidence-save',async()=>{const v=costVersion(),s=selectedActualSnapshot(),x=actualEvidenceRow(s),binding=actualEvidenceBinding,file=el('actual-evidence-file').files?.[0],kind=val('actual-evidence-kind');if(!companyCanDecide()||!v||!s||!x||!binding||actualEvidence||!file||!actualDocumentKinds.includes(kind)||!el('actual-evidence-confirm').checked)throw Error('Проверьте строку, выберите вид документа и подтвердите привязку');const format=file.name.split('.').pop().toLowerCase();if(!['pdf','docx','xlsx'].includes(format)||!Number.isSafeInteger(file.size)||file.size<1||file.size>2097152)throw Error('Допустимы PDF/DOCX/XLSX до 2 МБ');const digest=await actualEvidenceDigest(v,s,x);if(!actualEvidenceScope(binding,v,s,x,digest))actualEvidenceMismatch();const sha=await sha256Bytes(await file.arrayBuffer());el('actual-evidence-confirm').checked=false;const query=new URLSearchParams({format_hint:format,document_kind:kind,line_sha256:digest,confirm_user_supplied:'true'});let r;try{r=await call(actualEvidencePath(v,s,x)+'?'+query.toString(),{method:'POST',body:file,upload:true})}catch(e){if(e.status===409){resetActualEvidence();el('actual-evidence-status').textContent='Привязка изменилась или документ уже приложен. Проверьте строку заново.'}else el('actual-evidence-status').textContent='Запись не подтверждена. Проверьте строку или повторите тот же файл и вид.';throw e}if(!sameActualEvidenceSelection(v,s,x)||!validActualEvidence(r,v,s,x,digest)||r.member_id!==requireCompany().member_id||r.document_kind!==kind||r.format_hint!==format||r.inspection.sha256!==sha||r.inspection.size_bytes!==file.size)actualEvidenceMismatch();showActualEvidence(r);return {attached:true,stored_bytes_reverified:true}});
bind('actual-evidence-download',async()=>{const v=costVersion(),s=selectedActualSnapshot(),x=actualEvidenceRow(s),artifact=actualEvidence,epoch=sessionEpoch;if(!companyCanWrite()||!v||!s||!x||!artifact||!token)throw Error('Сначала проверьте документ');if(!validActualEvidence(artifact,v,s,x,await actualEvidenceDigest(v,s,x)))actualEvidenceMismatch();return verifiedCostDownload(actualEvidencePath(v,s,x)+'/download',artifact,'actual',()=>epoch===sessionEpoch&&sameActualEvidenceSelection(v,s,x)&&actualEvidence===artifact)});

const sampleCategories=['own_labor_rub','external_direct_rub','cash_overhead_rub'];
function invalidateActualSamples(){invalidateNormDraft();el('actual-sample-comparable').checked=false;el('actual-sample-distinct').checked=false;el('actual-sample-result').replaceChildren();el('actual-sample-status').textContent=''}
function renderActualSamples(){el('actual-sample-list').replaceChildren(actualTable(['Закупка','Работа','Количество','Ставка, ₽','Сумма, ₽','Срез'],actualSamples.map(x=>[x.source_platform+':'+x.external_id,x.title,x.reported_quantity+' '+x.unit,x.reported_rate_rub,x.reported_amount_rub,'v'+x.snapshot_revision+' · '+x.as_of])));blankSelect('actual-sample-remove-select','Выберите закупку');for(const x of actualSamples){const o=document.createElement('option');o.value=x.case_id;o.textContent=x.source_platform+':'+x.external_id+' · '+x.title;el('actual-sample-remove-select').append(o)}}
function resetActualSamples(){actualSamples=[];invalidateActualSamples();renderActualSamples()}
function eligibleActualSample(){const v=costVersion(),s=selectedActualSnapshot(),x=actualEvidenceRow(s);if(!v||!s||s!==actualHistory?.[0]||!x||!companyCase||!sampleCategories.includes(x.line.category))return null;const l=x.line,q=x.kind==='PLANNED'?l.actual_quantity:l.quantity,rate=x.kind==='PLANNED'?l.actual_rate_rub:l.rate_rub;if(typeof q!=='string'||scaledInt(q,4)<=0n)return null;const platform=companyCase.source_platform??'eis',id=companyCase.external_id??companyCase.registry_number;if(typeof id!=='string'||!id||!['eis','b2bcenter','workspace'].includes(platform))return null;return {v,s,x,quantity:q,rate,platform,id}}
function syncActualSamples(read){const active=Boolean(read&&companyCase),candidate=active&&eligibleActualSample();el('actual-sample-panel').hidden=!active;el('actual-sample-add').disabled=uiBusy||!candidate||actualSamples.length>=20;el('actual-sample-remove').disabled=uiBusy||!active||!actualSamples.some(x=>x.case_id===val('actual-sample-remove-select'));el('actual-sample-clear').disabled=uiBusy||!active||!actualSamples.length;el('actual-sample-preview').disabled=uiBusy||!active||!actualSamples.length||!el('actual-sample-comparable').checked||!el('actual-sample-distinct').checked}
function sampleReference(x){return Object.fromEntries(['case_id','scenario_id','snapshot_id','row_kind','ordinal','line_sha256'].map(k=>[k,x[k]]))}
function sampleDistribution(values,inputDigits,outputDigits){const sorted=values.map(x=>scaledInt(x,inputDigits)).sort((a,b)=>a<b?-1:a>b?1:0),n=sorted.length,scale=10n**BigInt(outputDigits),base=10n**BigInt(inputDigits);const format=(numerator,denominator)=>{const q=(numerator*scale*2n+denominator)/(2n*denominator);return (q/scale).toString()+'.'+(q%scale).toString().padStart(outputDigits,'0')};return {minimum:format(sorted[0],base),median:format(sorted[Math.floor((n-1)/2)]+sorted[Math.floor(n/2)],2n*base),maximum:format(sorted[n-1],base)}}
function validSamplePreview(r,p,rows){if(r?.schema!=='company_actual_descriptive_sample_v1'||r.customer_id!==requireCompany().customer_id||r.category!==p.category||r.title!==p.title||r.unit!==p.unit||r.currency!=='RUB'||r.distinct_case_count!==rows.length||r.basis!=='EXPLICIT_ONE_CUMULATIVE_REPORTED_ROW_PER_DISTINCT_CASE'||r.small_sample_warning!==(rows.length<5)||r.recommended_rate!==null||!['comparability_independently_verified','actual_amounts_independently_verified','contract_execution_verified','approved_norm','inputs_stored','external_submission_allowed'].every(k=>r[k]===false)||!Array.isArray(r.samples)||r.samples.length!==rows.length)return false;
 const expected=rows.map(({category,...x})=>x);return samePriceValue(r.samples,expected)&&samePriceValue(r.reported_quantity_distribution,sampleDistribution(rows.map(x=>x.reported_quantity),4,4))&&samePriceValue(r.reported_unit_rate_distribution_rub,sampleDistribution(rows.map(x=>x.reported_rate_rub),2,3))&&samePriceValue(r.reported_amount_distribution_rub,sampleDistribution(rows.map(x=>x.reported_amount_rub),2,3))}


bind('actual-sample-add',async()=>{const c=eligibleActualSample();if(!companyCanWrite()||!c||actualSamples.length>=20)throw Error('Выберите заявленную строку последнего среза с положительным количеством');const {v,s,x,quantity,rate,platform,id}=c,l=x.line,first=actualSamples[0],caseId=companyCase.case_id;if(actualSamples.some(a=>a.case_id===caseId||(a.source_platform===platform&&a.external_id===id)))throw Error('Закупка уже в выборке; сначала исключите её');if(first&&(first.category!==l.category||first.title!==l.title||first.unit!==l.unit))throw Error('Выберите ту же работу, категорию и единицу без преобразования');const epoch=sessionEpoch,digest=await actualEvidenceDigest(v,s,x);if(epoch!==sessionEpoch||!sameActualEvidenceSelection(v,s,x)||companyCase.case_id!==caseId)throw Error('Выбор изменился');actualSamples.push({category:l.category,source_platform:platform,external_id:id,case_id:caseId,scenario_id:v.scenario_id,scenario_revision:v.revision,baseline_sha256:actualDigest,snapshot_id:s.snapshot_id,snapshot_revision:s.revision,row_kind:x.kind,ordinal:l.ordinal,line_sha256:digest,as_of:s.inputs.as_of,title:l.title,unit:l.unit,reported_quantity:quantity,reported_rate_rub:rate,reported_amount_rub:l.actual_amount_rub,origin:'USER_REPORTED_UNVERIFIED',actual_amount_verified:false});invalidateActualSamples();renderActualSamples();return {selected_count:actualSamples.length}});
bind('actual-sample-remove',async()=>{if(!companyCanWrite())throw Error('Недоступно');actualSamples=actualSamples.filter(x=>x.case_id!==val('actual-sample-remove-select'));invalidateActualSamples();renderActualSamples();return {selected_count:actualSamples.length}});
bind('actual-sample-clear',async()=>{resetActualSamples();return {cleared:true}});
for(const id of ['actual-sample-remove-select','actual-sample-comparable','actual-sample-distinct'])el(id).addEventListener('change',()=>{el('actual-sample-result').replaceChildren();invalidateNormDraft();syncCompanyControls()});
bind('actual-sample-preview',async()=>{if(!companyCanWrite()||!actualSamples.length||!el('actual-sample-comparable').checked||!el('actual-sample-distinct').checked)throw Error('Выберите и подтвердите сопоставимые строки');const rows=actualSamples.slice(),first=rows[0],epoch=sessionEpoch,p={category:first.category,title:first.title,unit:first.unit,samples:rows.map(sampleReference),confirm_comparable_reported_rows:true,confirm_one_cumulative_row_per_case:true};el('actual-sample-result').replaceChildren();let r;try{r=await call('/api/saas/company-portfolio/actual-samples/preview',{method:'POST',body:p})}catch(e){el('actual-sample-status').textContent=e.status===404?'Функция недоступна или строка не найдена.':e.status===409?'Срез устарел. Исключите его и выберите актуальный.':'Сравнение не получено.';throw e}if(epoch!==sessionEpoch||!validSamplePreview(r,p,rows)){clearSession();throw Error('Несоответствие выборки факта или расчёта')}const h=document.createElement('p');h.textContent='Закупок: '+r.distinct_case_count+'. '+(r.small_sample_warning?'Малая выборка. ':'')+'Заявленные данные не проверены; норматив и ставка не утверждены.';const table=actualTable(['Показатель','Минимум','Медиана','Максимум'],[['Количество, '+r.unit,r.reported_quantity_distribution],['Ставка, ₽',r.reported_unit_rate_distribution_rub],['Сумма, ₽',r.reported_amount_distribution_rub]].map(([k,v])=>[k,v.minimum,v.median,v.maximum]));el('actual-sample-result').replaceChildren(h,table);el('actual-sample-status').textContent='Предварительное сравнение. Не сохранено.';return {sample_count:rows.length,approved_norm:false}});

const normPath='/api/saas/company-portfolio/cost-norms';
const normHash=x=>sha256Bytes(new TextEncoder().encode(canonicalCostJSON(x)));
function invalidateNormDraft(){normDraft=null;el('cost-norm-preview-result').replaceChildren();el('cost-norm-approve-confirm').checked=false}
function resetNormCatalog(){normPending=null;normCatalog=[];normOffset=0;normMore=false;normHistory=null;invalidateNormDraft();for(const id of ['quantity','rate','note','withdraw-note'])el('cost-norm-'+id).value='';for(const id of ['limits','withdraw-confirm'])el('cost-norm-'+id).checked=false;blankSelect('cost-norm-select','Выберите норматив');el('cost-norm-catalog').replaceChildren();el('cost-norm-history-result').replaceChildren();el('cost-norm-status').textContent=''}
function selectedNorm(){return normCatalog.find(x=>x.norm_key===val('cost-norm-select'))}
function syncNormControls(){const read=companyCanWrite(),write=companyCanDecide(),item=selectedNorm(),hasSample=!!(read&&companyCase&&actualSamples.length);el('cost-norm-panel').hidden=!read;el('cost-norm-manager').hidden=!write;el('cost-norm-proposal-panel').hidden=!hasSample;el('cost-norm-approval-panel').hidden=!write;
 for(const [id,enabled] of Object.entries({load:read,prev:read&&normOffset>0,next:read&&normMore,history:read&&item,'history-prev':read&&item&&normHistory?.key===item.norm_key&&normHistory.offset>0,'history-next':read&&item&&normHistory?.key===item.norm_key&&normHistory.more,withdraw:write&&item?.action==='APPROVED'&&el('cost-norm-withdraw-confirm').checked&&val('cost-norm-withdraw-note').length>=10,preview:hasSample&&el('actual-sample-comparable').checked&&el('actual-sample-distinct').checked&&el('cost-norm-limits').checked,approve:write&&hasSample&&normDraft&&el('cost-norm-approve-confirm').checked}))el('cost-norm-'+id).disabled=uiBusy||!enabled;
}
function normProposal(){const f=actualSamples[0];if(!companyCanWrite()||!f||!el('actual-sample-comparable').checked||!el('actual-sample-distinct').checked||!el('cost-norm-limits').checked)throw Error('Подтвердите источники и сопоставимость.');const q=val('cost-norm-quantity').replace(',','.'),r=val('cost-norm-rate').replace(',','.'),note=val('cost-norm-note');if(!/^[0-9]{1,9}(\\.[0-9]{1,4})?$/.test(q)||scaledInt(q,4)<=0n||!/^[0-9]{1,12}(\\.[0-9]{1,2})?$/.test(r)||note.length<10||note.length>2000)throw Error('Укажите положительное количество, ставку и обоснование (10–2000 символов).');return {sample:{category:f.category,title:f.title,unit:f.unit,samples:actualSamples.map(sampleReference),confirm_comparable_reported_rows:true,confirm_one_cumulative_row_per_case:true},norm_quantity:q,norm_rate_rub:r,rationale:note,confirm_reported_source_limits:true}}
function normIntegrity(){clearSession();throw Error('Несоответствие корпоративного норматива или контрольной суммы')}
async function validNormDraft(r,p,rows){if(!r||r.schema!=='company_cost_norm_preview_v1'||r.customer_id!==requireCompany().customer_id||!digestPattern.test(r.norm_key)||!digestPattern.test(r.preview_sha256)||!Number.isInteger(r.expected_revision)||r.expected_revision<0||r.expected_revision>100||!samePriceValue(r.proposal,p)||!['approved_norm','automatically_applied','inputs_stored','external_submission_allowed'].every(k=>r[k]===false)||!validSamplePreview(r.sample_observation,p.sample,rows))return false;const {preview_sha256,...value}=r;return preview_sha256===await normHash(value)}

async function validNormRecord(r){if(!r||r.schema!=='company_cost_norm_version_v1'||r.customer_id!==requireCompany().customer_id||typeof r.norm_id!=='string'||!r.norm_id||typeof r.member_id!=='string'||!r.member_id||!digestPattern.test(r.norm_key)||!digestPattern.test(r.record_sha256)||!Number.isInteger(r.revision)||r.revision<1||r.revision>100||!['APPROVED','WITHDRAWN'].includes(r.action)||r.external_submission_allowed!==false||r.automatically_applied!==false||r.result?.approved_norm!==(r.action==='APPROVED')||r.result.automatically_applied!==false||r.result.external_submission_allowed!==false||!sampleCategories.includes(r.result.category)||typeof r.result.title!=='string'||typeof r.result.unit!=='string'||r.result.currency!=='RUB'||typeof r.result.rationale!=='string'||r.inputs?.expected_revision!==r.revision-1||typeof r.inputs.idempotency_key!=='string'||typeof r.created_at!=='string')return false;
 const x=r.result,p=r.inputs;if(r.action==='APPROVED'){if(p.confirm_internal_approval!==true||p.proposal?.confirm_reported_source_limits!==true||!digestPattern.test(p.preview_sha256)||p.preview_sha256!==x.preview_sha256||!p.proposal.sample||x.norm_quantity!==p.proposal.norm_quantity||x.norm_rate_rub!==p.proposal.norm_rate_rub||x.rationale!==p.proposal.rationale||x.title!==p.proposal.sample.title||x.unit!==p.proposal.sample.unit||x.category!==p.proposal.sample.category||x.origin!=='EXPLICIT_INTERNAL_MANAGER_APPROVAL'||x.actual_amounts_independently_verified!==false||!Array.isArray(x.sample_observation?.samples)||x.sample_observation.samples.length<1||x.sample_observation.samples.length>20)return false;const rows=x.sample_observation.samples.map(a=>({...a,category:x.category}));if(!validSamplePreview(x.sample_observation,p.proposal.sample,rows)||!samePriceValue(rows.map(sampleReference),p.proposal.sample.samples))return false;
 const preview={schema:'company_cost_norm_preview_v1',customer_id:r.customer_id,norm_key:r.norm_key,expected_revision:p.expected_revision,proposal:p.proposal,sample_observation:x.sample_observation,approved_norm:false,automatically_applied:false,inputs_stored:false,external_submission_allowed:false};if(await normHash(preview)!==p.preview_sha256)return false;
 }else if(p.confirm_withdrawal!==true||x.rationale!==p.rationale||!digestPattern.test(x.withdrawn_record_sha256)||typeof x.withdrawn_norm_id!=='string'||Object.hasOwn(x,'norm_rate_rub'))return false;
 const stamp=r.created_at.replace(/Z$/,'+00:00');if(!/^\\d{4}-\\d\\d-\\d\\dT\\d\\d:\\d\\d:\\d\\d(?:\\.\\d{6})?\\+00:00$/.test(stamp))return false;
 return await normHash({norm_id:r.norm_id,created_at:stamp,tenant_id:requireCompany().tenant_id,member_id:r.member_id,norm_key:r.norm_key,revision:r.revision,action:r.action,idempotency_key:p.idempotency_key,inputs:p,result:x})===r.record_sha256
}
function normTable(rows){return actualTable(['Работа','Категория','Единица','Количество','Ставка, ₽','Версия','Решение','Обоснование','Источники','Участник','Дата'],rows.map(r=>[r.result.title,r.result.category,r.result.unit,r.result.norm_quantity??'—',r.result.norm_rate_rub??'—',String(r.revision),r.action==='APPROVED'?'Утверждён':'Отозван',r.result.rationale,(r.result.sample_observation?.samples??[]).map(s=>s.source_platform+':'+s.external_id+' · v'+s.snapshot_revision).join('; ')||'—',r.member_id,r.created_at]))}
async function checkNormPage(r,key=null){if(!r||r.customer_id!==requireCompany().customer_id||typeof r.has_more!=='boolean'||!Array.isArray(r.items)||r.items.length>10||(key!==null&&r.norm_key!==key))normIntegrity();for(const x of r.items){let valid=false;try{valid=await validNormRecord(x)}catch(_){}if(!valid||(key!==null&&x.norm_key!==key))normIntegrity()}if(key===null&&new Set(r.items.map(x=>x.norm_key)).size!==r.items.length)normIntegrity();if(key!==null&&r.items.some((x,i)=>i>0&&x.revision!==r.items[i-1].revision-1))normIntegrity()}

async function loadNormCatalog(offset=0){if(!companyCanWrite())throw Error('Недоступно');const prior=selectedNorm()?.norm_key;normCatalog=[];normHistory=null;normMore=false;el('cost-norm-catalog').replaceChildren();el('cost-norm-history-result').replaceChildren();blankSelect('cost-norm-select','Выберите норматив');el('cost-norm-withdraw-confirm').checked=false;el('cost-norm-withdraw-note').value='';let r;try{r=await call(normPath+'?offset='+offset+'&limit=10')}catch(e){el('cost-norm-status').textContent=e.status===404?'Функция нормативов отключена.':'Каталог не получен.';throw e}await checkNormPage(r);normCatalog=r.items;normOffset=offset;normMore=r.has_more;for(const x of normCatalog){const o=document.createElement('option');o.value=x.norm_key;o.textContent=x.result.title+' · '+x.result.unit+' · v'+x.revision;el('cost-norm-select').append(o)}if(normCatalog.some(x=>x.norm_key===prior))el('cost-norm-select').value=prior;el('cost-norm-catalog').replaceChildren(normTable(normCatalog));el('cost-norm-status').textContent='Каталог: '+normCatalog.length+' записей на странице.';return {count:normCatalog.length}}
async function loadNormHistory(offset=0){const item=selectedNorm();if(!companyCanWrite()||!item)throw Error('Выберите норматив');normHistory=null;el('cost-norm-history-result').replaceChildren();const r=await call(normPath+'/'+item.norm_key+'?offset='+offset+'&limit=10');await checkNormPage(r,item.norm_key);if(offset===0&&r.items[0]?.record_sha256!==item.record_sha256){el('cost-norm-withdraw-confirm').checked=false;throw Error('Каталог устарел, обновите его.')}normHistory={key:item.norm_key,offset,more:r.has_more};el('cost-norm-history-result').replaceChildren(normTable(r.items));return {versions:r.items.length}}
function normAttempt(path,body){const signature=canonicalCostJSON([path,body]);if(normPending?.signature!==signature){if(!globalThis.crypto?.randomUUID)throw Error('Требуется защищённый HTTPS');normPending={signature,key:crypto.randomUUID()}}return {...body,idempotency_key:normPending.key}}
async function normWrite(path,body,check){const payload=normAttempt(path,body);let r;try{r=await call(path,{method:'POST',body:payload})}catch(e){if(e.status===409){invalidateNormDraft();normPending=null;el('cost-norm-status').textContent='Версия или источники изменились. Обновите данные.'}throw e}let valid=false;try{valid=await validNormRecord(r)&&r.member_id===requireCompany().member_id&&samePriceValue(r.inputs,payload)&&check(r)}catch(_){}if(!valid)normIntegrity();normPending=null;return r}
bind('cost-norm-load',()=>loadNormCatalog());bind('cost-norm-prev',()=>loadNormCatalog(Math.max(0,normOffset-10)));bind('cost-norm-next',()=>loadNormCatalog(normOffset+10));
bind('cost-norm-history',()=>loadNormHistory());bind('cost-norm-history-prev',()=>loadNormHistory(Math.max(0,(normHistory?.offset??0)-10)));bind('cost-norm-history-next',()=>loadNormHistory((normHistory?.offset??0)+10));
for(const id of ['quantity','rate','note','limits'])for(const event of ['input','change'])el('cost-norm-'+id).addEventListener(event,()=>{invalidateNormDraft();syncNormControls()});
el('cost-norm-select').addEventListener('change',()=>{normHistory=null;el('cost-norm-history-result').replaceChildren();el('cost-norm-withdraw-confirm').checked=false;el('cost-norm-withdraw-note').value='';syncNormControls()});
for(const id of ['approve-confirm','withdraw-confirm','withdraw-note'])for(const event of ['input','change'])el('cost-norm-'+id).addEventListener(event,syncNormControls);
bind('cost-norm-preview',async()=>{const p=normProposal(),rows=actualSamples.slice();invalidateNormDraft();const r=await call(normPath+'/preview',{method:'POST',body:p});let valid=false;try{valid=await validNormDraft(r,p,rows)}catch(_){}if(!valid)normIntegrity();normDraft=r;const h=document.createElement('p');h.textContent='Проект: '+p.sample.title+' · '+p.norm_quantity+' '+p.sample.unit+' × '+p.norm_rate_rub+' ₽. Следующая версия: '+(r.expected_revision+1)+'. Не утверждён.';el('cost-norm-preview-result').replaceChildren(h);return {preview_sha256:r.preview_sha256,approved_norm:false}});
bind('cost-norm-approve',async()=>{const d=normDraft;if(!companyCanDecide()||!d||!el('cost-norm-approve-confirm').checked||!samePriceValue(normProposal(),d.proposal))throw Error('Проверьте проект и подтвердите утверждение');el('cost-norm-approve-confirm').checked=false;const r=await normWrite(normPath,{proposal:d.proposal,preview_sha256:d.preview_sha256,expected_revision:d.expected_revision,confirm_internal_approval:true},r=>r.action==='APPROVED'&&r.norm_key===d.norm_key&&samePriceValue(r.result.sample_observation,d.sample_observation));invalidateNormDraft();await loadNormCatalog();el('cost-norm-status').textContent='Утверждена версия '+r.revision+'. Не применяется автоматически.';return {norm_id:r.norm_id,revision:r.revision}});
bind('cost-norm-withdraw',async()=>{const item=selectedNorm(),rationale=val('cost-norm-withdraw-note');if(!companyCanDecide()||item?.action!=='APPROVED'||!el('cost-norm-withdraw-confirm').checked||rationale.length<10||rationale.length>2000)throw Error('Подтвердите отзыв и укажите причину');el('cost-norm-withdraw-confirm').checked=false;const r=await normWrite(normPath+'/'+item.norm_key+'/withdraw',{expected_revision:item.revision,rationale,confirm_withdrawal:true},r=>r.action==='WITHDRAWN'&&r.norm_key===item.norm_key&&r.result.withdrawn_norm_id===item.norm_id&&r.result.withdrawn_record_sha256===item.record_sha256);invalidateNormDraft();await loadNormCatalog(normOffset);el('cost-norm-status').textContent='Норматив отозван; история сохранена.';return {norm_id:r.norm_id,revision:r.revision}});

async function loadCompanyCase(id){
 requireCompany();resetCompanyDetail();
 if(!companyItems.some(x=>x.case_id===id))throw Error("Выберите карточку из своего портфеля");
 const path="/api/saas/company-portfolio/cases/"+encodeURIComponent(id);
 const item=await call(path);if(item.case_id!==id)throw Error("Ответ не соответствует карточке");
 const history=await call(path+"/decisions?limit=50");
 companyCase=item;companyItems=companyItems.map(x=>x.case_id===id?item:x);renderCompanyItems();
 el("company-case-state").textContent=requireCompany().company_name+" · "+companyCaseText(item)+" · только внутреннее решение";
 el("company-case-url").textContent=item.source_kind==="commercial_reference"?"Сохранённая ссылка: "+(item.source_url||"недоступна")+" · оригиналы требуют отдельной проверки":"";
 el("company-history").textContent=history.items.map(x=>"v"+x.revision+" · "+x.action+" · "+x.decided_at+"\\n"+x.rationale).join("\\n\\n")+(history.has_more?"\\nПервые 50 решений":"")||"История пуста";
 el("company-detail").hidden=false;
 if(companyCanWrite()&&item.source_kind!=="commercial_reference")await loadCompanyEvidence(path);
 if(companyCanWrite()&&item.source_kind==="commercial_reference"&&item.source_url)await loadCommercialCaptures();
 return {case_id:item.case_id,revision:item.revision};
}
bind("company-load",()=>loadCompanyPage());
bind("company-more",()=>companyInboxView?loadCompanyInbox({restart:false}):loadCompanyPage({restart:false}));
bind("company-inbox-load",()=>loadCompanyInbox());
el("company-case").addEventListener("change",()=>{resetCompanyDetail();syncCompanyControls()});
el("company-evidence").addEventListener("change",()=>{el("company-evidence-result").hidden=true;el("company-evidence-result").textContent="";syncCompanyControls()});
bind("company-open",()=>loadCompanyCase(val("company-case")));
bind("company-save",async()=>{
 if(!companyCanWrite())throw Error("Недостаточно прав");
 const number=val("company-registry");if(!/^[0-9]{19,20}$/.test(number))throw Error("Введите 19 или 20 цифр номера ЕИС");
 const saved=await call("/api/saas/company-portfolio/cases",{method:"POST",body:{registry_number:number}});
 el("company-registry").value="";await loadCompanyPage();return {saved_case: saved.case_id};
});
bind("company-commercial-save",async()=>{
 if(!companyCanWrite())throw Error("Недостаточно прав");
 const saved=await call("/api/saas/company-portfolio/commercial-cases",{method:"POST",body:{source_url:val("company-commercial-url")}});
 el("company-commercial-url").value="";await loadCompanyPage();return {saved_case:saved.case_id};
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
 clearMetrics();
 let saved;
 try{saved=await call(path+"/decisions",{method:"POST",body:{...body,idempotency_key:pendingCompanyDecision.key}})}
 catch(error){
   if(error.status===409){resetCompanyDetail();throw Error("Решение изменилось или конфликтует. Откройте карточку заново и подтвердите новое решение.")}
   // An uncertain network result keeps the same key for an explicit identical retry.
   el("company-confirm").checked=false;throw error;
 }
 pendingCompanyDecision=null;el("company-confirm").checked=false;
 // Never silently overwrite a more recent revision or present a successful refresh on failure.
 try{if(companyInboxView){el("company-inbox-filter").value=companyInboxView;await loadCompanyInbox()}else await loadCompanyCase(id)}catch(error){
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
 discoveryRun=null;discoveryProfile=null;discoveryEnabled=false;companySchedule=null;el("company-schedule-state").textContent="Загрузите расписание.";el("company-schedule-hour").value="8";el("company-schedule-confirm").checked=false;blankSelect("company-search-index","Не подключать");el("company-search-eis").checked=true;
 el("company-search-state").textContent="Загрузите портфель и состояние поиска.";
 el("company-search-receipts").textContent="";blankSelect("company-search-candidate","Выберите кандидата");
}
function syncCompanySearchControls(){
 const owner=companyCanDecide(), read=Boolean(companyIdentity?.legal_accepted);
 el("company-search-refresh").disabled=uiBusy||!read;
 el("company-search-start").disabled=uiBusy||!owner||!discoveryEnabled||discoveryProfile?.profile_state!=="ACTIVE";
 el("company-search-run").disabled=uiBusy||!owner||!discoveryEnabled||!discoveryRun||!["PENDING","IN_PROGRESS"].includes(discoveryRun.status)||discoveryRun.plan.profile_version!==discoveryProfile?.profile_version;
 el("company-search-accept").disabled=uiBusy||!companyCanWrite()||!discoveryRun||!el("company-search-candidate").value;
 const scheduleOwner=read&&companyIdentity.role==="owner";
 el("company-schedule-refresh").disabled=uiBusy||!read;
 el("company-schedule-enable").disabled=uiBusy||!scheduleOwner||!companySchedule?.execution_enabled||discoveryProfile?.profile_state!=="ACTIVE";
 el("company-schedule-disable").disabled=uiBusy||!scheduleOwner||!companySchedule?.enabled;
}
function acceptDiscoveryReply(result){
 if(result&&result.customer_id!==requireCompany().customer_id){clearSession();throw Error("Ответ поиска относится к другой компании")}
 discoveryRun=result;blankSelect("company-search-candidate","Выберите кандидата");
 if(!result){el("company-search-state").textContent=discoveryEnabled?"Поиск пока не подготовлен":"Поиск выключен";el("company-search-receipts").textContent="";return}
 const state={PENDING:"Ожидает выполнения",IN_PROGRESS:"Выполняется",COMPLETED:"Выполнен заданный поиск",PARTIAL:"Выдача неполная",STALE_PROFILE:"Профиль изменился",EXPIRED_WINDOW:"Окно поиска истекло"}[result.status]||"Статус требует проверки";
 el("company-search-state").textContent=state+" · "+result.completed_steps+"/"+result.plan.steps.length+" · профиль v"+result.plan.profile_version+" · "+result.run_day+(result.discovery_incomplete?" · полнота не подтверждена":"")+(discoveryEnabled?"":" · новые запросы отключены");
 el("company-search-receipts").textContent=result.step_receipts.map(x=>x.query+" · "+(x.region||"все регионы")+" · "+x.outcome+" · кандидатов "+x.candidates.length+(x.coverage_complete?"":" · неполное покрытие")).join("\\n");
 for(const item of result.candidates){const option=document.createElement("option");option.value=item.registry_number||item.source_platform+":"+item.external_id;option.textContent=option.value+" · "+item.title;el("company-search-candidate").append(option)}
}
bind("company-search-refresh",async()=>{
 requireCompany();resetCompanySearch();const current=await call("/api/saas/company-portfolio/discovery/latest");
 discoveryEnabled=current.enabled===true;
 for(const index of current.commercial_indexes||[]){const opt=document.createElement("option");opt.value=index;opt.textContent=index;el("company-search-index").append(opt)}
 const profile=await call("/api/saas/company-portfolio/search-context");
 if(profile.customer_id!==requireCompany().customer_id){clearSession();throw Error("Ответ профиля относится к другой компании")}
 discoveryProfile=profile;acceptDiscoveryReply(current.run);return {enabled:discoveryEnabled,status:discoveryRun?.status||"NOT_STARTED",profile_version:profile.profile_version};
});
function showCompanySchedule(result){
 if(result.customer_id!==requireCompany().customer_id){clearSession();throw Error("Расписание другой компании")}
 companySchedule=result;el("company-schedule-hour").value=String(result.hour_moscow);el("company-schedule-confirm").checked=false;
 el("company-schedule-state").textContent=(result.enabled?"Разрешено владельцем":"Отключено")+" · "+(result.execution_enabled?"Серверный запуск разрешён":"Серверный запуск выключен")+" · "+result.hour_moscow+":00 МСК"+(result.enabled&&!result.profile_current?" · профиль изменился, требуется подтверждение":"")+(result.enabled?" · источники: "+[...(result.sources.include_eis?["ЕИС"]:[]),...(result.sources.commercial_indexes||[])].join(", "):"");
}
bind("company-schedule-refresh",async()=>{
 requireCompany();const result=await call("/api/saas/company-portfolio/discovery/schedule");showCompanySchedule(result);return result;
});
bind("company-schedule-enable",async()=>{
 if(companyIdentity?.role!=="owner"||!companySchedule?.execution_enabled||discoveryProfile?.profile_state!=="ACTIVE"||!el("company-schedule-confirm").checked)throw Error("Нужно подтверждение владельца и актуальный профиль");
 const raw=val("company-schedule-hour"),hour=Number(raw),index=val("company-search-index");
 if(!raw||!Number.isInteger(hour)||hour<0||hour>23)throw Error("Введите час 0–23");
 const body={enabled:true,expected_revision:companySchedule.revision,expected_profile_version:discoveryProfile.profile_version,hour_moscow:hour,include_eis:el("company-search-eis").checked,commercial_indexes:index?[index]:[],confirm_unattended_public_search:true};
 el("company-schedule-confirm").checked=false;const result=await call("/api/saas/company-portfolio/discovery/schedule",{method:"PUT",body});showCompanySchedule(result);return result;
});
bind("company-schedule-disable",async()=>{
 if(companyIdentity?.role!=="owner"||!companySchedule?.enabled)throw Error("Недостаточно прав");
 const result=await call("/api/saas/company-portfolio/discovery/schedule",{method:"PUT",body:{enabled:false,expected_revision:companySchedule.revision}});showCompanySchedule(result);return result;
});
bind("company-search-start",async()=>{
 if(!companyCanDecide()||!discoveryEnabled||discoveryProfile?.profile_state!=="ACTIVE")throw Error("Поиск недоступен");
 const body={expected_profile_version:discoveryProfile.profile_version};
 const index=val("company-search-index");if(index)body.commercial_indexes=[index];if(!el("company-search-eis").checked)body.include_eis=false;
 const result=await call("/api/saas/company-portfolio/discovery/runs",{method:"POST",body});
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
 const candidate=discoveryRun?.candidates.find(x=>(x.registry_number||x.source_platform+":"+x.external_id)===number);
 if(!companyCanWrite()||!candidate)throw Error("Выберите кандидата из своего поиска");
 const saved=candidate.registry_number?await call("/api/saas/company-portfolio/cases",{method:"POST",body:{registry_number:candidate.registry_number}}):await call("/api/saas/company-portfolio/commercial-cases",{method:"POST",body:{source_url:candidate.source_url}});
 // Preserve the selected completed discovery while refreshing the same company's portfolio.
 const snapshot={run:discoveryRun,profile:discoveryProfile,enabled:discoveryEnabled,customer:requireCompany().customer_id};
 await loadCompanyPage();
 if(companyIdentity?.customer_id===snapshot.customer){discoveryEnabled=snapshot.enabled;discoveryProfile=snapshot.profile;acceptDiscoveryReply(snapshot.run)}
 return {saved_case:saved.case_id,source_verified:false};
});

syncCompanyControls();
</script></body></html>"""
