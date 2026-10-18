# Tender Agent — официальный EIS getDocsIP ZIP/XML в едином learning corpus

**ООО «Арвектум», 18.10.2026.** Сохранение через уже существующий официальный SOAP getDocsIP и валидатор архивных оригиналов ЕИС, без новой БД/токена/транспорта/внешней модели.

## Что реально сделано

1. Точный allowlist 3 ранее выявленных номеров: Смоленская областная Дума 0163200000326005243 (EOK2020), НГТУ «ЮНИВУЗ-3» 0332100025426000039 (EZK2020), ГИС Московской области 0148200002426000013 (EF2020). Они ранее представлены 3 metadata-only events из 31 старого импорта. Новая запись — фактически заново скачанная и SHA-проверенная ZIP-версия, НЕ три новые квалифицированные закупки.
2. Новый scripts/procurement_llm/collect_eis_official_archives.py использует ZakupkiSoapClient.get_docs_by_reestr_number. Официальная архивная ссылка использует https://int.zakupki.gov.ru/dstore/common/download/compound с двумя служебными UUID параметрами docRequestUid и compoundUid; только этот точный template разрешён, query значения **не записываются и не публикуются**. Настроенный прямой RU маршрут обязателен.
3. Только ZIP до 8 MB; существующий classify_official_eis_archive проверяет commonInfo.purchaseNumber, XML epNotification тип/имя/версию и SHA исходного XML/ZIP. Повреждённый, конфликтующий, неверный номер или UNKNOWN архив не поступает в корпус.
4. Dry-run **3/3** оригиналов 82367 байт, никаких изменений БД/SSD.
5. Перед записью выполнен полный PostgreSQL pg_dump -Fc на ArvectumSSD: /Volumes/ArvectumSSD/Arvectum/private/tender-agent/backups/arvectum-before-official-eis-3-20261018-2155.dump; режим 0600, размер 2108685, SHA256 045a382f79cf0d156e92527998764043b0ef8339f3216ef65f01c34c35000add; pg_restore --list подтверждает таблицу и её данные, живого restore не было. Прежнее количество наблюдений — 110.
6. Owner-authorized --apply --confirm-database arvectum сохранил **3 приватных ZIP оригинала** под ArvectumSSD/private/tender-agent/original-snapshots/eis/{номер}/{sha}.zip (режим 0600) и **3 новые owner-internal candidate_unreviewed** метаданных observation в той же PostgreSQL (только SHA ZIP/XML, выбранная архивная версия, тип и private original path). Raw ZIP/XML, URL query и EIS токены не скопированы в SQL. SQL **110 → 113** наблюдений, 3 source_ref manual:ta-eis-zip.
7. Frozen source replay из ровно тех же ZIP: **0 inserted, 3 existing, 0 new archives**. Изменившийся timestamp не переписывает старое событие; новая source byte версия append-only.
8. Тестовый suite checks competitive and special notice formats, wrong XML ID, invalid ZIP, immutable replay, private file permissions, batch failure before write, SQL rollback on error, absence of legal GO.

## Не доказано и остаётся открытым

SHA-верифицированный архив ЕИС **не доказывает** текущий статус закупки, последнюю действующую редакцию, ЭТП допуск, квалификацию участника, полноту ТЗ, подписи XML/ZIP или человеческую gold-разметку. Нет новой процедуры подачи или проверки актуального решения buyer. Collector является разрешённым CLI по заданным номерам, а не непрерывной системой поиска всех новых ЕИС закупок. Code review and AM-4 merge/deploy pending. После фактической приёмки остаётся сравнение реальных независимых run ChatGPT и Tender Agent по идентичному source manifest с human adjudication до дообучения.

Никаких ETP заявок, платежей, подписей, писем заказчикам, второй DB, продакшен-deploy нового кода или обучения весов не выполнялось.
