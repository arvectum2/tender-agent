# Product Backlog

Updated: 2026-09-14
Canonical strategy source: `docs/roadmap/master-roadmap.yaml` / `docs/roadmap/MASTER_ROADMAP.md`

## Reuse-first operating policy — 2026-09-14

Default question for every new item: **“Who already solved this, and what can we reuse or lawfully reimplement before writing custom code?”**

Every new/active P0/P1 item gets exactly one delivery strategy: `REUSE`, `COPY_PATTERN`, `ADAPT`, or `INVENT`. `INVENT` requires a written reuse check, gap, differentiating value and ownership-cost justification. Otherwise it is not admitted as a custom build.

Product shape: **Thin Commodity Shell + Deep Decision Core**. Commodity UX/infrastructure should converge quickly on proven market patterns; differentiation belongs in evidence-bound tender decisions and commercial workflow.

## P0 — accelerated backlog

- [ ] **REUSE-FIRST-001 / Stage 0 — Competitive reverse-spec + reuse registry** (`COPY_PATTERN`) — benchmark 8–10 direct competitors on `search → results → tender card → documents → AI analysis → decision → next action`; for every step record the best reference, pattern to copy, what Tender Agent must do better, reusable OSS/API options, license/legal notes and whether custom code is justified.
- [ ] **Stage 0 — P0/P1 backlog triage** (`ADAPT`) — classify every active P0/P1 item; split mixed tasks so commodity subparts are reused/adapted and only the moat boundary can remain `INVENT`; explicitly de-scope duplicate commodity engineering.
- [ ] **Stage 1 — Thin commodity shell** (`REUSE` / `COPY_PATTERN` / `ADAPT`) — search/filter/saved views, tender card, document viewer/parsing, auth/roles, alerts and export at baseline quality only. No custom multi-sprint build without an approved gap.
- [ ] **Stage 2 — Decision Core v1** (`INVENT`) — source-bound facts, `document → page → fragment → conclusion`, hard blockers, deterministic rules, GO/NO-GO/NEEDS REVIEW, risk/unknown/confidence, regression corpus and labeled evaluation. Current `DOCUMENT-QA-005` work belongs here and remains valid because it fixes procurement-specific evidence integrity.
- [ ] **Stage 3 — Commercial Core** (`INVENT` at the moat boundary) — nomenclature normalization, customer-catalog matching, substitutes/compatibility, supplier qualification/handoff, RFQ/TKP, landed cost, margin and bid economics; reuse generic parsers/discovery/connectors underneath.

## P1 — only after validated core value

- [ ] **Stage 4 — Automation + integrations** (`ADAPT`) — alerts, email/CRM/source connectors, API/webhooks and scheduled reporting when a validated operator workflow needs them.
- [ ] **Stage 5 — Reliability + moat** (`INVENT` only for domain depth) — 44-ФЗ/223-ФЗ/private edge cases, decision-outcome telemetry, security/compliance, deeper integrations and continuous regression expansion.

## Explicit do-not-build list

Do not build custom OCR, PDF renderer/viewer, vector/search engine, auth framework, generic chatbot/RAG shell, notification service, analytics/dashboard platform, CRM clone or premature distributed infrastructure unless Stage 0 records a concrete measured gap.

## Existing roadmap strategy map

| Work | Strategy | Custom boundary / rationale |
|---|---|---|
| `DOCUMENT-QA-005` | `INVENT` | Procurement-specific source/role precedence and evidence integrity |
| `ARV-018` GO/NO-GO | `INVENT` | Core evidence-grounded decision product |
| `ARV-020` readiness checklist | `INVENT` | Only evidence-bound procurement blockers/requirements |
| `ARV-061` cited pre-analysis | `ADAPT` | Reuse retrieval/extraction; own cited procurement reasoning |
| `ARV-065` copilot/Q&A | `ADAPT` | Reuse generic Q&A/RAG; no generic chat platform |
| `ARV-016` price-list ingest | `ADAPT` | Reuse file parsers; custom starts at nomenclature normalization |
| `ARV-017` tender ↔ catalog matching | `INVENT` | Commercial moat |
| `ARV-023` supplier search | `ADAPT` | Reuse discovery/connectors; own ranking/qualification/RFQ handoff |
| `ARV-019` kanban | `COPY_PATTERN` | Commodity operator UX |
| `ARV-021` monitoring/notifications | `ADAPT` | Standard scheduling/notification primitives |
| `ARV-022` OCR fallback | `REUSE` | Existing OCR engines only |
| `ARV-056` calendar/change control | `COPY_PATTERN` | Commodity workflow pattern |
| `ARV-063` application package generator | `ADAPT` | Reuse document/template tooling; own procurement rules only |
| `ARV-047/048/049` search/events/K8s infra | `REUSE` | Standard infrastructure and still deferred until evidence demands it |

## Deferred Until After MVP v1

- SaaS hardening for multi-tenant deployment
- production auth and access-control layer
- deployment automation and operational packaging
- UI polish beyond the commercial operator skeleton
- procurement platform integrations
- supplier outbound automation
- EDS/signature workflow
- post-award commercialization and external execution

## Open Follow-Ups

- [ ] [ARV-001 / #87](https://github.com/arutyunoveth/ai-corporation/issues/87) — merge the deterministic golden-report gate, then complete the Mac mini acceptance on one approved real R10.1 report; freeze policy v1 only after two independent reviews, exact artifact hashes and a `PASS` manifest; synthetic fixtures cannot close the task
- [ ] [ARV-072 / #41](https://github.com/arutyunoveth/ai-corporation/issues/41) — execute the controlled competitive benchmark on identical real procurements; keep public-surface research separate from live output scoring
- [ ] [ARV-073 / #71](https://github.com/arutyunoveth/ai-corporation/issues/71) — install and customize ODS on the Mac mini as the local AI infrastructure layer; keep Hermes as the required bounded agent runtime; connect `ai-corporation` through LiteLLM/`ods/current`; inventory, migrate and safely remove duplicated standalone services only after backup, replacement validation and rollback preparation; prepare the downstream on-premise design
- [ ] [ARV-074 / #73](https://github.com/arutyunoveth/ai-corporation/issues/73) — run the isolated Obsidian Mind memory pilot outside production runtime and record an `ADOPT / ADOPT WITH LIMITS / REJECT` decision
- [ ] [ARV-076 / #82](https://github.com/arutyunoveth/ai-corporation/issues/82) — create and validate an independent Docker/Colima backup set with PostgreSQL dump, cold named-volume archives, SHA-256 verification, isolated restore evidence and a tested lost-SSD recovery runbook
- consolidate remaining absolute local links in historical governance/launch docs without rewriting historical decisions
- add richer report export formats if customer demos require them
- define paid-pilot packaging and onboarding constraints after `C6`
- enrich the demo flow with bounded LLM-assisted analysis in `C3`, keeping deterministic fallback available
- evaluate richer schema families and provider abstraction hardening after `C3`, without broad runtime opening
- persist versioned supplier-request draft templates if commercial operators need reusable outbound packs
- add richer quote attachment parsing and validation while keeping manual registration as the safe default
- evaluate status-engine synchronization for commercial workspace actions without forcing unsafe automatic transitions
- [x] confirm that accepted local C1-C6 and CP0 state is published/synced to `origin/main` before external repository review (DP0)
- [x] add a minimal pilot-facing auth/access boundary before broader customer circulation (DP1)
- [x] create bounded partner workspace and safe data intake layer (DP2)
- [x] create safe redaction workflow for real tender materials (DP3)
- [x] create safe partner-facing report export and delivery flow (DP4)
- [x] create structured feedback and outcome loop for design-partner pilots (DP5)
- [x] run end-to-end design-partner pilot dry run (DP6)
- [x] complete paid pilot readiness review (DP7)
- [x] restricted paid pilot operations setup (PP0) — runbook, data policy, templates, checklist, gitignore
- [x] real partner tender folder runner (PP1) — local folder-based pilot command with folder validation, intake, redaction, analysis, export guard, and output generation
- [x] tender operator pilot runner refinement (PP1R) — RFQ-first workflow for tender/operator companies; calibrated contract risk; TKP comparison/economics; no product catalog assumptions
- collect first real design-partner/tender-operator evidence with real operator/customer feedback
- improve customer/export packaging for partner-facing report delivery without opening external execution
