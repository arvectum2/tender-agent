# Implementation Plan: Power Quality evidence closure

**Specification**: `spec.md`
**Date / source baseline**: 2026-10-28, `origin/main` commit `36181694` (recheck before merge).
**Task class**: product_specific; governed engineering methodology adapter.
**Constitution**: Arvectum OS 1.2.0, Ratified. Relevant Accepted RFC-0001/0004/0005/0006/0007/0008 v1.0.0 checked; no new platform capability, shared contract or constitutional amendment.
**Corporate process**: AES-001 0.1.0 Bootstrap; existing Tender Agent S0–S11 research protocol. No replacement/second standard.

## Technical context
- Python 3.12/3.11-compatible source, existing pytest + Ruff. Tender Agent domain code `src/modules/market_intelligence/`.
- Research input: the existing `v29` materialization, verified official EIS receipts, commercial ETP primary HTML, commission and public contract-register original XML hashes. **Never** commit confidential original bytes or fresh generated live reports.
- Canonical runtime/provenance: existing Tender Agent PostgreSQL `arvectum` and `/Volumes/ArvectumSSD/Arvectum/data/tenders/`, plus authorized existing temporary PQ runtime. Source acquisition/extraction/index stays within Data Platform responsibilities.
- Existing primary checkpoint: `.agent/checkpoints/TA-MI-AUTONOMY-20261027.yaml`; do not mutate this checkpoint or `.agent/current-task.yaml` in the pilot branch. Watchdog remains one hourly automation.
- Implementation branch/worktree intentionally isolated from dirty main checkout and Watchdog's active runtime.

## Execution phases

**Phase A — SDD / process bootstrap.** Install `.specify/` scaffold using Spec Kit v1.2.4 `none`. Replace generated constitution placeholder with explicit non-authoritative AES/Company/Arvectum OS/product references. Link the workflow guide in existing MI documentation. No new authority, execution service, DB or agent.

**Architectural cross-review / CI blocker closure:** `src/modules/market_intelligence/pq_dp_ingest.py` had a pre-existing private Data Platform source import that violates the strict consumer boundary. Replace it with `src.shared.document_processing.process_document_bytes`, the existing versioned Data Platform SDK facade. Keep legacy `dp_source` argument (ignored) for ABI compatibility with existing research runners, preserve source SHA/field names/native PDF fallback/OCR, and return explicit per-document extraction errors on unavailable credentials. Verify using offline fake-SDK regression and one synthetic, nonpersisting live `/v1/process/document` request with **existing** operator credentials; never commit or log the credential. Do not create new DP stores or disable the architecture audit.

**Phase B — US1 verified reporter fix.** Remove hardcoded `101` and `69` from warning messages in `pq_verified_market_report.summarize`. Derive warnings from the same count values as the structured JSON. Preserve every safety limitation and public figure category. Add unit tests for 3/2/1 and 101/33/68 cases and check integrity of source-derived report semantics. No network or runtime mutation required.

**Phase C — US2 market evidence closure.** Existing implementation only: use the MI-013 source/review queue to acquire first-party ETP protocols, verify signed contract/registry outcomes and names, differentiate product supply vs service/design/adjacent EPC, dedup projects and track coverage. Use real immutable SHA, exact quote + location, and source tier; do not imply that committee awards prove executed contracts. More extensive work remains OPEN pending actual source access.

**Phase D — US3 durable QA and publication.** Run targeted tests, source audit and existing S0–S11 quality gates. Publish an evidence/coverage-limited report if exhaustive verification is not possible; unresolved fields remain `unknown`. Update canonical roadmap and checkpoint only after actual accepted integration under existing controls.

## Verification / rollback / risks
- AES QA **L1**: Spec Kit integration status, `git diff --check`, Ruff for changed Python; **L2**: unit regression of counts; **L3**: existing PQ source/reporter integration tests; **L4**: CI/PR/merge (must not be claimed without evidence). Real EIS/ETP data quality is a separate **L6** external integration activity, not proven by unit tests.
- Restore by reverting the isolated feature commit; the active product branch, Watchdog, source bytes and databases are untouched.
- Risk: watchdog changes `origin/main` concurrently — rebase/merge review before integration, no force pushes or automatic production modifications.
- Risk: classified source absence as zero sales — fail explicitly, no extrapolation.
- Risk: misattributed suppliers/bid totals — preserve `source_tier`, price-kind and signed-contract distinctions.
- Status is `In progress` until all S0–S11/evidence, independent reviews and canonical closure gates pass.
