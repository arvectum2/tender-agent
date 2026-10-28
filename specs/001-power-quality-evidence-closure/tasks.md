# Power Quality — Spec Kit task plan

**Source of priority/status**: existing TA-MI-AUTONOMY-20261027 checkpoint, `docs/roadmap/MASTER_ROADMAP.md`. This document tracks only this bounded SDD feature; it is not a competing roadmap.

## Phase 1 — adoption and trustworthy partial report (US1)
- [x] T001 Audit current `origin/main`, AES-001, Accepted RFC boundaries and S0–S11 protocol; isolate active runtime/Watchdog.
- [x] T002 Initialize Spec Kit v1.2.4 `none` in a new worktree, not the dirty main checkout.
- [x] T003 Replace placeholder constitution with non-authoritative governance adapter and document ChatGPT → ARC implementation rules.
- [x] T004 Reconcile count warnings in `pq_verified_market_report.py` to exact computed source counts; never hardcode 101/69.
- [x] T005 Add tests for 3/2/1 and 101/33/68 corpora; assert no TAM or signed-supplier inference.
- [x] T006 Validate lint, unit/regression and source snapshot consistency, then cross-review documentation/code/test diff.
- [x] T006a Repair existing CI architecture failure without relaxing audit: PQ extraction now uses the shared Data Platform consumer SDK facade, not a cross-repo Python import; source SHA, read-only extraction, selective resume, failure receipt and PDF fallback regression tested with a real synthetic authorized HTTP request.
- [x] T007 PR #520 merged to `main` as `e92c948c`; Spec Kit CLI v1.2.4 status OK; targeted smoke 17 passed (CI/merge already performed, broader AES S0-S11 closure still open).

## Phase 2 — audited original sources (US2)
- [ ] T008 2024, 2025, 2026 discovery coverage: ЕИС 44/223, official contract register, commercial ETPs; log dates, provider, queries, failures and explicit denominator.
- [ ] T009 Recover primary source and relevant original protocol/documents for the 68 non-223/nonstandard leads; 3 verified Bidzaar original cards are an initial subset, not 68 verified outcomes.
- [ ] T010 Revisit 32615966040 and 32616400421 after bounded retry; absence of downloaded files ≠ absence of procurement.
- [ ] T011 Join each evidence-supported lot with official commission and contract registry; preserve legally unavailable signed-supplier fields as unknown.
- [ ] T012 Normalize buyer, EPC, designer, OEM, dealer and service roles with INN and primary citations; check alternate explanations.
- [ ] T013 Deduplicate notice ↔ lot ↔ project ↔ signed contract, including repeated tenders and mixed EPC; exclude non-PQ costs from any PQ market-volume calculation.
- [ ] T014 Run source-grade numeric, privacy, rights, audit, contradiction and coverage checks; produce report + separate registers with original evidence and exact coverage limitations.

## Phase 3 — governed continuation (US3)
- [ ] T015 Exercise bounded restart/resume S0–S11 with existing SHA source ledger, queue, lease and checkpoint; prevent duplicate external actions.
- [ ] T016 Connect report acceptance evidence to existing roadmap/checkpoint after normal reviewed integration; preserve hourly Watchdog unchanged.
- [ ] T017 Only when evidence sufficient, independently review source-verified full report and consider task closure. No invented market size, supplier contract or training gold.

## Closure evidence
Record exact tests, exit codes, source snapshot version, base/head SHA, PR/CI state and unresolved source gaps. `In progress` means no DONE 100% claim.
