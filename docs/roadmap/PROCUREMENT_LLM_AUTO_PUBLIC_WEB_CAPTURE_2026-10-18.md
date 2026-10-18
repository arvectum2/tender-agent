# Procurement LLM — автоматический захват веб-источников Tender Agent

**18.10.2026. ООО «Арвектум».** Этап TA-WEB-SOURCE-LEARNING-CAPTURE-20261018 следует за фактическим авторизованным импортом 31 наблюдения в существующую PostgreSQL arvectum (77 → 108 записей), без второй БД.

## Реально реализовано в review-ветке

В TenderResearchPipeline.fetch_search_results после штатного upsert_web_page вызывается make_fetched_web_source_candidate и append_candidate, **в той же транзакции** сохранения страницы. Новый candidate создаётся только для публичной HTTPS-страницы с status=fetched, HTTP200, MIME text/html, совпадающим hostname начальной/конечной страницы и непустым decoded HTML не более 4 MiB. На этом этапе pipeline не производит дополнительных внешних запросов.

Идентичность source candidate — procurement_ref, SHA256 URL и SHA256 decoded HTML. Точный повтор idempotent, обновлённое содержимое даёт append-only версию. SHA относится только к **декодированному HTML, выданному fetcher**, а не к оригинальным сырым HTTP-байтам сайта; это не доказательство актуальной правовой редакции ЕИС.

В PostgreSQL через уже существующие make_manual_candidate/append_candidate сохраняются только источник-хост, хеш URL, хеш decoded HTML, размер, статус и явные ограничители: PUBLIC_FETCH_ONLY_NOT_OFFICIAL_PROVENANCE, owner_bid_go=false, human_verified_interpretation=false, training_labels=NOT_REVIEWED. Полные URL с query, HTML, body text, cookie, учетные записи, содержимое пользовательских чатов или private customer поля в learning candidate не попадают.

## Fail-closed

Неподходящие источники (HTTP, IP/localhost/private/internal host, нестандартный порт, credentials/query/fragment, redirect в другую host-зону), не HTML, пустой или превышающий limit ответ, ошибочные или заблокированные запросы не превращаются в обучающие source candidates. Их штатная запись ошибок в основной web corpus остаётся. Если вставка обязательной candidate после годного источника не удаётся, SQL-транзакция откатывает **и webpage, и observation**: тихого потери доказательства при работающей базе нет.

Тесты: **26 focused PASS** по приватности источника, версии, повтору, failed fetch, выключенному capture, ошибке БД и rollback; **712 related PASS, 2 SKIP** по Tender Research/Procurement Learning/Customer Pilot; Ruff для новых модулей и тестов PASS.

## Открытые задачи

- [x] Подключить уже существующий pipeline для публичных успешно скачанных веб-страниц к существующей канонической таблице кандидатов с атомарным сохранением.
- [x] Проверить unreviewed/no-gold, отсутствующее сырьё/секреты в learning payload, strict failure и replay.
- [ ] Согласовать merge/deploy всех зависимых PR и проверить на настоящем запущенном сервисе. Эта ветка **не задеплоена**.
- [ ] Добавить единый provider collector для Workspace, B2B-Center, EIS SOAP originals и внешних ChatGPT исследований, а также захват корректных обработанных PDF/DOCX. Сейчас нельзя говорить, что **все будущие внешние исследования ChatGPT** автоматически записываются.
- [ ] После фактической технической приёмки провести два реальных независимых разбора по одинаковой версии источников, сравнить, human adjudicate и лишь потом обсуждать обучающие этикетки.

**Никаких повторных production DB импортов, изменения Operator Workspace, отправки заявок, сообщений, платежей, подписей или автоматического обучения моделей не выполнялось.**
