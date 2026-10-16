# Arvectum agent instructions

## Mission

Build and maintain the Arvectum procurement automation platform with small, reviewable, evidence-backed changes. Preserve human control, auditability, deterministic behavior where possible, and the current restricted-pilot boundaries.

## Architecture boundaries

- Keep procurement analysis, Hermes logic, parsers, calculations, reports, and state transitions in FastAPI/Python.
- Treat self-hosted n8n as an external orchestrator for schedules, webhooks, retries, waits, and notifications only.
- n8n and other integrations must use documented internal APIs; they must not write directly to product database tables.
- PostgreSQL is the production datastore. Preserve SQLAlchemy 2 and Alembic conventions.
- LLM-backed behavior must stay bounded, schema-validated, traceable, and human-reviewed.
- Do not add autonomous procurement submission, EDS/signature actions, supplier communication, or other external execution unless the task explicitly authorizes a separately reviewed control boundary.

## Default workflow

1. Restate the requested outcome and identify the smallest affected subsystem.
2. Load only the relevant skill from `.agents/skills`; do not load every skill.
3. Inspect the narrowest useful set of files, symbols, tests, and recent related changes.
4. Write a short implementation plan before editing when more than one file or subsystem is involved.
5. Make the smallest coherent diff. Do not refactor unrelated code.
6. Run targeted lint/tests first, then broaden verification only when the change justifies it.
7. Report changed files, decisions, assumptions, commands run, results, and remaining risks.

## Skill routing

Use the most specific matching skill. Common routes:

- bug or failing test: `bug-investigation`;
- normal implementation: `focused-change`;
- FastAPI route/schema/service: `fastapi-feature`;
- migration/model persistence: `alembic-migration`;
- tender extraction/normalization: `tender-parser-change`;
- ЕИС/ЭТП/SOAP/REST adapter: `external-integration`;
- Hermes/prompt/schema/model behavior: `llm-schema-eval`;
- regression coverage: `regression-test-design`;
- browser journey: `browser-smoke`;
- security analysis: `security-review` or `tender-safety-review`;
- diff/PR assessment: `pr-review`;
- release decision: `release-readiness`.

The full catalog and local setup guidance are in `docs/development/AI_AGENT_TOOLING.md`.

## Verification commands

Prefer the existing environment and lockfile. Typical commands:

```bash
uv sync --extra dev
uv run ruff check <changed-paths>
uv run pytest -q <targeted-test-files-or-nodeids>
uv run pytest -q
```

Use the full test suite for cross-cutting changes, shared models, migrations, routing, security boundaries, or before release. Do not claim a command passed unless it was actually run.

## Data and security rules

- Never commit `.env`, tokens, certificates, private keys, cookies, real tender archives, real partner data, generated pilot exports, or operator logs.
- Use synthetic or explicitly sanitized fixtures in tests and documentation.
- Preserve current `.gitignore` protections.
- Treat authentication, authorization, secrets, file extraction, archive handling, HTML rendering, and external network calls as security-sensitive.
- Require human review for findings that touch authentication, secrets, personal data, EDS, external side effects, or destructive migrations.

## Canonical Arvectum Procurement LLM data capture — mandatory

- Before creating a training corpus/database or processing any real tender, read `docs/roadmap/PROCUREMENT_LLM_STORAGE_POLICY_2026-10-16.md`.
- **One existing Tender Agent store only:** Docker PostgreSQL 17 `arvectum-postgres` / database `arvectum` for canonical structured observations and existing `/Volumes/ArvectumSSD/Arvectum/data/tenders/` for source originals, source hashes, extracted text and protocol files. Reports referenced by existing `tender_analysis_runs.report_path` and existing `data/rag/reports`. Do not create any SQLite, extra PostgreSQL DB, new model-data vault, or duplicate original corpus.
- For every future **manual tender review, real company participation, automated run, result/award protocol, or owner correction**, record or queue a source-linked, immutable observation in this existing store. Key by original procurement number/external ID + edition/hash + run/event ID; preserve actor and status; never infer company participation or legal gold from model text.
- Protect all blind/holdout test sources from train data. No raw private sources or user chat transcripts in Git. A training pipeline/model is **deferred**; the former SQLite proof-of-concept is noncanonical, reconciled 29/29 into `arvectum` and retained solely as a frozen backup. New manual intake uses the guarded existing-PostgreSQL CLI; automated history capture remains opt-in until deployed. If intake cannot write safely, disclose the missing integration instead of claiming automatic capture.
- For **every new substantive manual ChatGPT procurement review** with authorized access to Mac mini, follow `docs/roadmap/PROCUREMENT_LLM_CONTINUOUS_INTAKE_2026-10-16.md`: prepare a redacted source-linked JSON observation (unique stable event ID, owner participation and evidence status), run `python -m scripts.procurement_llm.import_candidates --manual-stdin` for validation and only then `--apply --confirm-database arvectum` when allowed. Never include complete chat transcripts, unlicensed originals, blind gold or secrets. If tools/connectivity are absent, state plainly the review was NOT persisted and leave it queued; this repository does not passively subscribe to ChatGPT chats.
- In deployed app code, the `TENDER_LEARNING_CAPTURE_ENABLED=1` gate covers saved RAG and completed customer_pilot runs only with migration107 installed; do not imply this captures all Tender Agent pipeline paths or chats.
- After initial or recurring manual/automatic intake, use the **read-only** `python -m scripts.procurement_llm.audit_corpus` to check source SHA, linked runs, evidence confidence and `candidate_unreviewed` status. Read the audit gate in `docs/roadmap/PROCUREMENT_LLM_PROVENANCE_AUDIT_2026-10-16.md`; do not infer 44-FZ participation from the mere presence of public EIS original documents. Missing run reports or unsigned bid receipts remain explicit provenance gaps, not reconstructed labels.
- For restored or disputed old full reports and bid participation receipts, follow `docs/roadmap/PROCUREMENT_LLM_SOURCE_RECOVERY_2026-10-16.md` and use the read-only `scripts/procurement_llm/source_recovery.py`. A published EIS protocol may confirm an *application number, admission and bid price*, but it does NOT by itself confirm that the application belongs to Arvectum. Keep `participant_attribution=owner_reported_not_independently_verified` until independently corroborated. Absent full reports must NEVER be regenerated as historic originals; DB previews are not full source receipts. Pending manual events must be explicitly applied to canonical PostgreSQL, never described as already imported.
- Historical MD files found without verifiable saved `tender_analysis_runs.id` must be handled as `legacy_report_artifact` unreviewed **source-only** observations in the same PostgreSQL `arvectum`; see `docs/roadmap/PROCUREMENT_LLM_LEGACY_REPORT_ARTIFACTS_2026-10-16.md`. Never falsify run links. Use `import_candidates --legacy-report-file ... --expected-report-sha256 ...` in dry-run first, then append with explicit same-DB confirmation only when authorized. Do not copy full Markdown into corpus or promote to training/gold.
- ETP company participation evidence from connected corporate email must remain source-bound: use the private `manual-candidate-import-v1` intake, not a public Git raw email dump. RTS/Roseltorg/Sberbank-AST submission confirmations can verify application/participant status; a published EIS protocol confirms app number, price and admission; only **their conjunction** can establish that an admitted numbered application belongs to Arvectum. Record operator withdrawal with *unknown application number* unless an individual receipt proves the link. See `docs/roadmap/PROCUREMENT_LLM_ETP_EMAIL_EVIDENCE_2026-10-16.md`. When controlled DB write is blocked, preserve pending private batch and do NOT claim appended records or circumvent the block.
- The outcome-evidence gate in docs/roadmap/PROCUREMENT_LLM_OFFICIAL_OUTCOMES_2026-10-16.md distinguishes EIS original protocol, ETP company receipt, historical derived stats, and public secondary winner quote. Do not assign Aksioma company bid rank/price based on 119000 RUB winning price, infer Kaluga withdrawn application no. 206 from an unnumbered withdrawal, equate appRating26 to rank26, or invent Museum Bread outcome before 2026-10-20. Run audit_outcomes.py read-only. Never promote gold by inference.
- EIS original-protocol evidence: original getDocsIP final XML SHA checks outrank secondary winner quotes and derived analysis. Aksioma company application 3630084 admitted 399000 RUB appRating6, Aksay 122031738 admitted 119000 RUB appRating38; separately verify company ownership via ETP operator communication. See docs/roadmap/PROCUREMENT_LLM_OFFICIAL_EIS_FINAL_PROTOCOLS_2026-10-16.md. Nine operator metadata events remain PRIVATE/dry-run only, not in PG. Never infer gold, publish original private email, or circumvent blocked writes.
- Post-final EIS epNoticeApplicationCancel concerns its explicit application number only. In Aksay 0158300034526000388, notice published 2026-10-14 11:54 MSK targets application 122034518 (original rating14, 57000 RUB), NOT company application 122031738 (rating38, 119000 RUB) from the 11:26 final. Do not infer entire procurement cancellation, revised rating, our bid rejection or new winner. Use SHA-bound source-only scripts/procurement_llm/audit_eis_chronology.py; see docs/roadmap/PROCUREMENT_LLM_EIS_EVENT_CHRONOLOGY_2026-10-16.md. Do not create training gold labels from the notice.
- Future schema extension must be a reviewed Alembic migration in the existing `arvectum` DB; no production DB mutations without explicit authorization.

## Context and token budget

- Do not read the entire README or large documentation trees by default.
- Start with file names, symbols, imports, targeted grep, and related tests; open only the relevant ranges.
- Prefer concise summaries over pasting large files into the conversation.
- Use current external documentation through a documentation tool/MCP instead of copying whole manuals into prompts.
- Put recurring procedures in skills, subagents, commands, or scripts rather than repeating long prompts.
- Keep unrelated MCP servers disabled.
- Start a fresh task/session when the goal changes materially instead of carrying unrelated history.

## Source-of-truth loading

Load these only when relevant:

- Product scope and non-goals: `docs/product/MVP_v1_Scope.md`, `docs/product/MVP_v1_Non_Goals.md`
- Human-control policy: `docs/product/Human_Control_Policy_v2.md`
- Tender operator workflow: `docs/product/Tender_Operator_Pilot_Runbook.md`, `docs/product/Tender_Operator_RFQ_Workflow.md`
- Launch restrictions and gates: `docs/10_launch/Launch_L1_Restrictions.md`, `docs/10_launch/Launch_L1_Control_Gates.md`
- Canonical module registry: `docs/99_governance/canonical_module_registry_locked.md`

## Code review rules

Review changes for:

- broken human-control or restricted-pilot boundaries;
- direct database writes from external orchestration;
- missing traceability, schema validation, or deterministic fallbacks;
- unsafe archive/file handling, injection, XSS, secret or personal-data exposure;
- migration compatibility and rollback risk;
- behavior changes without focused regression tests;
- duplicated business logic or accidental divergence from canonical modules.

Prioritize concrete defects and regressions over style preferences.