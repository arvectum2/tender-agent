# APR-03B / APR-04 / APR-05 — composed synthetic API boundary, 24 November 2026

**Engineering DEVELOPMENT test: PASS on initial base 61cf6c92 (PR #739).** This is a composed **synthetic** continuity and fail-closed test, not official-original EIS acceptance, a real customer onboarding, actual legal consent, production deployment, or public/paid SaaS readiness.

## Measured and isolated scope

The new tests/test_apr0405_composed_synthetic_e2e.py exercises a single in-process FastAPI TestClient with disposable in-memory SQLite and two *fictional* entities (no real company ID, real registration PDFs, model, DP, EIS network call, payment or ETP traffic). The only preanalysis_from_public_search result is explicitly stubbed with a synthetic:case-1 citation; it is never presented as an authenticated original.

The test follows these API boundaries in sequence:

1. APR-04 operator onboarding creates two separate company profiles with price limits unset; a source-cited synthetic initial price must yield UNKNOWN, HUMAN_REVIEW_REQUIRED, and external_action_allowed=false.
2. APR-05 operator creates two distinct synthetic SaaS tenants; token redemption is scoped. Both company portfolio case creates fail HTTP **428** before *test-only* per-member legal acknowledgement.
3. Synthetic acknowledgement in tenant A leaves tenant B under **428**. After isolated synthetic acknowledgement by B, the same 19-digit reference yields **different** company case IDs; neither is a verified source and neither allows external submission.
4. Foreign tenant cannot read or write A's case/decisions (**404**). Only A records an explicitly human-origin DEFER; B has no decision.
5. SQLite inspection confirms **two test-only legal acceptance records**, **zero payment evidence**, **one scoped portfolio decision**, and **zero global Deals**. No automatic bid or corporate action is inferred.

## Verification

Initial focused regression on macOS Python 3.12 offline dependencies: **126 passed, 2 skipped, 0 failed**, plus Ruff and compile PASS. Skips are optional profile cases, not an acceptance of network-dependent behaviors. The new foreign-tenant write-denial assertion was rerun successfully; hosted protected CI remains a separate gate.

Existing prior APR-03B/04/05 archive and real-company private rehearsals remain unchanged. No previously copied original data was moved. Historical private identity verification and official live EIS edition are **NOT** attested here. This test does **not** reproduce a live model/citation claim or assert an actual legally authorised GO.

## Next acceptance gates

- Confirm tested current official original, source-revision and claim provenance for any real-case adoption.
- Independent role/tenant staging acceptance, actual owner business profile and documentary review.
- Legal/contractual and human approval of real customer, physical iPhone interaction, notifications and rollout.
- Separate permission for any production deployment, source fetching, ETP, bidder application, real invitation or billing.

This record is additive, with no extra executor admission, watchdog, DB writes, or production changes.
