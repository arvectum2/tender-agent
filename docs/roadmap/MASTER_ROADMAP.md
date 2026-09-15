# Tender Agent — canonical master roadmap

> Canonical scope/history source for `arvectum2/tender-agent`. The executor queue is only a filtered executable projection and is **not** the complete roadmap.

## Provenance and restoration rule

This roadmap restores the latest canonical Owner backlog snapshot available for recovery: `Arvectum_Backlog_Roadmap_2026-07-30_v9_storage_cleanup.xlsx`, sheet `Полный бэклог`, rows 5–97. The recovered registry is complete for `BASE-001..BASE-018` and `ARV-001..ARV-075` and preserves every historical ID, title, status, priority, dependency, progress value, source and comment without renumbering.

Current repository evidence is recorded as a **reconciliation overlay**. It may confirm, refine or flag a historical item, but it never silently rewrites the 2026-07-30 snapshot. New executable work still requires an explicit entry in `.agent/execution-queue.yaml`; presence here does not grant execution authority.

## Canonical relationship

`master-roadmap.yaml` → complete product scope/history → `.agent/execution-queue.yaml` → admitted executable projection → `.agent/current-task.yaml` → one active checkpoint.

Blocked, REVIEW, OWNER and HUMAN gates remain blocked/gated even when later independent queue work is executable. The roadmap does not expand Company AM-4 authority.

## Owner acceleration directive — 2026-09-14

The Product Owner changes the default development posture from **build-first** to **reuse-first**. Historical ARV IDs/status snapshots below remain immutable history; this directive is a current strategy overlay and does not renumber or silently rewrite them.

**Product thesis:** **Thin Commodity Shell + Deep Decision Core.** Before designing a feature from scratch, first identify who already solved the problem and prefer the shortest lawful path.

| Strategy | Default use | Hard boundary |
|---|---|---|
| `REUSE` | OSS/library/component already solves the commodity problem | Check license, security, maintenance and fit |
| `COPY_PATTERN` | A competitor/public product has a proven UX/workflow/functional pattern | Reimplement behavior; do **not** copy proprietary source, assets, text or private data |
| `ADAPT` | API/protocol/service/standard component can be integrated | Keep vendor boundary replaceable; own only the differentiating layer |
| `INVENT` | Existing options fail or the capability is part of Tender Agent's moat | Requires written gap, differentiation and maintenance-cost justification |

**INVENT gate:** no new custom implementation enters active work until reusable OSS/APIs/public patterns have been checked, the gap is documented, the differentiation maps to Decision Core / Commercial Core / procurement-specific edge cases, and ownership cost is justified. Without that evidence the item defaults to `REUSE`, `COPY_PATTERN` or `ADAPT`.

### Accelerated sequence

| Stage | Priority | Current state | Outcome / evidence |
|---|---|---|---|
| **0. Competitive reverse-spec + reuse registry** | P0 | **done** | PR #56 merged (`8b1c131`): 9 direct products, 10 reuse candidates, active P0/P1 strategy classification and explicit commodity de-scope. |
| **1. Thin commodity shell** | P0 | partial / not separately gated | Baseline shell pre-existed this cycle; Docker-context hardening PR #58 merged (`8924a857`). No standalone Stage 1 completion gate is currently admitted. |
| **2. Decision Core v1** | P0 | **done** | Discovery benchmark/hardening PR #59 merged (`762a392`); Decision Core v1 PR #61 merged (`3bf397f`) with evidence-bound fail-closed decisions. |
| **3. Commercial Core** | P0 | **done** | PR #63 merged (`4257cd2`): price-list ingest, tender-to-catalog matching, coverage/cost/headroom and auditable commercial feasibility with HUMAN control. |
| **4. Automation + integrations** | P1 | **not admitted** | No current execution-queue item authorizes implementation yet. |
| **5. Reliability + moat** | P1 | **not admitted** | No current execution-queue item authorizes implementation yet. |

### Commodity default: do not build from scratch

Custom OCR, PDF renderer/viewer, vector/search infrastructure, auth framework, generic chatbot/RAG shell, notification service, analytics/dashboard platform, CRM clone and premature distributed infrastructure are **not** differentiation. Reuse/adapt them unless a measured gap proves otherwise.

### What we deliberately own

Custom engineering is concentrated in: evidence-bound procurement facts; GO/NO-GO and blockers; nomenclature/catalog matching and substitutions; Supplier → RFQ → TKP; real margin/bid economics; contract/procurement risks; 44-ФЗ/223-ФЗ/private edge cases; and the regression corpus built from real failures.

### Strategy success gates

- ≥70% of new P0/P1 **commodity** work resolves through `REUSE` / `COPY_PATTERN` / `ADAPT`.
- 100% of substantive GO/NO-GO claims have source evidence or explicit `Unknown`.
- No hard decision exists without a traceable `document → page → fragment → conclusion` chain.
- Every confirmed real failure/edge case becomes a regression case.
- Competitor reverse-spec is refreshed at milestone boundaries before commodity scope expands.

## Continuous execution directive — 2026-09-15

The Owner requires the single `Tender Agent Watchdog` to be **work-conserving** at the maximum supported cadence: one exact run per hour. A run should do productive work rather than occupy time waiting for CI or another future condition.

The executor must reconcile issue/PR/done-gate state before continuing a stale checkpoint. If a done gate is already satisfied, it must close/reconcile that task rather than start another acceptance loop. Waiting on CI, external acquisition or human review is checkpointed; the lease is released, and another independent admitted `AUTO` item may progress in an isolated branch/checkpoint. A productive run should normally finish/checkpoint within 45 minutes so the next hourly tick is not lost to an overlapping long session. If executable work exists but no valid progress/lease is observed for more than 90 minutes, the next run treats that as a recovery condition and resumes from canonical state immediately.

This changes utilization/cadence only. It does **not** expand AM-4 authority, queue admission, external-action rights, or `REVIEW` / `OWNER` / `HUMAN` gates.

**Current execution status (2026-09-15):** the watchdog remains configured for exact-hourly autonomous runs and writes an audit record to issue #57, but the current execution queue has no remaining admitted executable item after Commercial Core v1 completion. Therefore an hourly invocation can reconcile/report without making product changes. Continuous *productive development* resumes only when the Product Owner explicitly admits the next bounded queue item; the executor must not invent scope merely to stay busy.

### DOCUMENT-QA-005 reconciliation

`DOCUMENT-QA-005` is **done**: issue #16 had already met its unbiased strict `customer_name` acceptance gate and was closed `completed` before the later #52 calibration. Case #52 is retained as post-acceptance regression evidence. Its generic EIS placement-organization/customer defect was fixed by PR #54 and issue #53 is completed; this does not silently reopen #16 or authorize an endless sequence of fresh blind cases.

## Current reconciliation highlights

- **ARV-001 — quality/product readiness:** current git history records the later governed closure; the July snapshot remains preserved underneath the overlay.
- **ARV-003 — production LLM analysis:** current docs refer to an accepted ARV-003 bundle, while an older R10.1 backlog status still says Gate 5 ready. This inconsistency is preserved as a status-revalidation item rather than silently resolved.
- **ARV-041 — legal SaaS/pilot package:** repository package exists, but the canonical legal release gate remains human: director approval, qualified Russian counsel review and infrastructure/Roskomnadzor/localization/retention checks.
- **ARV-067 — vertical ontologies / electrical equipment knowledge:** electrical ontology assets, taxonomy/profiles/truth packs and gated shadow work are present; current repository tests explicitly keep the ontology out of production runtime. Expert acceptance/evidence remains a gate.
- **ARV-006 — full 223-ФЗ:** restored as a P0 planned product track; it was missing from the narrow executor queue, not from the historical roadmap.
- **ARV-017 / ARV-023:** restored with their actual historical meanings: ARV-017 is tender matching against price lists/catalogs; ARV-023 is supplier search.
- **ARV-073 / ARV-074:** later documents reused these IDs for different work. The conflict is recorded fail-closed; no renumbering or silent reassignment was performed.
- **ARV-076 / ARV-096:** observed after the 2026-07-30 snapshot. They are recorded separately and are not used to invent missing IDs or automatic queue admission.

## Current executor programs

These programs are repository-native benchmark/document-QA execution tracks. No ARV mapping is invented where the repository does not provide one.

| Program | State | Source / completion evidence |
|---|---|---|
| `REUSE-FIRST-001` | **done** | PR #56 merged as `8b1c131`; 9-product reverse-spec + 10-candidate reuse registry |
| `BENCHMARK-PIPELINE-001` | done | issue #1 |
| `DOCUMENT-QA-004` | done | issue #11 |
| `DOCUMENT-QA-005` | **done** | issue #16 accepted/closed; #52/#53 post-acceptance hardening; PR #54 |
| `BUILD-DOCKER-CONTEXT-001` | **done** | issue #19; PR #58 merged as `8924a857` |
| `DISCOVERY-QA-001` | **done** | issue #2; PR #59 merged as `762a392` after Product Owner approval |
| `DECISION-CORE-V1-001` | **done** | issue #60; PR #61 merged as `3bf397f` after Product Owner approval |
| `COMMERCIAL-CORE-V1-001` | **done** | issue #62; PR #63 merged as `4257cd2` after Product Owner approval |
| `DOCUMENT-QA-NEXT-INCREMENT` | deferred_review | issue #3 strategy |

## ID conflicts

| ID | Historical canonical meaning | Later reuse | Resolution |
|---|---|---|---|
| `ARV-073` | R9 Operational Hardening: завершить инженерную отладку и заморозить ядро | ODS local AI infrastructure in docs/product/Product_Backlog.md | unresolved; historical meaning preserved, later reuse is not admitted under this ID automatically |
| `ARV-074` | ODS/Hermes-инфраструктура Mac mini и устранение дублирующихся локальных сервисов | Obsidian Mind memory pilot in docs/product/Product_Backlog.md | unresolved; historical meaning preserved, later reuse is not admitted under this ID automatically |

## Complete recovered roadmap

The table below is a compact view grouped by product block. The machine-readable YAML is authoritative for the full historical fields, normalized dependencies, original dependency surface and evidence overlay.

### 0. База проекта

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `BASE-001` | 0 | Готово | P0 | 100% | ООО «Арвектум» зарегистрировано, реквизиты и корпоративный контур оформлены | needs_revalidation |
| `BASE-002` | 0 | Готово | P1 | 100% | Фирменный стиль, логотип и брендбук | needs_revalidation |
| `BASE-003` | 0 | Базовый контур готов | P1 | 75% | Сайт arvectum.com и базовые digital-каналы | needs_revalidation |
| `BASE-004` | 0 | Готово | P0 | 100% | Backend-фундамент: FastAPI, SQLAlchemy, Alembic, Docker, роли и UI | needs_revalidation |
| `BASE-005` | 0 | Готово | P0 | 100% | PostgreSQL + pgvector + RAG-контур | needs_revalidation |
| `BASE-006` | 0 | Готово | P0 | 100% | Публичный поиск 44-ФЗ и точный поиск по номеру | needs_revalidation |
| `BASE-007` | 0 | Базовый контур готов | P0 | 85% | Рабочий SOAP-контур ЕИС для машиночитаемых данных | needs_revalidation |
| `BASE-008` | 0 | Готово | P0 | 100% | Загрузка закупки и формирование отчётов | needs_revalidation |
| `BASE-009` | 0 | Готово | P0 | 100% | Извлечение товарных позиций и характеристик | needs_revalidation |
| `BASE-010` | 0 | Готово | P0 | 100% | Разделение demo/live и отказ от тихих синтетических fallback | needs_revalidation |
| `BASE-011` | 0 | Базовый контур готов | P0 | 70% | Hermes H1–H4: базовая память, quality gates и feedback | needs_revalidation |
| `BASE-012` | 0 | Базовый контур готов | P0 | 80% | Quality R1–R5: golden loop, provenance и source graph | needs_revalidation |
| `BASE-013` | 0 | Готово | P1 | 100% | Демо- и пилотный пакет документов | needs_revalidation |
| `BASE-014` | 0 | Базовый контур готов | P1 | 65% | Базовый личный кабинет: клиенты, проекты и мастер поиска | needs_revalidation |
| `BASE-015` | 0 | Готово | P1 | 100% | Стабильный рендер PDF на Linux | needs_revalidation |
| `BASE-016` | 0 | Готово | P0 | 100% | R7 controlled pilot baseline: deployment, artifacts, backup/restore и recovery | needs_revalidation |
| `BASE-017` | 0 | Готово | P0 | 100% | R8 Customer Pilot Workspace: изолированный клиентский жизненный цикл | needs_revalidation |
| `BASE-018` | 0 | Готово | P0 | 100% | R9 Operational Hardening: fail-closed recovery, concurrency и backup/restore | needs_revalidation |

### 1. Качество ядра

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `ARV-050` | 0 | Готово | P0 | 100% | R8: изолированное рабочее пространство клиентского пилота | needs_revalidation |
| `ARV-073` | 0 | Готово | P0 | 100% | R9 Operational Hardening: завершить инженерную отладку и заморозить ядро | id_conflict |
| `ARV-002` | 0 | Базовый контур готов | P0 | 90% | Стабильный live end-to-end pipeline без скрытых fallback | needs_revalidation |
| `ARV-003` | 2 | В работе | P0 | 97% | R10.1: production LLM-анализ с evidence map и confidence | accepted_evidence_present_needs_status_revalidation |
| `ARV-001` | 3 | Запланировано | P0 | 85% | R10.2: Quality & Product Readiness — golden report и release gates | completed_governed |
| `ARV-004` | 4 | Запланировано | P0 | 66% | R10.3: production-loop Hermes и customer-scoped feedback | needs_revalidation |
| `ARV-005` | 5 | Запланировано | P0 | 45% | R10.4: контролируемый пилот на 10–20 реальных закупках | needs_revalidation |
| `ARV-067` | 7 | На проверке | P1 | 90% | Вертикальные онтологии и настраиваемые схемы извлечения по категориям | review |
| `ARV-061` | 12 | Запланировано | P1 | 5% | Commercial MVP v1: быстрый cited-преданализ | needs_revalidation |
| `ARV-065` | 37 | Запланировано | P1 | 0% | Evidence-grounded copilot по закупке: Q&A, AI-юрист и сметчик | needs_revalidation |

### 2. Источники и production

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `ARV-009` | 0 | Готово | P0 | 100% | Оценить объём данных, pgvector и требования к диску | confirmed_done |
| `ARV-007` | 0 | Готово | P0 | 100% | Redis как очередь, lock, cache и rate-limit слой | confirmed_done |
| `ARV-075` | 1 | Запланировано | P0 | 0% | Аудит и разгрузка системного диска Mac mini: удалить мусор и перенести данные Арвектум на внешний SSD | needs_revalidation |
| `ARV-008` | 6 | Запланировано | P0 | 25% | Фоновые задания и workers с прогрессом и повторным запуском | needs_revalidation |
| `ARV-010` | 9 | В работе | P0 | 93% | Production-наблюдаемость, безопасность и восстановление | in_progress |
| `ARV-006` | 15 | Запланировано | P0 | 10% | Добавить полноценную работу с 223-ФЗ | needs_revalidation |
| `ARV-074` | 16 | Исследование | P1 | 5% | ODS/Hermes-инфраструктура Mac mini и устранение дублирующихся локальных сервисов | id_conflict |
| `ARV-058` | 17 | Запланировано | P1 | 10% | Возобновляемая синхронизация, локальный кэш и идемпотентный импорт | needs_revalidation |
| `ARV-011` | 18 | В работе | P1 | 55% | Выбрать и арендовать VPS для backend | in_progress |
| `ARV-012` | 19 | Запланировано | P1 | 25% | Переезд с Mac mini на VPS | needs_revalidation |
| `ARV-013` | 20 | Запланировано | P0 | 0% | Заменить временный CloudPub на нормальный production-доступ | needs_revalidation |
| `ARV-014` | 21 | Запланировано | P0 | 28% | Белые списки площадок и Anti-DDoS после появления IP VPS | needs_revalidation |

### 3. Коммерческий MVP

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `ARV-042` | 0 | Готово | P1 | 100% | Пилотная программа и критерии успешности | confirmed_done |
| `ARV-052` | 0 | Готово | P2 | 100% | Human-in-the-loop: экспертная проверка и эскалация сложного отчёта | confirmed_done |
| `ARV-018` | 13 | В работе | P1 | 60% | Commercial MVP v1: карточка GO / NO-GO / NEEDS REVIEW | needs_revalidation |
| `ARV-020` | 14 | Запланировано | P1 | 20% | Commercial MVP v1: чек-лист готовности заявки | needs_revalidation |
| `ARV-015` | 22 | В работе | P1 | 45% | Профиль поставщика для персонального анализа закупок | needs_revalidation |
| `ARV-064` | 23 | Запланировано | P1 | 0% | Корпоративное хранилище документов и переиспользуемый профиль компании | needs_revalidation |
| `ARV-016` | 24 | Запланировано | P1 | 5% | Обработка прайс-листов XLSX/CSV/PDF | needs_revalidation |
| `ARV-017` | 25 | Запланировано | P1 | 0% | Подбор тендеров по прайс-листу и каталогу | needs_revalidation |
| `ARV-053` | 26 | Запланировано | P1 | 0% | Проверка и скоринг контрагентов | needs_revalidation |
| `ARV-019` | 27 | Запланировано | P1 | 10% | Канбан закупок в личном кабинете | needs_revalidation |
| `ARV-063` | 28 | Запланировано | P1 | 0% | Генератор пакета заявки и заполнение клиентских шаблонов | needs_revalidation |
| `ARV-056` | 29 | Запланировано | P1 | 0% | Тендерный календарь, контроль изменений и наблюдение за заказчиками/конкурентами | needs_revalidation |
| `ARV-021` | 30 | Запланировано | P1 | 10% | Мониторинг закупок и уведомления | needs_revalidation |
| `ARV-022` | 36 | Запланировано | P1 | 5% | OCR fallback для сканированных документов | needs_revalidation |
| `ARV-060` | 43 | Запланировано | P2 | 0% | Командное обсуждение закупки: чат, упоминания и журнал решений | needs_revalidation |
| `ARV-066` | 44 | Запланировано | P2 | 0% | Импорт закупки одним кликом: URL, browser extension и share action | needs_revalidation |
| `ARV-055` | 45 | Запланировано | P2 | 0% | Похожие закупки и поиск аналогичных тендеров | needs_revalidation |
| `ARV-057` | 46 | Исследование | P2 | 0% | Исторические цены, база цен и ориентир НМЦК | needs_revalidation |
| `ARV-059` | 47 | Исследование | P2 | 0% | Аналитика фактического исполнения контрактов | needs_revalidation |
| `ARV-069` | 48 | Исследование | P2 | 0% | Прогноз конкуренции, участников и цены подачи | needs_revalidation |

### 4. Go-to-market

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `ARV-041` | 11 | На проверке | P1 | 95% | Добить юридическую обвязку SaaS и пилота | human_gate |
| `ARV-054` | 31 | Запланировано | P1 | 5% | Прозрачные тарифы, pay-per-analysis и мгновенная демоверсия | needs_revalidation |
| `ARV-038` | 33 | В работе | P1 | 45% | Обновить сайт: продукт вместо общей IT-компании | needs_revalidation |
| `ARV-039` | 34 | Запланировано | P1 | 20% | Метрики сайта и продукта | needs_revalidation |
| `ARV-040` | 35 | Запланировано | P1 | 10% | Обновить индексацию в Яндексе и Google | needs_revalidation |

### 5. Поставщики и RFQ

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `ARV-023` | 38 | Запланировано | P1 | 0% | Поиск поставщиков | needs_revalidation |
| `ARV-024` | 39 | Запланировано | P1 | 0% | База поставщиков и история взаимодействия | needs_revalidation |
| `ARV-025` | 40 | Запланировано | P1 | 0% | Интеграция почты пользователя: OAuth/SMTP + IMAP/API | needs_revalidation |
| `ARV-026` | 41 | В работе | P1 | 30% | Автоматическая подготовка и рассылка запросов ТКП | needs_revalidation |
| `ARV-027` | 42 | Запланировано | P1 | 20% | Сравнение ТКП и выбор поставщика | needs_revalidation |
| `ARV-028` | 49 | Запланировано | P1 | 5% | Развернуть self-hosted n8n как внешний оркестратор | needs_revalidation |
| `ARV-029` | 50 | Запланировано | P1 | 0% | Первые n8n-пайплайны | needs_revalidation |

### 6. Коннекторы ЭТП

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `ARV-030` | 51 | В работе | P1 | 35% | Единый слой marketplace connectors | needs_revalidation |
| `ARV-031` | 52 | Запланировано | P1 | 0% | Дедупликация ЕИС и ЭТП | needs_revalidation |
| `ARV-032` | 53 | Исследование | P1 | 10% | Исследовать уникальность данных восьми федеральных ЭТП | needs_revalidation |
| `ARV-033` | 54 | Исследование | P1 | 20% | ТЭК-Торг SOAP proof of concept | needs_revalidation |
| `ARV-036` | 55 | Исследование | P2 | 0% | Интеграция B2B-Center | needs_revalidation |
| `ARV-035` | 56 | Исследование | P2 | 0% | Интеграция Фабрикант | needs_revalidation |
| `ARV-037` | 57 | Исследование | P2 | 0% | Интеграция Tender-Pro | needs_revalidation |
| `ARV-034` | 58 | Запланировано | P2 | 0% | Подключить остальные федеральные ЭТП | needs_revalidation |
| `ARV-071` | 59 | Исследование | P2 | 0% | Buyer-side SRM и структурированные ТКП | needs_revalidation |

### 7. Масштабирование

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `ARV-068` | 32 | Запланировано | P1 | 0% | Учёт потребления, квоты, токены и применение тарифных лимитов | needs_revalidation |
| `ARV-043` | 60 | В работе | P2 | 68% | Multi-tenant SaaS: организации, роли и изоляция данных | needs_revalidation |
| `ARV-046` | 61 | Исследование | P2 | 20% | Enterprise/on-premise и air-gapped deployment | needs_revalidation |
| `ARV-045` | 62 | Отложено | P2 | 0% | Интеграции 1С, CRM, ERP и корпоративных систем | needs_revalidation |
| `ARV-044` | 63 | Отложено | P2 | 5% | Web-first + mobile companion «тендерный радар» | needs_revalidation |
| `ARV-070` | 64 | Отложено | P3 | 0% | Интеграции банковских гарантий и тендерного финансирования после GO | needs_revalidation |

### 8. Поздняя оптимизация

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `ARV-047` | 66 | Отложено | P3 | 0% | OpenSearch / Elasticsearch для расширенного поиска | needs_revalidation |
| `ARV-048` | 67 | Отложено | P3 | 0% | ClickHouse для событий и аналитики | needs_revalidation |
| `ARV-049` | 68 | Отложено | P3 | 0% | Kubernetes / Helm | needs_revalidation |

### 9. Управление разработкой

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `ARV-072` | 8 | В работе | P1 | 35% | Регрессионный competitive benchmark на одинаковых реальных закупках | in_progress |
| `ARV-051` | 10 | Базовый контур готов | P0 | 98% | Протокол параллельной разработки Codex / OpenCode | needs_revalidation |
| `ARV-062` | 65 | Запланировано | P1 | 0% | Настроить полное зеркало репозитория ai-corporation в GitVerse | needs_revalidation |

## Post-snapshot observed IDs

| ID | Work | State | Admission |
|---|---|---|---|
| `ARV-076` | Docker/Colima backup and restore | implementation_present_acceptance_followup | not inferred into execution queue |
| `ARV-096` | Real EIS document-set acceptance | observed_post_snapshot_work | not inferred into execution queue; gaps ARV-077..ARV-095 are not invented |

## Executor rule

`.agent/execution-queue.yaml` must point back to this master roadmap and may contain only explicitly admitted executable items. The executor may update queue execution status/evidence within its existing authority, but it must not promote a master-roadmap item, resolve an ID collision, change priority/scope, or infer a new ARV mapping by itself.

When a roadmap item becomes ready for execution, the Product Owner/Owner or another already-authorized canonical mechanism must create/promote the corresponding queue entry with explicit authority, dependencies, done gate and merge policy.
