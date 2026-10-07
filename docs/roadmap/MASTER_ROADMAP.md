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
| **1. Thin commodity shell** | P0 | **done** | Dedicated acceptance matrix proves baseline search/filter + versioned saved profiles + tender card + document download/parsing adapters + auth/visibility + monitoring alerts + export. Focused gate 67 passed / 10 skipped; exact-head CI `37612128040` SUCCESS 9/9; closure PR #192 merged as `a58ec11`. No new commodity subsystem was required. |
| **2. Decision Core v1** | P0 | **done** | Discovery benchmark/hardening PR #59 merged (`762a392`); Decision Core v1 PR #61 merged (`3bf397f`) with evidence-bound fail-closed decisions. |
| **3. Commercial Core** | P0 | **done** | PR #63 merged (`4257cd2`): price-list ingest, tender-to-catalog matching, coverage/cost/headroom and auditable commercial feasibility with HUMAN control. |
| **4. Automation + integrations** | P1 | **done at admitted v1 boundary** | PR #74 (`56ca227`) change monitoring + PR #75 (`fbf6d3c`) ingest resilience + PR #79 (`4149801`) internal integration outbox. External delivery remains disabled and separately gated. |
| **5. Reliability + moat** | P1 | **done at admitted v1 boundary** | PR #76 (`c335c60`) ops observability + PR #77 (`c5e653a`) domain regression registry + PR #80 (`dc87a0b`) read-only 223-ФЗ intake + review-approved PR #81 (`f603c9f`) 223-ФЗ Decision Core. |

### Stage 1 acceptance — 2026-10-07

Stage 1 is now closed at its original exit gate. The accepted commodity journey is:

`authenticated operator → search/filter or versioned saved profile → result/tender card → source document download/parsing adapter → watch/alert feed → report/export`

The closure reuses existing Tender Agent components rather than introducing a new search engine, viewer, auth framework, notification platform, CRM or export stack. Full enterprise IAM/SSO, arbitrary dashboard CRUD, inline PDF.js-style viewing and external notification delivery remain separate future scopes and are not Stage 1 blockers. Acceptance evidence is recorded in `docs/strategy/STAGE1_THIN_COMMODITY_SHELL_ACCEPTANCE.md` and `tests/test_stage1_thin_commodity_shell.py`.

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

**Historical execution snapshot (2026-09-18):** at that point every explicitly admitted queue item through order 80 was completed and the queue was temporarily exhausted. This paragraph is retained only as history; it is **not** the current executor state.

**Current execution status (2026-10-07, 21:32 MSK):** the full canonical **COMMERCIAL-WORKFLOW** branch remains admitted and is now **2/12 complete**. `ARV-015-OPERATOR-PROFILE-PARSER-001` merged in PR #199 (`94534c81`) and `COMMERCIAL-WORKFLOW-ARV-019-001` merged in PR #198 (`8f13060b`) with completion bookkeeping in PR #201 (`0948f5f4`). The next ready item is **ARV-022 OCR fallback** (`COMMERCIAL-WORKFLOW-ARV-022-001`); ten branch items remain. Existing OCR work in PR #129 should be recovered/rebased where useful rather than duplicated. The renewed Company AM-4 cycle is now conservatively counted at **3/10** automatic merges (#199, #198, #201); the next time-based review deadline remains 2026-11-07. All procurement submission, EDS/signature, external communication, legal/commercial acceptance and other hard stops remain unchanged.

## Owner product directive — 2026-10-06: Daily Tender Run + iPhone Tender Agent

The Product Owner promotes the real daily procurement workflow observed in production use into the next product layer.

### A. Daily Tender Run — P0

Goal: make the routine workflow reproducible end-to-end with one scheduled/backend run while keeping the substantive bid decision human.

Canonical flow:

EIS search/filter → dedupe → shortlist → document acquisition on Mac mini → Data Platform → deep analysis → evidence-bound summary → manager inbox → HUMAN GO / NO GO / DEFER → application readiness → submission tracking → outcome → postmortem → portfolio metrics.

Required behavior:

- saved filters on a configurable schedule plus manual rerun;
- deduplicate already-seen procurements and reprocess only material changes;
- cheap screening before expensive deep analysis;
- EIS documents acquired through Mac mini and analyzed locally via Data Platform;
- one manager digest plus one evidence-grounded report per shortlisted procurement;
- agent recommendation, rationale, confidence, blockers and evidence persisted separately from the human decision;
- GO / NO GO / DEFER is the explicit manager gate;
- after GO, prepare readiness artifacts automatically without fabricating submission/signature success;
- capture factual submission, platform, price, timestamps, outcome, winning price/participant and postmortem cause when evidence exists;
- write stages into the canonical event/decision/outcome lifecycle and Procurement Portfolio.

Success gate: a normal business day can be processed without chat-driven orchestration; the manager only reviews prepared summaries and records a decision.

This reuses existing search, intake, Data Platform, screening, decision log, submission control, outcome intake, postmortem and Procurement Portfolio capabilities. It is not a parallel data model.

### B. ARV-044 mobile companion — promoted to P0 owner priority

Historical ARV-044 remains immutable in the recovered snapshot. The Owner now promotes its current product meaning from a deferred lightweight “tender radar” into the primary iPhone decision client for Tender Agent.

MVP contract:

- native SwiftUI iPhone app;
- Mac mini remains the Tender Agent backend;
- private backend access through Tailscale for the internal MVP;
- APNs push for new reports, deferred-due items, material procurement changes, deadline risk and published outcomes;
- inbox/digest with manager-ready summaries;
- procurement card with NMCK, deadline, recommendation, blockers, risks, unknowns and evidence;
- explicit GO / NO GO / DEFER actions with optional reason/comment;
- mobile Portfolio for decisions, submissions and outcomes;
- deep links to EIS/full web report;
- mobile decisions written to the same canonical decision log as web decisions.

Human boundary:

- the app may present the agent recommendation but never turns it into a bid decision automatically;
- ETP/EDS/signature actions remain explicit human steps where required;
- submission/result states are recorded only from real evidence or explicit human confirmation.

Detailed spec: docs/product/Daily_Tender_Run_and_iPhone_MVP.md.

**Current product status (2026-10-07):** **MOB-4 is completed and merged** in PR #183 as `bdcd868f1c42f3d3165cc8cad2c83b63b682521b`; exact-head CI run `37584606448` passed all 9 jobs. The iPhone Portfolio now consumes the canonical Procurement Portfolio projection for decision/submission/outcome totals and rates, provides deterministic pipeline/outcome filters, shows grounded submission/outcome timestamps and rationale/postmortem data, and refreshes canonical state before opening a deep-linked case. Missing evidence remains pending/unknown. **DTR-3** remains completed in PR #180 (`3b25e10`) and preserves the same HUMAN/source-evidence gates. No new mobile stage is admitted by this reconciliation.

### Delivery sequence

| Stage | Priority | Deliverable | Exit condition |
|---|---|---|---|
| DTR-1 | P0 | **DONE — Daily Tender Run domain/orchestrator + persisted state** | Pre-decision contour remains implemented and restartable |
| DTR-2 | P0 | **DONE — manager inbox/digest API + mobile façade** | Pre-decision manager-attention contour remains implemented |
| MOB-1 | P0 | **DONE — SwiftUI read-only inbox + procurement summary** | PR #171 merged; iPhone securely reads live Mac mini reports |
| MOB-2 | P0 | **DONE — GO / NO GO / DEFER API + mobile actions** | PR #173 merged; human mobile decisions are audited and visible in Procurement Portfolio |
| MOB-3 | P0 | **DONE — APNs push + deep links** | PR #176 merged; bounded push/deep-link routing opens the correct Tender Agent case |
| DTR-3 | P1 | **DONE — post-GO readiness + submission/result monitoring** | PR #180 merged; only HUMAN/source-grounded evidence advances readiness, submission and outcome state |
| MOB-4 | P1 | **DONE — mobile portfolio/metrics polish** | PR #183 merged; canonical pipeline/outcomes and factual rates are comfortable to review from phone |

Roadmap status is now reconciled to execution: MOB-1, MOB-2, MOB-3, DTR-3 and MOB-4 were separately admitted, completed, and merged. This closes the currently defined bounded iPhone delivery sequence; this roadmap update does **not** admit a new development item.

### DOCUMENT-QA-005 reconciliation

`DOCUMENT-QA-005` is **done**: issue #16 had already met its unbiased strict `customer_name` acceptance gate and was closed `completed` before the later #52 calibration. Case #52 is retained as post-acceptance regression evidence. Its generic EIS placement-organization/customer defect was fixed by PR #54 and issue #53 is completed; this does not silently reopen #16 or authorize an endless sequence of fresh blind cases.

## Current reconciliation highlights

- **BASE-001..BASE-018:** current reconciliation is **18/18 confirmed_done**. This is a current evidence overlay only; the historical 2026-07-30 percentages and statuses remain unchanged. BASE-011 is closed as the Hermes infrastructure foundation, while real-user self-improvement is retained under ARV-004 as a post-MVP, not-admitted Feedback & Learning Loop.
- **Current queue — 2026-10-07:** COMMERCIAL-WORKFLOW is **2/12 complete**. Done: ARV-015 structured operator profile ingestion and ARV-019 procurement kanban/operator workflow. Next: ARV-022 OCR fallback. Remaining admitted after ARV-022: ARV-053, ARV-055, ARV-057, ARV-059, ARV-060, ARV-063, ARV-064, ARV-066, ARV-069. The watchdog may continue autonomously under renewed AM-4 while all consequential external actions and Product/HUMAN/REVIEW gates remain fail-closed.
- **ARV-044 — mobile companion:** current Owner priority is P0; MOB-1 is complete in PR #171 (`01b4be72`), MOB-2 in PR #173 (`fe92b39`), MOB-3 in PR #176 (`3ab3872`), and MOB-4 in PR #183 (`bdcd868`). DTR-3 post-GO orchestration is also complete in PR #180 (`3b25e10`) and preserves the same HUMAN participation boundary. The currently defined native-iPhone MVP sequence is implemented; Android, public multi-tenant release and autonomous decision/submission remain deferred and are not implied complete. Historical 2026-07-30 P2/5% fields remain unchanged in the immutable snapshot.
- **ARV-001 — quality/product readiness:** current git history records the later governed closure; the July snapshot remains preserved underneath the overlay.
- **ARV-003 — production LLM analysis:** current docs refer to an accepted ARV-003 bundle, while an older R10.1 backlog status still says Gate 5 ready. This inconsistency is preserved as a status-revalidation item rather than silently resolved.
- **ARV-041 — legal SaaS/pilot package:** repository package exists, but the canonical legal release gate remains human: director approval, qualified Russian counsel review and infrastructure/Roskomnadzor/localization/retention checks.
- **ARV-067 — vertical ontologies / electrical equipment knowledge:** electrical ontology assets, taxonomy/profiles/truth packs and gated shadow work are present; current repository tests explicitly keep the ontology out of production runtime. Expert acceptance/evidence remains a gate.
- **ARV-006 — full 223-ФЗ:** the bounded v1 intake and evidence-bound decision increments are now completed (PR #80 + #81). This advances ARV-006 materially but does not silently claim every historical meaning of “full 223-ФЗ support” is finished; residual breadth remains a future scope decision.
- **ARV-017 / ARV-023:** restored with their actual historical meanings: ARV-017 is tender matching against price lists/catalogs; ARV-023 is supplier search.
- **ARV-010 / ARV-021 / ARV-025 / ARV-029 / ARV-031 / ARV-045 / ARV-056 / ARV-058 / ARV-072:** bounded v1 infrastructure has now landed through PRs #74–#77 and #79. Historical broader meanings remain immutable; the reconciliation overlay records implemented foundations without claiming unbuilt external transports, full connector breadth, or later analytics are complete.
- **ARV-073 / ARV-074:** later documents reused these IDs for different work. The conflict is recorded fail-closed; no renumbering or silent reassignment was performed.
- **ARV-076 / ARV-096:** observed after the 2026-07-30 snapshot. They are recorded separately and are not used to invent missing IDs or automatic queue admission.

## Current executor programs

The accelerated admitted pipeline that was active on 2026-09-15 is now fully reconciled as completed.

| Program | State | Source / completion evidence |
|---|---|---|
| `REUSE-FIRST-001` | **done** | PR #56 merged as `8b1c131`; 9-product reverse-spec + 10-candidate reuse registry |
| `BENCHMARK-PIPELINE-001` | done | issue #1 |
| `DOCUMENT-QA-004` | done | issue #11 |
| `DOCUMENT-QA-005` | **done** | issue #16 accepted/closed; #52/#53 post-acceptance hardening; PR #54 |
| `BUILD-DOCKER-CONTEXT-001` | **done** | issue #19; PR #58 merged as `8924a857` |
| `DISCOVERY-QA-001` | **done** | issue #2; PR #59 merged as `762a392` |
| `DECISION-CORE-V1-001` | **done** | issue #60; PR #61 merged as `3bf397f` |
| `COMMERCIAL-CORE-V1-001` | **done** | issue #62; PR #63 merged as `4257cd2` |
| `DOCUMENT-QA-NEXT-INCREMENT` | **done** | issue #51; PR #73 merged as `dca11d4` |
| `CHANGE-MONITORING-V1-001` | **done** | issue #65; PR #74 merged as `56ca227` |
| `INGEST-RESILIENCE-V1-001` | **done** | issue #66; PR #75 merged as `fbf6d3c` |
| `INTEGRATION-OUTBOX-V1-001` | **done** | issue #67; PR #79 merged as `4149801` |
| `OPS-OBSERVABILITY-V1-001` | **done** | issue #68; PR #76 merged as `c335c60` |
| `223FZ-INGEST-V1-001` | **done** | issue #69; PR #80 merged as `dc87a0b` |
| `223FZ-DECISION-V1-001` | **done** | issue #70; PR #81 merged as `f603c9f` after explicit Product Owner approval |
| `DOMAIN-REGRESSION-V1-001` | **done** | issue #71; PR #77 merged as `c5e653a` |
| `MOB-1-IOS-INBOX-001` | **done** | ARV-044 P0 slice; PR #171 merged as `01b4be72`; exact-head CI `37518592972` SUCCESS |
| `MOB-2-IOS-DECISIONS-001` | **done** | ARV-044 P0 slice; PR #173 merged as `fe92b39`; exact-head CI `37524387682` SUCCESS |
| `MOB-3-IOS-PUSH-DEEPLINKS-001` | **done** | ARV-044 P0 slice; PR #176 merged as `3ab3872`; exact-head CI `37533637202` SUCCESS; physical APNs delivery still requires Apple push entitlement/credentials |
| `DTR-3-POST-GO-AUTOMATION-001` | **done** | Daily Tender Run post-GO slice; PR #180 merged as `3b25e10`; exact-head CI `37575956723` SUCCESS 9/9; readiness/submission/outcome advancement remains HUMAN/source-evidence gated |
| `MOB-4-IOS-PORTFOLIO-METRICS-001` | **done** | ARV-044 P1 polish; PR #183 merged as `bdcd868`; exact-head CI `37584606448` SUCCESS 9/9; canonical portfolio metrics/outcomes only, no new consequential action |

### Execution queue after reconciliation

The earlier order-80 execution snapshot has been superseded by later Owner-directed work. As of **2026-10-07**, `MOB-1-IOS-INBOX-001`, `MOB-2-IOS-DECISIONS-001`, `MOB-3-IOS-PUSH-DEEPLINKS-001`, `DTR-3-POST-GO-AUTOMATION-001`, and `MOB-4-IOS-PORTFOLIO-METRICS-001` are **done and merged**. `ARV-005-CONTROLLED-PILOT-EVIDENCE-001` has also satisfied its technical done gate: the frozen 12-case 44-FZ core produced 12 reports, the three exploratory 223-FZ cases are separately scored source-bound blockers, and the aggregate report is preserved under `docs/pilot/`. BASE-001..BASE-018 are now **18/18 confirmed_done** in the current reconciliation overlay. Human usefulness/commercial acceptance remains HUMAN/REVIEW. There are now **no non-done admitted queue items**; the next bounded item must be admitted under the active Owner continuation rule rather than inferred from roadmap presence.

### Available continuation branches — candidate matrix

These are **roadmap branches, not admitted work**. Selecting one means creating a bounded task/Definition of Done and explicitly admitting it to the execution queue. The historical IDs listed here are preserved; this matrix does not create new ARV IDs.

| Branch | Historical scope | What remains useful to do | Main gate |
|---|---|---|---|
| **CORE-QUALITY-PILOT** | ARV-002, 003, 004, 005, 061, 065, 067 | Revalidate live E2E/LLM readiness; finish Hermes/customer feedback loop; controlled 10–20 procurement pilot; fast cited pre-analysis; evidence-grounded copilot; ontology acceptance | Pilot/customer evidence and ARV-067 expert acceptance are REVIEW/HUMAN |
| **PRODUCTION-RUNTIME** | ARV-008, 010, 011–014, 075 | Workers/jobs; residual security/recovery after observability v1; VPS/production access/migration/allowlists; Mac storage revalidation | Production/network/provider/local destructive changes require explicit applicable authority |
| **COMMERCIAL-WORKFLOW** | ARV-015, 019, 022, 053, 055, 057, 059, 060, 063, 064, 066, 069 | Supplier profile; kanban; reusable OCR fallback; counterparty checks; company docs; application package; collaboration/import; later analytics | No automated participation decision, legal acceptance or application submission |
| **SUPPLIER-RFQ** | ARV-023–029 | Supplier search/database; user-mail adapter; RFQ/TKP preparation/comparison; n8n orchestration | External supplier/customer email/RFQ send remains REVIEW/HUMAN |
| **ETP-CONNECTORS** | ARV-030–037, 071 | Unified marketplace connector layer; federal ETP uniqueness research; TEK-Torg/Fabrikant/B2B-Center/Tender-Pro/other ETPs | Read-only acquisition can be bounded; authenticated/consequential platform actions need separate authority |
| **223FZ-BREADTH** | ARV-006 | Expand beyond completed read-only intake + Decision Core v1 using measured source/procedure gaps | New breadth needs concrete regression/corpus evidence; unsupported legal/procedural claims remain UNKNOWN/NEEDS_REVIEW |
| **MONITORING-DELIVERY** | ARV-021, 056, 025, 029, 045 | Extend completed internal monitoring/outbox foundation to approved email/CRM/webhook/scheduled-reporting adapters | Live external delivery remains disabled until separate REVIEW/HUMAN authority |
| **COMPETITIVE-BENCHMARK** | ARV-072 | Use completed domain-regression infrastructure for identical-procurement competitor benchmark refresh | Corpus/method frozen before outputs; anti-circularity mandatory |
| **GO-TO-MARKET** | ARV-038–041, 054 | Product-first site; metrics; indexing; tariffs/demo; legal SaaS/pilot package | ARV-041 remains director/counsel/regulatory HUMAN gate; pricing/public commitments need Owner approval |
| **SAAS-SCALE** | ARV-043–046, 068, 070 | Multi-tenant orgs/roles/isolation; quotas; on-prem/air-gapped; mobile expansion beyond the completed internal iPhone MVP (for example public/multi-tenant or Android); later finance/integration | Financing/guarantees/external enterprise commitments are HUMAN/commercial gates |
| **DEVELOPMENT-GOVERNANCE** | ARV-051, 062 | Revalidate parallel-development protocol; mirror posture; reusable Project Watchdog binding | Must not alter Company/Product authority; open PR #78 is maintenance only |
| **LATE-INFRA** | ARV-047–049 | OpenSearch, ClickHouse, Kubernetes/Helm when measured need appears | Deferred + reuse-first measured-gap gate |
| **STATUS-REVALIDATION** | BASE-003, 007, 011, 012, 014; ARV-003, 051, 075 | Reconcile stale July progress/status values against current repository/runtime evidence | Status reconciliation only; no implementation authority |
| **ID-CONFLICT-RESOLUTION** | ARV-073, ARV-074 | Resolve later ID reuse versus preserved historical meanings without silent renumbering | Explicit OWNER reconciliation required |

The already delivered Decision Core, Commercial Core, monitoring, ingest resilience, integration outbox, observability, 223-ФЗ v1 and domain-regression foundations should **not** be reopened as generic continuation branches without a concrete regression or an explicitly new bounded increment.


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
| `BASE-001` | 0 | Готово | P0 | 100% | ООО «Арвектум» зарегистрировано, реквизиты и корпоративный контур оформлены | confirmed_done |
| `BASE-002` | 0 | Готово | P1 | 100% | Фирменный стиль, логотип и брендбук | confirmed_done |
| `BASE-003` | 0 | Базовый контур готов | P1 | 75% | Сайт arvectum.com и базовые digital-каналы | confirmed_done |
| `BASE-004` | 0 | Готово | P0 | 100% | Backend-фундамент: FastAPI, SQLAlchemy, Alembic, Docker, роли и UI | confirmed_done |
| `BASE-005` | 0 | Готово | P0 | 100% | PostgreSQL + pgvector + RAG-контур | confirmed_done |
| `BASE-006` | 0 | Готово | P0 | 100% | Публичный поиск 44-ФЗ и точный поиск по номеру | confirmed_done |
| `BASE-007` | 0 | Базовый контур готов | P0 | 85% | Рабочий SOAP-контур ЕИС для машиночитаемых данных | confirmed_done |
| `BASE-008` | 0 | Готово | P0 | 100% | Загрузка закупки и формирование отчётов | confirmed_done |
| `BASE-009` | 0 | Готово | P0 | 100% | Извлечение товарных позиций и характеристик | confirmed_done |
| `BASE-010` | 0 | Готово | P0 | 100% | Разделение demo/live и отказ от тихих синтетических fallback | confirmed_done |
| `BASE-011` | 0 | Базовый контур готов | P0 | 70% | Hermes H1–H4: базовая память, quality gates и feedback | confirmed_done |
| `BASE-012` | 0 | Базовый контур готов | P0 | 80% | Quality R1–R5: golden loop, provenance и source graph | confirmed_done |
| `BASE-013` | 0 | Готово | P1 | 100% | Демо- и пилотный пакет документов | confirmed_done |
| `BASE-014` | 0 | Базовый контур готов | P1 | 65% | Базовый личный кабинет: клиенты, проекты и мастер поиска | confirmed_done |
| `BASE-015` | 0 | Готово | P1 | 100% | Стабильный рендер PDF на Linux | confirmed_done |
| `BASE-016` | 0 | Готово | P0 | 100% | R7 controlled pilot baseline: deployment, artifacts, backup/restore и recovery | confirmed_done |
| `BASE-017` | 0 | Готово | P0 | 100% | R8 Customer Pilot Workspace: изолированный клиентский жизненный цикл | confirmed_done |
| `BASE-018` | 0 | Готово | P0 | 100% | R9 Operational Hardening: fail-closed recovery, concurrency и backup/restore | confirmed_done |

### 1. Качество ядра

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `ARV-050` | 0 | Готово | P0 | 100% | R8: изолированное рабочее пространство клиентского пилота | confirmed_done |
| `ARV-073` | 0 | Готово | P0 | 100% | R9 Operational Hardening: завершить инженерную отладку и заморозить ядро | id_conflict |
| `ARV-002` | 0 | Базовый контур готов | P0 | 90% | Стабильный live end-to-end pipeline без скрытых fallback | confirmed_done |
| `ARV-003` | 2 | В работе | P0 | 97% | R10.1: production LLM-анализ с evidence map и confidence | accepted_evidence_present_needs_status_revalidation |
| `ARV-001` | 3 | Запланировано | P0 | 85% | R10.2: Quality & Product Readiness — golden report и release gates | completed_governed |
| `ARV-004` | 4 | Запланировано | P0 | 66% | R10.3: production-loop Hermes и customer-scoped feedback | needs_revalidation — post-MVP, not admitted |
| `ARV-005` | 5 | Запланировано | P0 | 45% | R10.4: контролируемый пилот на 10–20 реальных закупках | confirmed_done |
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
| `ARV-010` | 9 | В работе | P0 | 93% | Production-наблюдаемость, безопасность и восстановление | confirmed_done |
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
| `ARV-015` | 22 | В работе | P1 | 45% | Профиль поставщика для персонального анализа закупок | revalidated_residual_gap |
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
| `ARV-038` | 33 | В работе | P1 | 45% | Обновить сайт: продукт вместо общей IT-компании | review |
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

## Continuous Owner-directed continuation

`OWNER-CONTINUOUS-ROADMAP-2026-09-18` keeps the hourly executor work-conserving when the admitted queue becomes empty. Selection is deterministic from the continuation matrix in document order, one bounded item per run. Existing bounded tasks are preferred; otherwise only an evidence/revalidation slice may be materialized. This does **not** authorize product-priority invention, new material architecture, authority downgrades, production/external effects, or bypass of REVIEW/HUMAN/OWNER gates.

The first materialized continuation slice is `ARV-002-REVALIDATION-001` under `CORE-QUALITY-PILOT`. The 2026-09-18 watchdog policy change is material for Company AM-4 review purposes, so future automatic merges fail closed to REVIEW until attributable Owner renewal; implementation/testing/review-ready PR preparation may continue.

## ARV-002 revalidation — 2026-09-19

Current exact-number public EIS lookup is live and the source-to-handoff/source-graph/recovery regressions are green. The revalidation did **not** mark ARV-002 fully done: the current EIS search-card parser can populate `customer_name` with page JavaScript via an overly broad fallback, while the stricter common-info detail extractor returns the correct explicit customer.

Evidence and the single bounded, non-admitted successor candidate `ARV-002-LIVE-CUSTOMER-PARSE-001` are recorded in `docs/roadmap/ARV-002_REVALIDATION_2026-09-19.md` and the ARV-002 reconciliation overlay. No implementation authority is inferred from candidate status.

### ARV-002 residual closure — 2026-10-07

The Owner explicitly admitted ARV-002-LIVE-CUSTOMER-PARSE-001. The raw-HTML customer regex fallback was removed, a deterministic JavaScript-pollution regression fixture was added, and search cards now fail closed to customer_name=null unless explicit customer-scoped evidence exists. The common-info detail extractor remains authoritative.

Verification: 87 focused live-path/parser/source-graph/no-fallback tests passed; the companion persistence/recovery gate passed 32 tests with 12 environment/profile skips; make check passed; and a read-only exact-number EIS run for 0888500000226000399 returned a clean fail-closed search card plus the correct explicit detail-page customer. Evidence is in docs/roadmap/ARV-002_LIVE_CUSTOMER_PARSE_2026-10-07.md. The reconciliation state is now confirmed_done, subject to exact-head CI/merge of the closure commit.

## ARV-010 revalidation — 2026-09-20

The historical ARV-010 storage guardrails were followed by merged `OPS-OBSERVABILITY-V1` / PR #76. Current main now has a versioned `/api/ops/observability` snapshot for queue age/depth, ingestion/document failures, storage guard state, backup freshness and recent worker failures, with deterministic warning/critical/unknown semantics plus a non-destructive incident runbook.

The reconciliation overlay marks ARV-010 `confirmed_done` for its repository-side umbrella. This does **not** claim live external notifications, third-party telemetry deployment, production mutation or provider-side monitoring; those remain separately gated scopes.

## ARV-015 revalidation — 2026-09-21

Current main already has a reusable M-006 supplier registry and Decision Core supplier-profile binding, while the RFQ-first `Tender_Operator_Profile_Template.md` defines categories, regions, NMCK/VAT/financial constraints, risk preferences and licenses/SRO. The runtime PP1R parser currently only records profile presence/preview metadata and does not turn those fields into a reusable structured profile.

The bounded non-admitted successor `ARV-015-OPERATOR-PROFILE-PARSER-001` is recorded in `docs/roadmap/ARV-015_REVALIDATION_2026-09-21.md`. It deliberately reuses the existing template and Decision Core; it does not invent a parallel profile subsystem.

## ARV-006 revalidation — 2026-09-21

Merged 223-FZ intake and Decision Core already provide dedicated public search/card intake, source-bound basic facts, document discovery, revision ambiguity guards and fail-closed regime semantics. ARV-006 remains partial: lots/positions and structured changes, clarifications, protocols and status lifecycle are not yet established. One source-traceable successor candidate is recorded as `candidate_not_admitted`; no new 223-FZ implementation or legal rule is authorized by this reconciliation.

## BASE-011 / ARV-004 product-boundary reconciliation — 2026-10-07

BASE-011 is now `confirmed_done` as the Hermes infrastructure foundation. The repository already has the bounded primitives named by the BASE item: client/fallback behavior, runtime context, category profiles, normalization, quality gates, feedback/memory, eval-case generation, supplier-readiness and bid-decision helpers.

The unfinished real-user self-improvement capability is not a BASE prerequisite. It is retained under existing `ARV-004` as the **post-MVP Feedback & Learning Loop**, documented in `docs/product/Feedback_Learning_Loop.md`. ARV-004 is deliberately not admitted to the execution queue at this stage.

The successor loop is constrained to attributable correction → immutable human review → regression case → validated reusable-rule candidate → reviewed promotion. External Hermes runtime is optional, automatic cross-customer learning is prohibited, and canonical HUMAN GO / NO GO / DEFER authority remains unchanged.

## Executor rule

`.agent/execution-queue.yaml` must point back to this master roadmap and may contain only explicitly admitted executable items. The executor may update queue execution status/evidence within its existing authority, but it must not arbitrarily promote a master-roadmap item, resolve an ID collision, change priority/scope, or infer a new ARV mapping by itself.

While `OWNER-CONTINUOUS-ROADMAP-2026-09-18` is active, its deterministic one-at-a-time bounded-materialization rule is itself an explicitly authorized canonical admission mechanism: the watchdog may select the next eligible continuation item in document order and admit only the bounded form permitted by `.agent/owner-directive.yaml`. Outside that mechanism, roadmap promotion still requires Product Owner/Owner or another separately authorized canonical source.
