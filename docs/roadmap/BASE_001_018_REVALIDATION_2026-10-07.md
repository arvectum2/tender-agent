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
| BASE-007 | revalidated_residual_gap | SOAP/getDocsIP/getDocsByReestrNumber code and deterministic tests remain valid; current credential/certificate/host production smoke is an external runtime gate and is not inferred from repository state. |
| BASE-008 | confirmed_done | Procurement ingestion/analysis/report export is present across current operator and RAG flows. |
| BASE-009 | confirmed_done | Product/requirement extraction remains implemented with source-first and role-aware regression coverage. |
| BASE-010 | confirmed_done | Live/demo boundary and fail-closed/no-silent-synthetic behavior are covered by current transport/output tests. |
| BASE-011 | revalidated_residual_gap | Hermes components and focused tests remain, but canonical docs still classify external Hermes/autonomous runtime as opt-in/manual/experimental; a real user-correction production self-improvement loop is not proven. |
| BASE-012 | confirmed_done | Quality/provenance/source-graph work has materially exceeded the July baseline; the frozen ARV-005 pilot added 12 unique 44-FZ cases plus three separately scored 223-FZ cases with regression capture and source-bound failure behavior. |
| BASE-013 | confirmed_done | Demo/pilot package is extensive and has been updated with current controlled-pilot, live-walkthrough and ARV-005 technical evidence. |
| BASE-014 | confirmed_done | Historical client/project/search UI foundation is now complemented by customer pilot, partner workspace, workspace feed, procurement UI/wizard, portfolio and tenant-isolation flows. |
| BASE-015 | confirmed_done | Unicode-capable PDF generation and PDF artifact regressions remain in code; final Linux CI is the authoritative platform check for this revalidation head. |
| BASE-016 | confirmed_done | R7 remains preserved as a frozen production-like baseline and later controlled-pilot evidence builds on it rather than rewriting it. |
| BASE-017 | confirmed_done | R8 customer-pilot lifecycle, tenant isolation and artifact binding remain present with current regression coverage. |
| BASE-018 | confirmed_done | R9 fail-closed/idempotency/concurrency/recovery contracts remain present. One local macOS backup/restore acceptance case is environment-sensitive; exact-head Linux CI is required before closure. |

Overall current classification: **16 confirmed_done, 2 revalidated_residual_gap**. The two gaps are bounded and do not invalidate the historical baseline: BASE-007 is external runtime evidence, BASE-011 is an intentionally unproven autonomous/user-correction loop.

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

`RealEisLoader` still supports registry-number retrieval through `getDocsByReestrNumber`/getDocsIP semantics and fails closed on missing token, SOAP fault, validation/processing failure and no-data states. Focused SOAP/getDocs tests pass. A fresh authenticated production smoke against the current certificate/token/host contour was intentionally not performed by this repository-only revalidation.

Evidence:
- `src/tender_research/eis_real_loader.py`
- `src/modules/tender_operator_agent_demo/zakupki_soap_client.py`
- `tests/tender_research/test_eis_real_loader.py`
- `tests/test_tender_operator_agent_getdocs_ip_client.py`
- `tests/test_tender_operator_agent_zakupki_soap_client.py`
- `tests/test_zakupki_soap_diagnostics.py`

Result: `revalidated_residual_gap` — external runtime smoke/certificate evidence only.

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

Hermes package, category profiles, runtime analysis, supplier-readiness and bid-decision tests remain present. Canonical recovery/runtime policy still says Hermes is opt-in, external Hermes runtime is not required, and company-agent execution remains manual/sequential. Therefore the July next result — a production loop grounded in real user corrections — cannot be claimed complete from current repository evidence.

Evidence:
- `src/modules/hermes_agent/`
- `tests/tender_research/test_hermes_*.py`
- `docs/ops/r0/experiments/HERMES_RECOVERY.md`
- `docs/agents/company/Company_Agent_Runtime_Policy.md`

Result: `revalidated_residual_gap`.

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

## Closure gate

Before this revalidation can be marked completed:
1. update the canonical overlay for BASE-001…018;
2. run repository checks on the changed documentation/roadmap state;
3. obtain exact-head GitHub CI for the revalidation branch;
4. merge only under an applicable Owner/review gate. Automatic merge remains fail-closed while the current AM-4 cycle is review-due.
