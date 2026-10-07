# BASE-001…BASE-018 revalidation — 2026-10-07

## Scope and rule

This is a current-state reconciliation overlay for the historical 2026-07-30 BASE registry. It does **not** rewrite the historical status, progress, source, dependency or completion fields in `docs/roadmap/master-roadmap.yaml`.

Revalidation base: canonical Tender Agent main after ARV-005 closure, merge commit `ffc698efb02a1c662d92fa46ec65f4f0f0112552`.

Evidence classes used here:
- current repository code, tests and canonical documentation;
- current public `arvectum.com` surface for website/product statements;
- Owner-session official corporate/brand artifacts for BASE-001/002, checked without committing private source documents or sensitive banking/personal data;
- preserved historical release/merge evidence already recorded in the immutable snapshot.

## Result summary

| ID | Revalidation result | Current conclusion |
|---|---|---|
| BASE-001 | confirmed_done | Corporate/legal foundation remains established; current official Owner-session corporate records were checked. |
| BASE-002 | confirmed_done | Brand system remains established and is visibly applied on current public surfaces. |
| BASE-003 | confirmed_done | The live site is now product-first, multilingual and includes privacy/cookie, CTA, human-control and social-channel surfaces. |
| BASE-004 | confirmed_done | FastAPI/SQLAlchemy/Alembic/Docker application foundation remains active and materially expanded. |
| BASE-005 | confirmed_done | Capability remains present, but generic RAG ownership has deliberately moved to Arvectum Data Platform; PostgreSQL remains Tender Agent source-of-truth/domain storage and pgvector-backed platform retrieval is the supported architecture. |
| BASE-006 | confirmed_done | Public 44-FZ discovery and exact-number paths remain implemented and regression-tested. |
| BASE-007 | confirmed_done | SOAP/getDocsIP/getDocsByReestrNumber code and deterministic tests remain valid; a fresh authenticated production smoke on 2026-10-07 completed successfully against EIS and returned an archive URL over the verified direct TLS route. |
| BASE-008 | confirmed_done | Procurement ingestion/analysis/report export is present across current operator and RAG flows. |
| BASE-009 | confirmed_done | Product/requirement extraction remains implemented with source-first and role-aware regression coverage. |
| BASE-010 | confirmed_done | Live/demo boundary and fail-closed/no-silent-synthetic behavior are covered by current transport/output tests. |
| BASE-011 | confirmed_done | The Hermes H1–H4 foundation is implemented and tested: client/fallback, runtime context, category profiles, normalization, quality gates, feedback/memory primitives, eval-case generation, supplier-readiness and bid-decision helpers. The unfinished real-user learning loop is reclassified as post-MVP ARV-004 rather than a BASE prerequisite. |
| BASE-012 | confirmed_done | Quality/provenance/source-graph work has materially exceeded the July baseline; the frozen ARV-005 pilot added 12 unique 44-FZ cases plus three separately scored 223-FZ cases with regression capture and source-bound failure behavior. |
| BASE-013 | confirmed_done | Demo/pilot package is extensive and has been updated with current controlled-pilot, live-walkthrough and ARV-005 technical evidence. |
| BASE-014 | confirmed_done | Historical client/project/search UI foundation is now complemented by customer pilot, partner workspace, workspace feed, procurement UI/wizard, portfolio and tenant-isolation flows. |
| BASE-015 | confirmed_done | Unicode-capable PDF generation and PDF artifact regressions remain in code; final Linux CI is the authoritative platform check for this revalidation head. |
| BASE-016 | confirmed_done | R7 remains preserved as a frozen production-like baseline and later controlled-pilot evidence builds on it rather than rewriting it. |
| BASE-017 | confirmed_done | R8 customer-pilot lifecycle, tenant isolation and artifact binding remain present with current regression coverage. |
| BASE-018 | confirmed_done | R9 fail-closed/idempotency/concurrency/recovery contracts remain present. One local macOS backup/restore acceptance case is environment-sensitive; exact-head Linux CI is required before closure. |

Overall current classification after the BASE-011 product-boundary reconciliation: **18 confirmed_done, 0 BASE residual gaps**. This does not claim an autonomous Hermes production runtime or a self-improving cross-customer loop. That unfinished product capability is explicitly moved to post-MVP roadmap item ARV-004.

## Item evidence

### BASE-001 — corporate foundation

Current Owner-session official registration/tax and banking artifacts were checked and remain consistent with the existence of ООО «Арвектум» and its operating corporate contour. No private document, bank account data, personal identifier or signing material is copied into the public repository.

Result: `confirmed_done`.

### BASE-002 — brand system

The current Owner-session brandbook confirms the Arvectum wordmark/monogram, Mint/Deep Navy/Graphite system, PT Sans hierarchy and JetBrains Mono technical accents. The current public website visibly uses the same system.

Result: `confirmed_done`.

### BASE-003 — website and base digital channels

Current public `arvectum.com` exposes Russian/English navigation, product-first Tender Agent positioning, CTA, privacy/cookie surfaces, explicit human-control language and outbound social/contact channels. This satisfies the historical base item and materially advances the July “rebuild around product and pilot” next result.

Result: `confirmed_done`.

### BASE-004 — backend foundation

Current manifests and runtime entry points retain FastAPI, SQLAlchemy, Alembic and Docker deployment. The module registry now contains the original foundation plus product, workflow, decision, portfolio, mobile and operational modules.

Evidence:
- `pyproject.toml`
- `Dockerfile`
- `deploy/pilot/Dockerfile`
- `src/main.py`
- `src/shared/api/router_registry.py`

Result: `confirmed_done`.

### BASE-005 — PostgreSQL, pgvector and RAG capability

The July implementation shape has intentionally evolved. PostgreSQL remains canonical product/domain storage. `pgvector` migrations and integration tests remain, while generic extraction/chunking/embedding/retrieval ownership has been moved out of Tender Agent into Arvectum Data Platform. Tender Agent now consumes the shared Data Platform SDK and retains only procurement-domain projections/evidence bindings.

Evidence:
- `docs/tender_research/data_platform_boundary.md`
- `migrations/versions/090_enable_pgvector_and_add_rag_tables.py`
- `src/tender_research/rag/data_platform.py`
- `tests/tender_research/test_data_platform_boundary.py`
- `tests/tender_research/test_rag_data_platform.py`

Result: `confirmed_done` as an evolved architecture, not a regression.

### BASE-006 — public 44-FZ and exact-number search

Current public 44-FZ provider, registry discovery and exact-number/operator flows remain in the active code path.

Evidence:
- `src/tender_research/providers/public_44fz_search.py`
- `src/tender_research/registry_discovery.py`
- `tests/tender_research/test_public_44fz_provider.py`
- `tests/test_tender_operator_agent_public_44fz_search.py`

Result: `confirmed_done`.

### BASE-007 — EIS SOAP machine-readable contour

`RealEisLoader` still supports registry-number retrieval through `getDocsByReestrNumber`/getDocsIP semantics and fails closed on missing token, SOAP fault, validation/processing failure and no-data states. Focused SOAP/getDocs tests pass.

Fresh production evidence was obtained on 2026-10-07 after the Owner restored EIS-side PMD access and issued a new individual/extract token. The token value remained local and was neither printed into repository artifacts nor committed. The read-only `getDocsByReestrNumber` smoke for previously validated procurement `0116300036226000029` reached `int.zakupki.gov.ru`, returned `status=completed`, produced one archive URL and no warnings. TLS verification for both `zakupki.gov.ru` and `int.zakupki.gov.ru` passed with hostname verification, macOS system trust and direct proxy-bypassed routing.

Evidence:
- `src/tender_research/eis_real_loader.py`
- `src/modules/tender_operator_agent_demo/zakupki_soap_client.py`
- `tests/tender_research/test_eis_real_loader.py`
- `tests/test_tender_operator_agent_getdocs_ip_client.py`
- `tests/test_tender_operator_agent_zakupki_soap_client.py`
- `tests/test_zakupki_soap_diagnostics.py`
- sanitized Owner-session production smoke, 2026-10-07: `completed`, archive URL present, zero warnings

Result: `confirmed_done`.

### BASE-008 — procurement ingest and reporting

Current operator/RAG flows retain document intake and report generation/export, including PDF. The product has added source-bound and controlled-provider reporting on top of the historical base.

Evidence:
- `src/tender_research/rag/export_service.py`
- `tests/test_tender_operator_agent_report_export.py`
- `tests/tender_research/test_rag_report_export_service.py`
- `tests/production_llm_analysis/test_report_source_binding.py`

Result: `confirmed_done`.

### BASE-009 — positions and characteristics extraction

Current extraction logic is covered by legacy-structured-position, source-first goods extraction and document-role/customer-role regressions. Domain-regression infrastructure further captures confirmed procurement edge cases.

Evidence:
- `tests/test_legacy_word_structured_positions.py`
- `tests/test_pilot_001_d08_1_source_first_goods_extraction.py`
- `tests/test_document_roles.py`
- `docs/testing/domain-regression-v1.md`

Result: `confirmed_done`.

### BASE-010 — demo/live boundary

Current tests preserve explicit live-source behavior, transport policy and live-output boundary; the product does not silently convert unavailable live evidence into synthetic “success”.

Evidence:
- `tests/test_tender_operator_agent_demo_acceptance_smoke.py`
- `tests/test_public_eis_transport_policy.py`
- `tests/production_llm_analysis/test_live_output_boundary.py`

Result: `confirmed_done`.

### BASE-011 — Hermes H1–H4

The historical BASE item is a foundation item: basic memory, quality gates and feedback primitives. That foundation is present and tested. Current code includes the Hermes client with deterministic fallback, runtime context assembly, category profiles, normalization, quality gates, feedback persisted into memory, eval-case creation, supplier-readiness and bid-decision helpers.

The previous residual classification conflated this completed foundation with its historical `next_result`: a production self-improvement loop grounded in real user corrections. Product Owner reconciliation on 2026-10-07 separates those scopes. The real-user learning loop is now the post-MVP successor under existing roadmap item `ARV-004`, documented in `docs/product/Feedback_Learning_Loop.md`, and is not admitted into the current execution queue.

Canonical policy remains unchanged: external Hermes runtime is optional, company-agent execution stays manual/sequential, and Hermes does not become a second autonomous GO / NO GO decision engine.

Evidence:
- `src/modules/hermes_agent/`
- `tests/tender_research/test_hermes_*.py`
- `docs/ops/r0/experiments/HERMES_RECOVERY.md`
- `docs/agents/company/Company_Agent_Runtime_Policy.md`
- `docs/product/Feedback_Learning_Loop.md`

Result: `confirmed_done` for the BASE infrastructure foundation. The post-MVP learning loop remains separate under `ARV-004`.

### BASE-012 — quality, provenance and source graph

Source-graph/provenance contracts and regression tests remain active. Since July, Decision Core/domain regression and the frozen ARV-005 controlled pilot expanded real-procurement evidence beyond the original five-case baseline: 12 unique 44-FZ cases completed technical reporting and three exploratory 223-FZ cases failed closed as source-bound blockers.

Evidence:
- `src/modules/procurement_source_graph/`
- `tests/test_procurement_source_graph_json_roundtrip.py`
- `tests/test_procurement_source_graph_production.py`
- `tests/test_arv067g_provenance.py`
- `docs/pilot/ARV-005_TECHNICAL_PILOT_REPORT_2026-10-03.md`

Result: `confirmed_done`.

### BASE-013 — demo and pilot package

The historical package still exists and is now supplemented by controlled-pilot plans/reviews, restricted-pilot operations guidance, live walkthrough material and the frozen ARV-005 aggregate technical report.

Evidence:
- `docs/demo/`
- `docs/product/Restricted_Paid_Pilot_Operations_Runbook.md`
- `docs/product/Tender_Operator_Pilot_Live_Walkthrough.md`
- `docs/pilot/ARV-005_TECHNICAL_PILOT_REPORT_2026-10-03.md`

Result: `confirmed_done`.

### BASE-014 — base operator workspace

The historical UI foundation has materially evolved: customer registry/pilot, partner workspace, workspace feed, procurement operator UI/wizard and canonical portfolio workflows exist. R8 tenant-isolation tests cover the multi-tenant successor requirement.

Evidence:
- `src/modules/customer_registry/`
- `src/modules/customer_pilot/`
- `src/modules/partner_workspace/`
- `src/modules/workspace_feed/`
- `src/modules/procurement_portfolio/`
- `tests/test_tender_operator_agent_procurement_ui.py`
- `tests/test_tender_operator_pilot_wizard_ui.py`
- `tests/test_partner_workspace_dp2.py`
- `tests/test_r8_acceptance_tenant_stage.py`

Result: `confirmed_done`.

### BASE-015 — Linux PDF rendering

ReportLab-based export still resolves Linux Unicode font candidates first and PDF artifact tests verify valid PDF output, identity and fail-closed behavior. Current exact-head CI is required before final closure to re-establish the Linux execution signal for this change set.

Evidence:
- `src/tender_research/rag/export_service.py`
- `tests/test_tender_operator_agent_report_export.py`
- `tests/test_r8_final_pdf_generation.py`

Result: `confirmed_done`, subject only to the normal exact-head CI gate.

### BASE-016 — R7 controlled-pilot baseline

The R7 historical release remains a frozen baseline. Current repository retains pilot deployment, backup/recovery and later controlled-pilot evidence; the historical R7 snapshot is not rewritten by later improvements.

Evidence:
- historical commit `8bb52591372475dde63dc32260cd2a0c4cf0e422`
- `deploy/pilot/`
- `tests/test_pilot_backup_restore_scripts.py`
- `docs/pilot/ARV-005_TECHNICAL_PILOT_REPORT_2026-10-03.md`

Result: `confirmed_done`.

### BASE-017 — R8 Customer Pilot Workspace

Current customer-pilot code and tests retain isolated customer lifecycle, tenant staging/isolation, immutable artifact binding and PDF publication behavior.

Evidence:
- `src/modules/customer_pilot/`
- `tests/test_r8_customer_pilot.py`
- `tests/test_r8_acceptance_tenant_stage.py`
- `tests/test_r8_artifact_binding.py`
- `tests/test_r8_final_pdf_generation.py`

Result: `confirmed_done`.

### BASE-018 — R9 Operational Hardening

Current R9 regression set retains idempotency, interrupted-publication, orphan-lifecycle, DB/filesystem mismatch, recovery-security and backup/restore contracts. In this revalidation batch all selected R9 tests passed except the known local macOS backup/restore matrix, where the local `pg_restore 18.6` process failed against the disposable `pgvector/pgvector:pg16` acceptance environment. This is recorded as local-environment evidence, not as a silent PASS. Exact-head Linux CI remains the closure authority.

Evidence:
- `tests/test_r9_artifact_idempotency.py`
- `tests/test_r9_backup_restore.py`
- `tests/test_r9_db_filesystem_mismatch.py`
- `tests/test_r9_interrupted_publication_fault_matrix.py`
- `tests/test_r9_orphan_lifecycle.py`
- `tests/test_r9_recovery_security.py`
- `tests/integration/compose.r8-postgres.yml`

Result: `confirmed_done` with explicit local-environment caveat.

## Verification run

Focused BASE revalidation batch on the isolated worktree:

- **545 passed**
- **12 skipped**
- **1 failed**
- failure: `tests/test_r9_backup_restore.py::test_backup_restore_matrix_is_consistent_and_fail_closed`
- local diagnostic: Homebrew `pg_restore 18.6`; disposable acceptance PostgreSQL image is `pgvector/pgvector:pg16`.
- the same R9 local environment failure had already been observed independently during the preceding ARV-005 current-main verification; it is not newly introduced by this documentation-only reconciliation.

No procurement action, ETP write, signing, private-key access, supplier/customer outreach, payment, commitment or production mutation was performed.

## Post-merge BASE-007 production smoke

After PR #188 was merged, the current Mac mini runtime contour was rechecked rather than inferred from repository state.

- TLS trust verification: PASS for `zakupki.gov.ru` and `int.zakupki.gov.ru`; TLSv1.2, hostname verification and direct proxy-bypassed route confirmed.
- EIS credential: current individual/extract token loaded only from the protected local Owner environment; the token value is not stored in this repository.
- Read-only smoke: `getDocsByReestrNumber(0116300036226000029)`.
- Result: `completed`.
- Archive URL: present (1).
- Warnings: 0.
- No ETP write, signing, submission, private-key action or account mutation was performed by Tender Agent.

This closes the current-runtime evidence gap for BASE-007.

## Current closure state

The BASE revalidation is now conceptually complete at the product-boundary level: all 18 BASE items are `confirmed_done`. BASE-011 closure means the tested Hermes infrastructure foundation is complete; it does **not** assert that the post-MVP Feedback & Learning Loop is implemented.

Any future ARV-004 implementation remains separately gated and must preserve the existing human-decision and consequential-action boundaries.
