# Tender Agent — повторяемый collector оригиналов Workspace и B2B-Center

**ООО «Арвектум», 18.10.2026**. Новый код в отдельной review-ветке, работающий backend не развёртывали. Этап обеспечивает сохранение публичных первоисточников с оригинальным SHA в существующую PostgreSQL arvectum, без второй БД и без правовых или обучающих gold-выводов.

## Исполненные этапы

1. Вход — точный allowlist двух исходных URL: Workspace 19043, создание/редизайн сайта digital-агентства, и B2B-Center 4632891, X5 Import CRM RFI. Оба уже известны ранее, ни один не является вновь квалифицированной возможностью для подачи ООО.
2. Новый scripts/procurement_llm/collect_public_market_originals.py строго проверяет площадку+номер+URL, HTTP200 без redirect, HTML MIME, размер не более 900 KB, Workspace rel=canonical и og:url либо точное название с номером Тендер №... в B2B-Center. Загрузка только публичного оригинала, не кабинета, не платных материалов или скрытого ТЗ.
3. Dry-run 2/2 реальных источника HTTP200, 350490 байт, ноль изменений SQL/SSD.
4. Перед применением создан **полный** custom-format pg_dump той же PostgreSQL со всеми данными: /Volumes/ArvectumSSD/Arvectum/private/tender-agent/backups/arvectum-before-public-original-pilot-20261018-2140.dump, 0600, 2107946 байт, SHA256 06ae3a975d081fb749d44693de8dc39f36640add860cea24c59b56765e76d75d. pg_restore --list подтвердил каталог, включая таблицу learning. На действующей БД восстановление не запускалось.
5. После Owner-разрешения на ongoing capture произведён пилот --apply --confirm-database arvectum: 2 новые owner-only HTML исходника на ArvectumSSD /private/tender-agent/original-snapshots/{platform}/{id}/{sha}.html, каталог 0700, файлы 0600. В SQL попали только source metadata, raw HTML SHA, исходный номер, private file path и явный no-go, но НЕ исходный HTML. PostgreSQL: 108 → **110** observations, 2 новых candidate_unreviewed/owner_internal, buyer_deadline_current_verified=false, company_bid_eligibility_verified=false, owner_bid_go=false.
6. Первоначальный повтор обнаружил коллизию неизменяемого event-id с новым временем observation. Fail-closed остановил повтор. Исправлено без изменения старых записей: для одного original URL+одного raw HTML SHA сохраняется самая ранняя исходная отметка времени, а новая версия raw HTML создаёт append-only observation. Точный повтор из двух frozen оригинальных файлов показал 0 inserted / 2 existing / 0 новых snapshots. Повторная SQL-сверка остаётся 110.
7. Вся запись ограничена existing canonical procurement_learning_observations, без второго репозитория данных, API, платного запроса, письма, УКЭП, юридического GO и обучения.

## Проверки и ограничения

21 targeted/offline adversarial test PASS: URL/номер первоисточника, canonical/og/url, redirect/no-go, хранение 0600, source SHA, повтор с другим observed time, append-only изменённой версии, rollback SQL/snapshot на сбое. Более широкий regression suite Tender Research и Procurement Learning проверяется отдельно.

Это захват оригинальных HTML страниц B2B и Workspace по явно заданному allowlist. НЕ полный continuous crawler, не оригиналы ЕИС SOAP ZIP/XML, не все внешние чаты ChatGPT, не структурированная обучающая пара вопрос/ответ. После фактической технической приёмки для Procurement LLM ещё нужны два независимых реальных аналитических run с идентичным frozen source manifest, comparison и human adjudication. KPI 15–20 реально квалифицированных заявок остаётся открытым.

Следующий этап: единый provider registry для ЕИС SOAP и расширенного Workspace/B2B, источников PDF/DOCX и полный контроль пропусков записи; разрешённый merge/deploy review-кода отдельно. Работающий Operator Workspace и продакшен-приложение не перезапускались.
