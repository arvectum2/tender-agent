# Technical refactor: fresh real-original Data Platform HTTP → Tender Agent → report/export acceptance

**Date:** 2026-10-12, independent Mac mini. **Tender Agent exact code baseline:** `a2982cf9c2248b6b2bc9e8f3c8b66e37e0965648`; **Data Platform exact code baseline:** `daa0719da31f989afcf49283ffa295cfb5f2ccac`. All resources used were offline preserved first-party EIS source files from notice `0372200172326000015`. No new EIS, supplier or customer contact, no bids, no production writes, no external AI API.

## Reproducible acceptance contract

Added `scripts/acceptance/verify_real_eis_report_exports.py`. The script requires an explicit **loopback-only authenticated** Data Platform HTTP endpoint and a private receipt directory, verifies every original binary SHA-256 **before** upload and uses ephemeral Tender Agent ASGI runtime directories. It pins imports to the checkout containing the script (not an editable venv pointing to another local repository). No private documents are added to GitHub. It accepts two distinct modes with incompatible success conditions:

- `--intake-mode official`: five original documents (XLS, DOC, DOCX, DOCX, PDF), Data Platform v1 `POST /v1/process/document` for each, Tender Agent create/analyze/report HTTP 200, **5/5** resource/document source identities and **127/127** cited chunks. Both official-EIS exports return **409** and explain the archived/current-notice mismatch. This is a **PASS of fail-closed protection**, not a broken file renderer or a legitimate EIS participation document.
- `--intake-mode manual`: same five original files with **no official live-source attestation claim**, through authenticated local Data Platform and Tender Agent create/analyze/report HTTP 200, **5/5** provenance identities and **127/127** cited chunks. **DOCX HTTP 200 (37,833 bytes)** and **PDF HTTP 200 (40,844 bytes)**. DOCX package ZIP CRC and `word/document.xml` verified; PDF begins with `%PDF-` and has `%%EOF`. The recommendation remains `manual_review_required`, not GO.

The isolated Data Platform returned `/health` 200, unauthenticated `/v1/collections` **401**, authenticated `/v1/contract` **200 / 1.0**. Both temporary HTTP tests were carried out on the same isolated localhost port, using Data Platform hashing embedding, without external models. Private receipts: `evidence/tdp-r2/0372200172326000015-20261011/ta-dp-e2e-archived-guard-fresh-20261012.json` and `ta-dp-e2e-manual-export-fresh-20261012.json`. This check uses the DP pure process endpoint, **not** a durable PostgreSQL write.

## Durable storage proof — separate evidence, not a single transaction

Previously independently verified nonproduction PostgreSQL+pgvector API stage retained five actual original binary SHA receipts, five resource IDs, five document IDs, **127/127** chunk SHA checks and normalized offsets. See `evidence/tdp-r2/0372200172326000015-20261011/isolated-postgres-api-e2e.json` and `isolated-postgres-rdc-restored-20261012.json`. The staging database was disposable and **was not the live Data Platform instance**. We explicitly do **not** claim that the *fresh* HTTP/export and the separate persisted PostgreSQL replay were one continuous persisted run.

## Definition-of-Done status

Completed: code refactor merged in DP PR #121/#122, TA and DP regressions, the source-locked HTTP/quote provenance path, PDF/DOCX rendering, guarded archived-EIS refusal, prior isolated PostgreSQL persistence acceptance. No identified technical export defect remains in this bounded acceptance.

Not completed and never inferred from model output: real-time latest official EIS revision within the exported run; legal bidder eligibility and rights to third-party software; economics and 20/20 human-labeled final legal/commercial review; owner signature (currently 0/20); **one physically continuous current-revision** EIS → approved staging PostgreSQL → report/PDF/DOCX business-accepted transaction. Parent TDP remains `blocked`, though the technical refactor and the bounded acceptance tests described here are **complete**. Do not enable the watchdog, submit bids or deploy production based on this document.
