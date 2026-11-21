# Tender Agent → Procurement LLM: состояние и мост для результатов поисков

18 октября 2026, ООО «Арвектум», Mac mini. Анализ выполнен без production DB mutation, обучения модели и создания второй БД.

## Что действительно было

Последние внешние поиски Workspace и B2B-Center выполнялись самостоятельными read-only скриптами, **не через единый штатный Tender Agent ingest pipeline**. Для 44-ФЗ использовался существующий ZakupkiSoapClient Tender Agent, но новые документы и сводки сохранялись как Git-артефакты отдельных исследовательских PR, **без автоматической записи этих поисков в общую таблицу обучающих наблюдений**.

Канон уже существует: PostgreSQL 17 Docker 'arvectum-postgres' / database 'arvectum' / таблица 'procurement_learning_observations', Alembic 107, существующий guarded importer 'scripts/procurement_llm/import_candidates.py', существующий ArvectumSSD data/tenders оригиналов. Для некоторых штатных сохранённых аналитических прогонов уже реализован транзакционный capture при включённой штатной конфигурации. Это не распространяется автоматически на внешние ручные web research скрипты.

**Read-only прямая проверка PostgreSQL 18.10.2026:** 77 записей (20 development_e2e, 45 analysis_run, 10 manual_review, 2 legacy_report_artifact). Среди них source_ref LIKE 'manual:ta-research:%' — **0**.

## Реально подготовленный новый мост

Добавлен 'scripts/procurement_llm/build_research_intake.py' — **offline** адаптер из уже ранее аттестованных исходных research receipts в уже существующий формат 'manual-candidate-import-v1'. Он не обращается к поисковым площадкам, не создаёт новую БД и не добавляет записи в live PostgreSQL.

| Исходные уже выполненные поиски | Подготовленные наблюдения |
|---|---:|
| Workspace — 21 первичная карточка от PR #483 (включая закрытые/частные; не объявляются годными к участию) | 21 |
| ЕИС/44-ФЗ — 3 архивных номера с оригинальными ZIP/XML SHA из PR #484 (Смоленск уже известен ранее) | 3 |
| B2B-Center — 1 оригинальная карточка #4643484 + 6 других из PR #487 | 7 |
| **Итого SHA-связанных исследовательских наблюдений** | **31** |

На Mac mini создан owner-only PRIVATE staging-файл с разрешениями 0600:
'/Volumes/ArvectumSSD/Arvectum/private/tender-agent/pending-manual-evidence/research-firstparty-snapshots-20261018.json'.

Далее запущен **только dry-run существующего импортёра**:
- mode: dry_run
- candidates: **31**
- unique_ids: **31**
- Записей в production PostgreSQL после dry-run всё ещё **77**, новых 'ta-research' = **0**.

Каждый candidate получает устойчивый event_id по площадке + реестровому номеру + SHA оригинала + SHA отчёта-наблюдения, точный source/provenance link, UTC-дата, тип источника, source gate, отсутствие подтверждённой пригодности. Повтор того же receipt idempotent; новая версия append-only без переписывания старого. Это **только метаданные**, без копирования оригинальных документов, открытых текстов моделей, чатов, секретов, писем, приватных файлов, tenant-records или защищённых blind/holdout.

Все записи в существующем валидаторе имеют training_status=candidate_unreviewed, candidate_split=manual_candidate_not_blind, visibility_scope=owner_internal, participation=reviewed_only, human_verified_interpretation=false, owner_bid_go=false. Даже исходные SHA оригинальных XML **не означают** правильного правового ответа или готовых данных для LoRA.

## Повторение и будущий GO

1. Публичные EIS/B2B квитанции в дереве могут быть проверены командой 'python -m scripts.procurement_llm.build_research_intake' (по умолчанию сухой прогон 10 кандидатов).
2. Для полного пакета Workspace исходную JSON квитанцию PR #483 подают через '--workspace-receipt /PRIVATE/source.json' и '--write-private' только внутри заранее существующего канонического private intake каталога. Путь вне канона, symlink, отсутствие оригинальных SHA и изменение исходного статуса fail closed.
3. Уже созданный private-файл 31 проверяется без записи командой 'python -m scripts.procurement_llm.import_candidates --manual-file /PRIVATE/research-firstparty-snapshots-20261018.json'. Результат 31/31 подтверждён.
4. Перенос именно в рабочую таблицу — отдельное действие только после явного разрешения записи, штатного '--apply --confirm-database arvectum', Alembic preflight и последующего независимого read-only аудита inserted/existing. Эта команда **не выполнялась**.
5. В будущих этапах необходимо подключить все источники к общему Tender Agent Collector/ingest flow, сохранить документы на ArvectumSSD под content SHA, version, source URL; затем transaction-coupled capture внутри существующей БД. Сейчас реализован мост для исторических подтверждённых receipts, **не автоматизация всех будущих поисков**.
6. Для будущего обучения нужны отдельно human-corrected answers, исходный текст с правами на его обработку, реальные результаты торгов и independent blinded evaluation. Защищённый blind и gold запрещено включать в development train.

**Не путать 31 observation с 31 уникальной новой закупкой, 31 qualified BID_GO, 31 human labels или сохранёнными в рабочей БД записями.** Цель 15–20 действительно квалифицированных актуальных заказов пока открыта. Ни внешней заявки, оплаты, e-sign, DB write, второго UI, деплоя, ни новых весов LLM на этом этапе не было.
