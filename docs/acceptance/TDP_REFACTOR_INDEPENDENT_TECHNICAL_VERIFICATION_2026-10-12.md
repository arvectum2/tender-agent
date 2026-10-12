# Tender Agent / Data Platform — independent technical refactor verification

Date: 2026-10-12 (Europe/Moscow). Scope: read-only verification of already merged refactor, without a production deployment, procurement transaction, paid reviewer or owner commercial decision.

## Exact code revisions

- Tender Agent `arvectum2/tender-agent` canonical `main`: `a2982cf9c2248b6b2bc9e8f3c8b66e37e0965648`.
- Data Platform `arvectum2/data-platform` canonical `main`: `daa0719da31f989afcf49283ffa295cfb5f2ccac`.
- Data Platform service bounded-context refactor is **already merged** in PR #121, commit `6cfdef7249e3ec62b80b1b921f44c4f57aed9c87`; its `DP-CORE-REFACTOR-20261011` child checkpoint is `completed` on `main` via PR #122. Stale local `refactor/core-architecture` is **not** a merge candidate: 129 main-only commits, 9 branch-only commits and 21 merge conflicts when simulated. No stale merge performed.

## Verified independently on Mac mini

- Tender Agent at the exact above `main`: `make check` PASS; full Python 3.12 pytest **3936 passed, 238 skipped, 0 failed**, duration 149.60 seconds. PostgreSQL 16 CLI selected for compatible R9 restore tests.
- Data Platform at the exact above `main`: CI-scope Ruff `src tests sdk/python/src scripts/audit_modules.py scripts/check_dependency_lock.py` PASS; API/architecture Ruff PASS; full pytest with `PYTHONPATH=src:sdk/python/src` PASS (some integration-only tests skipped). Earlier historical PR #121 exact-head CI includes Python 3.11/3.12/3.13, PostgreSQL, JavaScript SDK and mirror checks.
- Original-source offline SHA recheck: **21/21** private EIS attachment bytes match SHA-256 in `evidence/tdp-r5/ai-expert-20261012/positive-docs-recovery-20261012/official-21-attachments-receipt.json`.
- Official live-card snapshot offline SHA recheck: **20/20** retained official EIS HTML files match their `html_sha256` in `evidence/tdp-r5/ai-expert-20261012/live-eis-cards-20261012/official-live-20-curl-receipt.json`.
- Stored provenance states refer to the snapshot of 2026-10-12, **not a new live legal recheck**. In original snapshot 5 submission-stage cards, 1 commission-stage card, 14 closed-stage cards.
- The independent original-source nonproduction proof (5/5 bytes and 127/127 normalized chunks) was completed earlier with isolated PostgreSQL API and must not be mislabeled as live Data Platform production ingestion.

## Boundary between completed technical refactor and remaining acceptance

**Technical modularization and latest local regression are verified.** This does not certify the entire TDP parent Definition of Done. The canonical parent must remain `blocked` until the remaining gates below have independent evidence:

1. Complete current-version eligibility, legal/third-party software rights, attachments and external-cost economics for the five submission-stage EIS cases; two cases have material unverified third-party code rights. Never infer the company's compliance from model output.
2. Human procurement/legal/commercial gold and dated owner acceptance for 20 authentic competitive cases; current owner signoffs remain **0/20**.
3. Last approved staging EIS -> authenticated Data Platform persisted originals and chunks -> Tender Agent report/API/PDF/DOCX E2E with current revisions and provenance. No live DP production data writes are authorized, and neither unverified unknowns nor model fallback can constitute business GO.
4. Do not send bids, contact parties, execute signatures, deploy production, create paid ChatGPT/OpenAI API use, or restart the disabled Tender Agent watchdog.

Read source-specific evidence in `TDP_RDC_LIVE_OFFICIAL_EIS_20_2026-10-12.md`, `TDP_RDC_FIVE_OPEN_EIS_PREACCEPTANCE_2026-10-12.md`, and `TDP_R5_FOUR_NEW_POSITIVE_ORIGINALS_CHATGPT_AUDIT_2026-10-12.md`. All final procurement decisions remain `DEFER/UNKNOWN` pending actual authorization. This report is verification evidence, not a procurement instruction.
