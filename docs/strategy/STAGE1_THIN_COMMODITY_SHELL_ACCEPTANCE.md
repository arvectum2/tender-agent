# Stage 1 — Thin Commodity Shell Acceptance

Status: **accepted**
Date: 2026-10-07
Strategic stage: accelerated_plan / stage 1 / thin_commodity_shell
Delivery strategy: REUSE + COPY_PATTERN + ADAPT

## Exit gate

Stage 1 is complete when the commodity shell is usable end-to-end and no commodity item has become a custom multi-sprint build without an approved gap.

The accepted baseline journey is:

authenticated operator -> search/filter or versioned saved profile -> result/tender card -> source document download/parsing adapter -> watch/alert feed -> report/export

This is intentionally a thin shell. Decision Core and Commercial Core remain the differentiated custom layers.

## Acceptance matrix

| Capability | Existing implementation | Acceptance evidence | Strategy / boundary |
|---|---|---|---|
| Search + filters | Tender Operator search UI/API: demo/local deterministic search plus public 44-FZ search; DTR profiles carry law/query/date/NMCK/keyword filters | tests/test_stage1_thin_commodity_shell.py; tests/test_tender_operator_agent_demo_acceptance_smoke.py; tests/test_tender_operator_agent_public_44fz_search.py | COPY_PATTERN + ADAPT; no custom generic search engine |
| Saved views / saved filters | Versioned DailyTenderProfile files under config/daily_tender_profiles/; monitoring watch persists saved_search metadata | Stage 1 shell test loads arvectum-it profile and persists profile/version/query into a watch | COPY_PATTERN; config-backed baseline is sufficient for internal MVP; no generic saved-view platform |
| Tender card | Server-rendered Commercial Operator Console deal card and supporting report/requirements/risks/decision views | Stage 1 shell test creates a bounded stub pre-bid deal and renders /commercial-console/deals/{deal_id}; tests/test_commercial_operator_console_c4.py covers full view set | COPY_PATTERN; no CRM clone |
| Document viewing / download | Tender Operator report UI exposes document list/download; run file download routes return source artifacts | tests/test_tender_operator_agent_upload_demo.py proves report page + per-file download | Reuse ordinary browser/download behavior; no custom document viewer required for the baseline |
| Document parsing adapter | tender_connectors.text_extraction delegates bytes to shared Data Platform process_document_bytes with a quality gate | Stage 1 shell test extracts a UTF-8 specification through the real adapter; tests/test_tender_connectors_text_extraction.py covers adapter and quality-gate behavior | ADAPT/REUSE; no custom OCR/PDF engine |
| Auth | Existing pilot Basic Auth middleware protects /api, /demo, /pilot, /customers, docs/openapi and readiness when enabled; rejects placeholders and adds no-store/security headers | Stage 1 shell auth test plus tests/test_r0_security_boundary.py | REUSE FastAPI/Starlette middleware primitives; not a custom auth framework |
| Roles / visibility | pilot_access_boundary defines actor categories and export/view visibility rules | Stage 1 shell test proves partner-visible allowed and internal-only denied; tests/test_pilot_access_boundary_dp1.py covers the matrix | Bounded product access policy; full multi-tenant IAM remains ARV-043, outside Stage 1 |
| Alerts | procurement_monitoring persists watches, deterministic source snapshots/diffs and internal feed events | Stage 1 shell test persists a saved-search watch; tests/test_procurement_monitoring.py covers idempotent change-alert generation | ADAPT; no bespoke notification platform |
| Export | Tender Operator report download plus per-run DOCX/PDF export routes; partner/export guards exist separately | Stage 1 shell test verifies attachment export; existing Tender Operator tests cover DOCX/PDF links and report downloads | REUSE/ADAPT; no custom office/PDF platform |
| End-to-end shell | All above components are installed in the same FastAPI application and share canonical Deal/document/event models | tests/test_stage1_thin_commodity_shell.py is the explicit Stage 1 acceptance smoke | No new parallel data model or commodity subsystem |

## Gap audit

No Stage 1 exit-gate gap requires a new commodity subsystem.

The following are deliberately **not** Stage 1 blockers:

- end-user CRUD for arbitrary saved dashboards: the current internal MVP has versioned saved-filter profiles plus persisted watch metadata;
- full enterprise IAM/SSO/multi-tenant administration: ARV-043 scope, not thin-shell baseline;
- inline PDF.js-style viewer: source-file download plus shared parsing is usable at baseline; add a viewer only after a measured usability gap;
- OCR engine ownership: ARV-022 stays replaceable/reuse-first;
- external email/SMS/Telegram delivery: Stage 4 keeps delivery separately gated;
- generic CRM, generic analytics platform or generic notification service.

## Reuse / custom boundary

Stage 1 owns no procurement moat. It composes existing primitives and proven public workflow patterns.

Custom multi-sprint engineering remains justified only above the shell, principally in:

- source-bound procurement facts/evidence;
- GO / NO-GO / NEEDS REVIEW rules;
- commercial matching/substitution/economics;
- Russian procurement edge-case regression depth.

No Stage 1 acceptance evidence authorizes external procurement action, signing, payments, supplier/customer communication or autonomous bid decisions.

## Verification command

uv run pytest -q \
  tests/test_stage1_thin_commodity_shell.py \
  tests/test_r0_security_boundary.py \
  tests/test_pilot_access_boundary_dp1.py \
  tests/test_procurement_monitoring.py \
  tests/test_tender_connectors_text_extraction.py \
  tests/test_commercial_operator_console_c4.py \
  tests/test_tender_operator_agent_demo_acceptance_smoke.py \
  tests/test_tender_operator_agent_demo.py

Stage 1 may be marked done only after this focused gate and repository CI pass.
