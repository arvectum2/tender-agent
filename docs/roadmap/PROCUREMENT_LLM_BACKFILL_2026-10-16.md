# Arvectum Procurement LLM — backfill на едином PostgreSQL, 16.10.2026

**Фактически выполнено на Mac mini, без обучения модели и без создания долгосрочной второй БД.**

## Хранилище и проверенная миграция

- Канон: Docker PostgreSQL 17 `arvectum-postgres` / БД `arvectum`, существующие реальные документы в `/Volumes/ArvectumSSD/Arvectum/data/tenders/`.
- Read-only baseline перед работой: 20 `procurement_tenders`, 95 `procurement_tender_documents`, 45 `tender_analysis_runs`, 55 `tender_bid_result_offers`, Alembic на версии `100_add_daily_tender_runs`.
- До любых изменений сделан и проверен `pg_dump -Fc` по пути `/Volumes/ArvectumSSD/Arvectum/private/tender-agent/pg-backups/arvectum-before-learning-107-20261016.dump`; SHA-256: `730e33bdfcc9eb042b7ccf2b53318c4cfb2000aad45c27df34eb44b836c68593`. Файл строго локальный; не добавлять в Git.
- Восстановлена временная изолированная БД `arvectum_learning_acceptance_20261016`, только для тестов, в том же контейнере. Попытка обычного `upgrade head` выявила `DuplicateTable saas_tenants` на ревизии 106: фактические девять таблиц SaaS уже существовали при Alembic 100.
- На копии успешно: миграции 100→105, независимая проверка имён/типов/nullable/PK/unique/index для всех **девяти** существующих SaaS-таблиц относительно ORM, `stamp 106` после PASS, миграция 107, перенос 29+45 в новую таблицу, проверка идемпотентности и сохранения исходных 45 run rows/55 offers.
- На рабочей БД повторён тот же принятый порядок: 100→105, preflight девяти SaaS-таблиц PASS, `stamp 106` как **подтверждение уже существующей физической схемы**, затем штатная Alembic 107. Не выполнялось повторное создание SaaS-таблиц, сброс или удаление объектов.
- Создана только **одна таблица внутри имеющейся `arvectum`**: `procurement_learning_observations`; никакого самостоятельного PostgreSQL/SQLite-хранилища для обучения.

## Проверенный backfill

`scripts/procurement_llm/import_candidates.py` запускается в режиме dry-run по умолчанию, `--apply --confirm-database arvectum` — только с известной PostgreSQL-конфигурацией и уже установленной Alembic 107.

| Источник | Проверено | В рабочей БД после первого импорта |
| --- | ---: | ---: |
| `development_e2e`, historic 44-ФЗ Gemma4 | 20 | 20 |
| `manual_review`, восстановленные по старым обсуждениям | 9 | 9 |
| `analysis_run`, имеющиеся `tender_analysis_runs` | 45 | 45 |
| **Итого** | **74** | **74** |

Повторный импорт frozen SQLite: **29 existing / 0 inserted**. Подлинные исходники, 55 ставок по Аксаю, 45 run IDs не переписывались. Эталон независимого оценщика не создавался; `training_status = candidate_unreviewed` для всех 74. Приватная прежняя SQLite `/Volumes/ArvectumSSD/Arvectum/private/procurement-llm/corpus-v1/candidate-registry.sqlite3` пока сохранена как резервный объект сверки (не каноническое хранилище, запись в неё прекращена).

## Путь новых наблюдений

- Новый **ручной** глубокий разбор: создать в PRIVATE-каталоге JSON с уникальным `event_id`, `procurement_ref`, `participation`, `review_state`, `source_links`, `participation_evidence` при `submitted`, затем запустить `python -m scripts.procurement_llm.import_candidates --manual-file /private/path/review.json --apply --confirm-database arvectum`. Запуск без `--apply` лишь проверяет форму, в БД не пишет.
- Старые и вновь сохранённые анализы: `python -m scripts.procurement_llm.import_candidates --backfill-existing-runs --apply --confirm-database arvectum`, повторные события по уже известным `run.id` не дублируются.
- **Анализ через `src.tender_research.rag.history_service.record_analysis_run`**: transaction-coupled запись источника в `procurement_learning_observations`, при установленной схеме 107 и `TENDER_LEARNING_CAPTURE_ENABLED=1`. Включать только при развернутом коде; при ошибке capture транзакция анализа не коммитится. Ручные обсуждения в ChatGPT, другие runtime-пайплайны и внешние разговоры автоматически не захватываются, пока не подключён явный ingestion инструмент; это **отдельная открытая задача**.
- Код не отправляет данные модели, не экспортирует train JSONL и не выполняет LoRA/QLoRA. `customer_id`/scope привязывают tenant events, owner-internal метаданные не имеют публичного API. Контур owner внутренний, без автоматической передачи содержимого между клиентами.
- Защита: blind/holdout отвергается, `legal_gold`/signed gold отвергаются, пробелы в источниках не превращаются в подтверждённые факты. Подготовленные записи на текущем этапе **не train-ready**.

## Команды контрольной проверки

```bash
python -m scripts.procurement_llm.import_candidates --legacy-sqlite /PRIVATE/path/candidate-registry.sqlite3
python -m scripts.procurement_llm.import_candidates --backfill-existing-runs
python -m scripts.procurement_llm.verify_saas_existing
# Перед запуском с --apply: проверить фактический AI_CORP_DATABASE_URL (имя БД должно быть arvectum)
# Только после сверки схемы и подтверждения права записи:
python -m scripts.procurement_llm.import_candidates --manual-file /PRIVATE/path/review.json --apply --confirm-database arvectum
```

**Не удалять бэкап PostgreSQL и старую SQLite до окончания всех проверок.** Временная тестовая БД подлежит удалению по завершении acceptance, чтобы не было дополнительного постоянного хранилища.
