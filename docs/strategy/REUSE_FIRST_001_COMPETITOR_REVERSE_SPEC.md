# REUSE-FIRST-001 — competitor reverse-spec and reuse registry

Status: review-ready evidence packet
Date: 2026-09-15
Canonical source: `.agent/execution-queue.yaml` / `REUSE-FIRST-001`
Strategy: `COPY_PATTERN`

## 1. Guardrails

This document records public product patterns and bounded reuse decisions. It does not copy proprietary source code, assets, private data, datasets, or product text. Presence here does not admit new roadmap work, create an ARV mapping, approve a dependency, or widen procurement/external-action authority.

A public product capability is evidence for a workflow pattern, not evidence that its implementation, ranking, scoring, data, or wording may be copied. Material dependencies remain subject to the applicable repository, security, legal/license, sovereignty, and Owner gates.

## 2. Competitor reverse-spec

Public evidence was checked on 2026-09-15. `Unknown` means the capability was not established from the public surface inspected and is deliberately not inferred.

| Product | Search / results | Tender card / documents | Analysis / decision support | Workflow / next action | Reuse decision | Boundary |
|---|---|---|---|---|---|---|
| Seldon 1.7 / Seldon.Pro | Multi-source procurement monitoring and criteria-based search | Aggregated procurement/document surfaces | Customer/supplier/competitor and market/risk analytics are public product themes | Monitoring, reporting and integration surfaces | `COPY_PATTERN` dense filter/result workflow; `ADAPT` replaceable external entity/risk data | Do not reproduce proprietary ranking/scoring or private data; source-bound Tender Agent decision logic remains custom |
| Tenderplan | Precise saved search/feed; keyword, region, OKPD2 and expert filters; search inside documentation/archives | Inline document viewing, comments, download/export | Customer/competitor and market analytics | Saved searches, online notifications, folders/tasks/team work, change tracking | `COPY_PATTERN` saved-search -> feed -> docs -> team task/notification | Do not clone a CRM; reuse generic task/calendar primitives where needed |
| Контур.Закупки | 44-FZ/223-FZ/615-PP/commercial search, templates and broad ETP coverage | Documentation and FAS context in one window | Customer/competitor analytics, arbitration/FAS and market signals | Favorites/lists, comments/statuses, alerts, team work, export/API | `COPY_PATTERN` one-window tender + docs + risk context + alerts; `ADAPT` external risk/company sources | Legal/risk conclusions in Tender Agent remain cited and fail-closed, not opaque scores |
| TenderGuru | Aggregated search with structured filters; API search/card endpoints | Tender cards, recognized procurement documents, related results/contracts | Public API exposes AI document-analysis/report surfaces plus counterparty/FAS/arbitration data | Daily mailings, API, CRM/BI integration, MCP surface | `ADAPT` API/MCP conventions and commodity data plumbing where licensing/terms fit; `COPY_PATTERN` search/card/docs flow | Public SaaS use requires separate data-license terms; do not assume right to republish TenderGuru data |
| РосТендер | Keyword/customer/region/OKPD2/KTRU/exact-number and advanced search patterns | Tender/source metadata and documentation links | Market/customer context appears in paid/public product surfaces | Saved search/templates, alert and API patterns | `COPY_PATTERN` simple entry + advanced filters + saved templates | Tender Agent should not compete on manual tender-support services; no dependency is approved by this row |
| Синапс.ПРО | Government/commercial procurement discovery with saved settings | Tender monitoring/favorites | Prices, demand, competition, company links/financial and participation/win statistics are public themes | Change notifications and monitoring | `COPY_PATTERN` saved search + favorites + competitive context; `ADAPT` authoritative company data | Do not build a generic company-information database |
| Закупки 360 | Search by title/item/lot, region/sector/platform/customer/OKPD2 is part of the public product pattern | Aggregated procurement flow | Analytics/forecast are public product themes | Task-planner/notification pattern | `COPY_PATTERN` lightweight tender-attached task planner | Keep workflow thin; no CRM clone or hidden external action |
| Bidzaar | Commercial-procurement marketplace/discovery rather than classic state-tender aggregator | Structured requests, requirements and supplier proposal documents | Supplier relevance, non-price criteria, competitive-list/proposal comparison | Request -> supplier discovery/invitation -> proposals -> comparison -> winner/next step | `COPY_PATTERN` Supplier -> RFQ -> structured comparison handoff; `ADAPT` supplier-discovery sources | Under current authority Tender Agent must not autonomously invite suppliers, send RFQs, choose a winner, or create commercial effects |
| B2B-Center | Commercial procurement/search ecosystem | Procedure/document workspace | Supplier/customer/SRM analytics are public product themes | Web-service integration, supplier workflows, procurement procedures | `COPY_PATTERN` integration-friendly commercial-procurement flow; `ADAPT` external ETP connectors | Participation/submission/signing remains HUMAN; Decision Core must stay decoupled from any one ETP |

### Public source register

The following public/first-party surfaces were used as product-pattern evidence. They are references, not copied implementation sources.

- Seldon: `https://seldon.pro/`, `https://seldon.pro/download/`
- Tenderplan: `https://tenderplan.ru/search`, `https://tenderplan.ru/company`
- Контур.Закупки: `https://zakupki.kontur.ru/site/tender-government`, `https://zakupki.kontur-f.ru/`
- TenderGuru: `https://www.tenderguru.ru/api`, `https://www.tenderguru.ru/api/documentation/tendery`, `https://www.tenderguru.ru/api/documentation/ai`, `https://www.tenderguru.ru/api/mcp`
- РосТендер: `https://rostender.info/`
- Синапс.ПРО: `https://synapsenet.ru/`
- Закупки 360: `https://zakupki360.ru/`
- Bidzaar: `https://bidzaar.com/for-purchasers`, `https://bidzaar.com/blog/rfp-how-to-request`
- B2B-Center: `https://www.b2b-center.ru/`, `https://www.b2b-center.ru/modul_srm/`

## 3. Reverse-spec: baseline journey versus moat

Across the public surfaces above, the recurring baseline is:

`search/saved query -> result list -> tender card -> source documents -> customer/competitor context -> favorite/task -> notification/export/API`.

This baseline is commodity. Tender Agent should reach parity through the shortest lawful `REUSE`, `COPY_PATTERN`, or `ADAPT` path and should not spend moat engineering on bespoke search infrastructure, document rendering, notification plumbing, generic company cards, generic analytics dashboards, generic CRM, or generic RAG/chat.

The differentiated Tender Agent journey is:

`canonical tender facts -> document/page/fragment evidence -> hard blockers -> GO / NO-GO / NEEDS REVIEW -> commercial feasibility -> next human-controlled action`.

The Decision/Commercial Core is the justified custom boundary. Technical access or automation must not convert a human-controlled next action into an external procurement/commercial effect.

## 4. Reusable component / API registry

This is an evaluation registry, not a dependency approval list. `Candidate` means it may be used or piloted only after normal dependency/security review. `Pattern only` means use the public interface/data-model idea without adopting the component/service.

| Candidate | Capability | License / terms observed | Maintenance / risk note | Decision for Tender Agent |
|---|---|---|---|---|
| Mozilla PDF.js | Browser PDF rendering/viewing | Apache-2.0 | Mature/high-adoption upstream; still pin versions and review supply chain | `REUSE candidate` for viewer; never build a custom PDF renderer without a measured gap |
| pypdf | Python PDF read/write/text primitives | BSD-3-Clause | Mature commodity parser; not a full renderer/OCR system | `REUSE candidate` for narrow PDF primitives where current stack does not already cover them |
| Apache Tika | Multi-format text/metadata extraction | Apache-2.0 | Mature Apache project; JVM/service footprint must be justified before introduction | `ADAPT candidate`; use only if it closes a measured format gap cheaper than existing parsers |
| Tesseract OCR | OCR engine | Apache-2.0; Leptonica dependency has its own permissive license | Mature; OCR quality is document/language dependent; dependency/SBOM review still required | `REUSE candidate`; do not invent an OCR engine |
| OCRmyPDF | Searchable-PDF/OCR pipeline | MPL-2.0 core; source-level modifications to MPL files must remain available under MPL; transitive/external components have separate licenses | Active project; license and external-program dependency stack require explicit review | `Conditional candidate`; prefer unmodified/process-bound use; no adoption from this task alone |
| openpyxl | XLSX/XLSM read/write | MIT (with separately noted bundled/backport licensing) | Mature commodity spreadsheet library | `REUSE candidate` for ARV-016 import plumbing; custom work begins at normalization/commercial semantics |
| pgvector | Vector similarity inside PostgreSQL | PostgreSQL-style permissive license | Mature but adds DB/index operational choices; not required merely because RAG exists | `Conditional REUSE`; use only behind measured retrieval need; no custom vector database |
| Open Contracting Data Standard (OCDS) | Open procurement data-model/schema pattern | Schema Apache-2.0; documentation CC BY 4.0 where stated | International standard, but Russian EIS semantics are not equivalent | `ADAPT / pattern only`; useful normalization reference, not a drop-in Russian procurement model |
| `atomno-mcp-zakupki` | MCP tools for Russian procurement search/card/customer/OKPD2 | MIT repository; underlying provider/hosted-service terms are separate | Very young/small upstream; search/get may depend on third-party or hosted providers; production security/availability/terms not established here | `Pattern/pilot candidate only`; useful reference for MCP/tool normalization, not an approved production dependency |
| TenderGuru API/MCP | Procurement search/card/docs/AI/organization APIs | Commercial service terms; public API page explicitly distinguishes API quotas and separate licensing for public-service data use | External paid/vendor dependency and data-license boundary | `ADAPT candidate only after commercial/legal approval`; no new spend authorized by REUSE-FIRST-001 |

### License/legal decision rules

1. Permissive license does not equal automatic adoption: security, maintenance, sovereignty, SBOM and existing-stack fit still matter.
2. Copyleft/file-level obligations must be reviewed before distribution or modification; do not bury them inside a proprietary deliverable by assumption.
3. A public API/MCP endpoint does not imply redistribution rights. Provider terms, data-source terms, rate limits, paid commitments and personal/commercial data boundaries remain independent gates.
4. No component in this registry creates incremental paid authority. Paid SaaS/API adoption is outside the current zero-new-spend AM-4 envelope.
5. Prefer existing project dependencies before adding a new component that duplicates current capability.

## 5. Active P0/P1 classification

The active accelerated-plan workstreams are classified below. Composite workstreams use more than one delivery strategy only where their commodity and moat layers are explicitly separated.

| Active workstream | Priority | Commodity layer | Moat/custom layer | Canonical delivery decision |
|---|---|---|---|---|
| Stage 0 — competitive reverse-spec and reuse registry | P0 | Public competitor patterns and OSS/API research | None | `COPY_PATTERN`; this task defines what not to invent |
| Stage 1 — thin commodity shell | P0 | Search/filter/saved views, tender card, viewer/parsing adapters, auth/roles, alerts/export | Procurement-specific relevance only after benchmark evidence | `REUSE + COPY_PATTERN + ADAPT`; **no INVENT by default** |
| Stage 2 — Decision Core v1 | P0 | Retrieval, extraction, UI/evidence primitives | Canonical facts, source-bound evidence, hard blockers, deterministic rules, GO/NO-GO/NEEDS REVIEW, confidence/unknown | `INVENT` only for the procurement decision layer; reuse/adapt foundations |
| Stage 3 — Commercial Core | P0 | File import/parsing, supplier-source connectors, generic matching primitives | Nomenclature semantics, tender-to-catalog compatibility/substitution, landed cost/margin/bid economics | `ADAPT` commodity plumbing + narrow `INVENT` commercial decision logic |
| Stage 4 — automation and integrations | P1 | APIs/webhooks, email/CRM/source connectors, saved-search alerts, scheduled reporting | Procurement-specific trigger/routing policy where evidence shows value | `ADAPT + REUSE + COPY_PATTERN`; no bespoke integration platform absent measured gap |
| Stage 5 — reliability and moat | P1 | Security/compliance tooling, observability, standard test/CI infrastructure | 44-FZ/223-FZ/private-procurement edge-case corpus, decision/outcome evaluation and source-bound regressions | `REUSE` infrastructure + narrow `INVENT` domain regression/evaluation layer |

### Current roadmap/queue overlay classifications

These existing canonical classifications are retained and bounded by the workstream split above:

- `REUSE-FIRST-001` — `COPY_PATTERN`.
- `DOCUMENT-QA-005` — `INVENT`, completed; procurement-specific source-bound role/entity precedence and regression evidence only.
- `ARV-018` — `INVENT`, Decision Core.
- `ARV-020` — `INVENT`, procurement-specific application-readiness/hard-blocker rules.
- `ARV-061` — `ADAPT`, generic retrieval/extraction reused; custom boundary is cited procurement reasoning/decision mapping.
- `ARV-065` — `ADAPT`, generic chat/Q&A/RAG reused; no generic chatbot product.
- `ARV-016` — `ADAPT`, commodity XLSX/CSV/PDF import reused; custom boundary starts at nomenclature normalization.
- `ARV-017` — `INVENT`, tender-to-catalog compatibility/substitution semantics above generic matching primitives.
- `ARV-023` — `ADAPT`, supplier sources/connectors reused; own only procurement ranking/qualification and human-controlled handoff.
- `ARV-019` — `COPY_PATTERN`.
- `ARV-021` — `ADAPT`.
- `ARV-022` — `REUSE`.
- `ARV-056` — `COPY_PATTERN`.
- `ARV-063` — `ADAPT`.
- `ARV-047`, `ARV-048`, `ARV-049` — `REUSE`.
- `BUILD-DOCKER-CONTEXT-001` — `ADAPT`; restore deterministic clean-checkout build without inventing infrastructure.
- `DISCOVERY-QA-001` — `ADAPT`, but remains `REVIEW`/blocked; reuse standard retrieval/index components and tune only after benchmark evidence.
- `DOCUMENT-QA-NEXT-INCREMENT` — potential `INVENT`, but remains deferred `REVIEW`; only a measured reusable procurement-specific failure family may be promoted.

## 6. INVENT justification ledger

Every current `INVENT` classification is required to pass the reuse gate below. Generic primitives stay reusable underneath even when the narrow domain layer is custom.

| Custom item | Reuse check | Measured/documented gap | Differentiation | Maintenance justification |
|---|---|---|---|---|
| `DOCUMENT-QA-005` | Generic document parsers/OCR/entity extraction are reusable | Blind procurement-document cases exposed role/identity precedence failures that generic extraction alone did not resolve | Source-bound customer/role identity and evidence integrity | Narrow regression-backed rules protect all downstream decision evidence; task is completed, not an excuse for generic parser ownership |
| `ARV-018` Decision Core | Generic RAG, rules-engine and workflow primitives can be reused | Commodity analytics/summaries do not satisfy canonical source-bound hard blockers and explicit unknown/confidence semantics | Auditable GO/NO-GO/NEEDS REVIEW with cited evidence | This is the core product decision moat; maintenance is constrained by regression evidence and procurement rules |
| `ARV-020` application readiness | Generic checklist/task UI can be copied/reused | Readiness depends on procurement-specific mandatory documents, hard blockers and evidence, not a generic checklist | Decision-ready application state rather than task completion state | Maintain only the procurement rule layer; reuse UI/workflow plumbing |
| `ARV-017` catalog matching/substitution | Generic fuzzy/vector/search matching can be reused | Product equivalence, compatibility and substitution require domain/nomenclature constraints and auditable rationale | Commercial feasibility and defensible substitute selection | Maintain only normalization/compatibility/substitution rules that affect bid economics; generic matching stays replaceable |
| Stage-5 procurement regression/evaluation layer | Standard CI/test/observability/security tooling is reusable | Generic reliability tooling does not encode 44-FZ/223-FZ/private-procurement edge cases or decision correctness | Accumulated domain regression depth and outcome evidence | Each custom case must originate from a confirmed real failure/edge case; no speculative test-framework invention |

No evidence supports building a custom OCR engine, PDF renderer, vector database/search infrastructure, authentication framework, generic chatbot/RAG shell, notification service, analytics platform, CRM clone, or premature distributed infrastructure. Those are explicitly de-scoped unless a later measured gap is canonically approved.

## 7. Bounded roadmap recommendations

1. Freeze new commodity-surface invention until the thin shell has an end-to-end usable flow and a measured gap proves reuse/adaptation insufficient.
2. Treat viewer/OCR/parsing/auth/alerts/analytics/tooling as replaceable infrastructure. Prefer current dependencies first; if missing, evaluate the registry above rather than building equivalents.
3. Keep public/paid procurement APIs behind adapters so no vendor becomes part of Decision Core semantics.
4. Put custom engineering budget into source-bound procurement facts, evidence, blockers, decision logic, commercial matching/substitution and regression depth.
5. Preserve HUMAN/REVIEW gates for submissions, RFQs/invitations, winner/participation decisions, signing and any other external procurement/commercial effect.
6. At each milestone boundary refresh the competitor reverse-spec before widening commodity scope; a new parity feature must identify a proven public pattern or document why none fits.

## 8. Done-gate assessment

- 9 direct procurement/tender products benchmarked across the required journey using public evidence: **PASS**.
- Repository-owned reusable component/API registry with license/legal/risk and de-scope fields: **PASS**.
- Active P0/P1 accelerated-plan workstreams classified as `REUSE/COPY_PATTERN/ADAPT/INVENT`: **PASS**.
- Every active `INVENT` boundary has reuse check, gap, differentiation and maintenance justification: **PASS**.
- Duplicate commodity builds explicitly de-scoped: **PASS**.
- No proprietary code/assets/text/private data copied and no external-action authority widened: **PASS**.

Technical completion of this packet does not approve a dependency, paid service, release, deployment, procurement submission, supplier/customer communication, or product-scope expansion.
