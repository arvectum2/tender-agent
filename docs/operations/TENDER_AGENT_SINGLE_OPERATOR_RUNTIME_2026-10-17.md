# Один интерфейс Tender Agent — фактическое переключение Mac mini 17.10.2026

## Решение владельца и инвентаризация

Owner потребовал **не создавать больше дублирующих Pilot и Operator Workspace**. Выбран ранее существующий операторский HTML/JS/CSS в src/modules/tender_operator_agent_demo/assets/operator_workspace.*; никакой новый frontend, БД или постоянный стенд не создавался.

Проверенный ДО переключения факт:
- 127.0.0.1:18082, Compose project arvectum-local-e2e, api image c6c5fe9f: /pilot/tender-agent отдавал старый 76510-byte Pilot Wizard, /pilot/tender-agent/workspace возвращал 404.
- 127.0.0.1:18083, отдельный контейнер arvectum-apr03b-preview-api, image a9f3bce9: /pilot/tender-agent и /pilot/tender-agent/workspace отдавали другую, единую Operator Workspace HTML. Впоследствии эти два образа стали причиной путаницы.
- Оба использовали существующий Compose и тома; старые контейнеры и реальные данные нельзя было удалять без проверки.

## Результат

- PR #461 merged to main SHA **66f7521f6ea572f634954be350cbd6c11c540f9b** с зелёными exact-head CI. Прогон Mac mini: **4936 pytest PASS / 285 SKIP / 0 FAIL**; 36 targeted PASS / 10 SKIP; make check/Ruff PASS. Официальные дела/ETP не изменялись.
- Для существующего Mac mini Compose API **arvectum-local-e2e-api-1** на **127.0.0.1:18082** выполнено in-place source update, без второй БД, нового project/порта/внешнего ingress. Worker пересоздан с тем же образом.
- Инструмент scripts/ops/verify_operator_workspace_preview.py подтвердил **полное совпадение 1162 файлов src+scripts** и Docker OCI revision **66f7521f6ea572f634954be350cbd6c11c540f9b**.
- **5 прежних Docker mounts сохранены byte-independent stable signature** (Type/Name/Destination/RW): d82ed620689f5ad460f8f2551bb6cc9c9bcbcf4d7765ededf379c45b0e48c3ea. API опубликован только на **127.0.0.1:18082**.
- Перед обновлением PG сохранён приватный backup на ArvectumSSD вне Git (режим 0600), 960845 bytes, SHA256 **ed2d813f2816e357bcaa7b0d893585a6551f1d1a620e9bce02d8d3573c7d81d2**; файл pg_restore manifest проверен (2168 записей). Существующая БД PG16 обновлена **106_add_saas_foundation → 107_add_procurement_learning_observations** (additive Alembic); публичный procurement_tenders count 0 до/после, данные не заменялись фикстурами.
- Существующий HTTP API: GET /health = 200; анонимный GET /pilot/tender-agent, /pilot/tender-agent/workspace, old /demo/tender-agent/wizard и protected asset = 401; авторизованный HTML обеих UI-ссылок byte-identical SHA256 **283b72f879d0b675b7362e79e1ea95bde0c3559bb28c63600f3821a2cd66d110**, статус 200; старый wizard path = 307 redirect на canonical /pilot/tender-agent/workspace; JS/CSS 200; canonical PostgreSQL registry GET 200 read-only (0 procurement_tenders, это НЕ наличие реальных закупок); сохранённая история runs GET 200.
- **Реальный Google Chrome Headless 155** загрузил UI на **18082**: поиск, история и база присутствуют, 1282 видимых текстовых символа, 1 JS asset, **0 uncaught JS exceptions**.
- ТОЛЬКО ПОСЛЕ этих проверок контейнер **arvectum-apr03b-preview-api** на **18083** остановлен (state exited), но **не удалён**, общие тома не удалялись. Порт 18083 больше не слушает, а 18082 остаётся healthy.

## Один адрес и правило продолжения

**Открывать только** http://127.0.0.1:18082/pilot/tender-agent/workspace — с действующей авторизацией и существующим защищённым способом доступа с MacBook. /pilot/tender-agent совместим и возвращает ту же страницу. Demo wizard URL только перенаправляет сюда. SaaS/onboarding имеют отдельные функции, но не альтернативный интерфейс оператора.

Постоянное правило записано в AGENTS.md и docs/architecture/TENDER_AGENT_SINGLE_OPERATOR_UI.md. Новые UI, Pilot Wizard, Operator Workspace клоны, отдельные стенды и БД без решения владельца **не создавать**.

**Не закрыто:** личное подтверждение владельца в браузере на настоящей разрешённой закупке, проверка исходных бинарных ЕИС, корректного анализа/citations и exports с существующей PostgreSQL/файлами; R4 independent human gold 0/15 и R5 owner reviews 0/20, коммерческие/юридические/производственные решения отдельно. Никакого одобрения заявки, подписи, внешних сообщений, платежей, VPS или обучения модели из этого локального переключения не следует.
