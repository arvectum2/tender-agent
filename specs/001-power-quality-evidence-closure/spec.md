# Feature Specification: Power Quality evidence closure and trustworthy market report

**Feature Branch**: `feature/spec-kit-pq-audit-20261028`
**Created**: 2026-10-28
**Status**: In progress — bounded engineering pilot, NOT a market study completion
**Canonical action**: existing `TA-MI-AUTONOMY-20261027` checkpoint, not a second roadmap
**Study window**: 2024-01-01 to 2026-10-28; Russia, PQ demand including 6–35 kV, with adjacent voltage/scope reported separately.

## User scenarios and acceptance

### US1 (P0) — Evidence-accurate intermediate report
As the market researcher I need every stated count in the partial PQ report to agree with the source-validated calculation, so that a changing corpus cannot leave stale warnings.

- **AC1:** `v29_candidate_leads = source_number_223_leads + non_223_or_nonstandard_leads`; output narrative warning counts are derived from these values, not manually entered constants.
- **AC2:** Counterexample regression: a corpus of 3 leads with 2 distinct 11-digit EIS numbers generates warnings about 3 candidates and 1 non-223/nonstandard lead, never 101/69.
- **AC3:** In the historical 101-row v29 corpus, 34 223-FZ candidate-lot rows represent 33 distinct notices (32616474682 has two lots), leaving **67** non-223/commercial candidate rows. The report and coverage ledger must agree; a separate synthetic 101/33/68 test case may be retained as a regression fixture. Keep `completeness=partial_do_not_extrapolate`.
- **AC4:** SHA integrity and numeric distinction regression tests remain passing. Bids, NMCK, public register prices and signed contract amounts are never conflated.

### US2 (P0) — Research completion with primary records
As the business owner I need a reproducible 2024–2026 procurement register, with supplier and price assertions linked to original source evidence.

- **AC5:** Per-period + per-source discovery/coverage ledger; ЕИС 44/223 and named commercial ETP sources with query provenance and honest source unavailability.
- **AC6:** For each relevant notice/lot, link original technical specification, final protocol and public contract registry or signed evidence where legally available. Price fields `nmck`, `winning_offer`, `registry_price`, `signed_contract`, `pq_component` separately; mark unknown explicitly.
- **AC7:** Deduplicate notices / lots / repeated procurements / projects / contracts with reviewable merge/split evidence.
- **AC8:** Buyers, verified participants, EPC, designers, suppliers and OEM roles are evidence-attributed; no automatic inference that a commission member is the signed supplier or OEM.
- **AC9:** For mixed EPC, isolate PQ component only when technical bills or trustworthy price allocation exist; otherwise omit from PQ equipment total.
- **AC10:** Produce source-linked registers and `report.md`, `coverage.json`, `quality_report.json`; do not claim census or estimate national TAM from discovered examples.

### US3 (P1) — Reliable continuation
As the operator I need ChatGPT → ARC to resume already-reviewed investigations without repeating downloads or creating new stores.

- **AC11:** Reuse `.agent/checkpoints/TA-MI-AUTONOMY-20261027.yaml`, source hash ledger, current lease and existing canonical corpus; do not replace unrelated `.agent/current-task.yaml`.
- **AC12:** Preserve S0–S11 event boundaries, source provenance, append-only conclusions with rights/privacy gates; no AI-made gold labels.
- **AC13:** One existing Tender Agent Watchdog continues unchanged; no disabling, duplicate scheduling, uncontrolled live ETП requests or write to production DB.

## In-scope
First implementation slice: Spec Kit `none` bootstrap, governed mapping to AES-001, source-count warnings fix, tests and validation against current read-only snapshot. Subsequent tasks follow existing MI checkpoint.

## Out-of-scope
Building a second crawler/market DB; replacing Data Platform; deploying a model/API; releasing a SaaS product; placing bids, ETP authentication circumvention, contacting vendors or triggering external commitments; fully automated market valuation without original evidence.

## Source baseline and known limitations (2026-10-28)
Verified runtime partial snapshot: 101 candidate rows, 34 223-FZ lot rows across 33 distinct EIS notices (31 notices with originals), **67** non-223/nonstandard rows, 3 original Bidzaar cards, 4 original B2B-Center cards, 6 commission decisions, 3 public 223 contract registry lots, **0 independently verified signed suppliers**. Out of 101 candidate rows, 39 have original primary sources (38 unique procurement numbers); 62 do not. 34 calendar months lack evidenced exhaustive provider discovery. The 10,998,960.00 RUB sample consists of three VAT-inclusive bid offers, not signed contract turnover. These are evidence counts, **not market coverage percentages**. Two EIS cases lack downloaded files; public 223 registry may hide supplier evidence. Commercial ETP award/contract outcomes remain incomplete.

**Extraction caveat:** New original documents have validated SHA and private storage, but the isolated ARC shell lacks the service Data Platform API key; as of this slice 247/262 canonical files have recorded completed extraction and 15 await authenticated SDK processing. A missing credential must produce a blocked/retryable state, never a false successful extraction.

**Decision authority:** consequential source-grade or market-coverage acceptance requires current evidence and ordinary product governance. Spec Kit output alone does not grant approval.
