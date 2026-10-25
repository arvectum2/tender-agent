# APR-03B / APR-04 / APR-05 — isolated integration readiness (no main merge)

## Scope and repository safety

A dedicated non-production review worktree was created from verified
`origin/main` commit `bc98bd397bbd91186dd08e1e611d972077c4ab74`.
The **existing independently accepted, still Draft** source PRs are
integrated **only into the isolated review branch**, in this order:

1. [PR #433](https://github.com/arvectum2/tender-agent/pull/433)
   (APR-03B: authentic archived EIS 44-FZ source-grounded, actual
   local model, three EIS critical source citations, operator read-only).
2. [PR #434](https://github.com/arvectum2/tender-agent/pull/434)
   (APR-04: real-company legal identity source-bound profile, isolated
   tenant store, personal archive evidence; UNKNOWN where owner business
   limits and qualifications have not been supplied).
3. [PR #435](https://github.com/arvectum2/tender-agent/pull/435)
   (APR-05: isolated staged tenant trial invitation and bearer session,
   protected profile read/write returns 428 without SaaS legal consent;
   no real payment evidence).

All three source GitHub PRs were open Draft and had **18 successful,
0 failed/pending checks each** at the start of this review.
Independent merges into this throwaway branch succeeded without
conflicts, yielding local commit `04837411`. No branch named
`main`, production service, ETP, operator credential or company
financial record was modified.

## What has actually been verified

The local combined integration has **63 PASS** targeted APR-03B,
APR-04, APR-05 and company profile regression tests; Ruff check PASS.
The complete merged-code Mac mini pytest regression independently
passed **4,033 tests / 238 skipped / 0 failed** in 154.85 seconds
(329 existing warnings). This combined execution is not an EIS- or
production-effect test; its result is local software integration only.
Exact GitHub review-branch CI is a separate acceptance gate and will be
recorded when complete.

This is an integration/review exercise, not a new validation of the
original company's registration documents. The original business
identity PDFs were inspected in the conversation context but **not
uploaded to this Mac mini's isolated staging datastore**; a synthetic
labelled PDF was used for access-control and integrity checks. Nothing
here establishes supplier eligibility, licences, SRO, experience or
operational ability.

## Required external and owner gates (explicitly OPEN)

- **Code merge:** APR-03B, APR-04, APR-05 source PRs and this
  integration packet are still Draft. The queue does not grant
  `auto_merge` authority for these APR cases. The Company AM-4
  policy requires an explicitly authorized queue item for automatic
  merge. Do not promote a green CI into permission to merge to main.
- **Corporate profile:** Owner must confirm the original registration
  identity/documentary verification in the approved environment and
  independently supply commercial NMCK bounds, price/margin policy,
  capacity, service categories, risks and qualification evidence.
  Unknown values stay UNKNOWN, not fabricated WITHIN_BOUNDS or GO.
- **SaaS legal gates:** The owner has not accepted versioned terms and
  privacy documents. No real tenant paid entitlement or receipt has
  been authorized. Trial identity is synthetic; write methods remain
  428 (legal hold). No external invitations or actual billing.
- **Procurement decision:** The archived EIS notice is historically
  authenticated, not verified against a current live edition;
  legal/business GO, ETP application, electronic signature,
  contractual commitments and production deployment remain barred.
- **Cross-PR publication:** Branches #433/#434/#435 must be reviewed
  with their actual base stack and exact-head CI before any separately
  approved deployment or merge sequence.

## Acceptance boundary

This review closes when the combined code has a green full local
regression, the exact committed review branch CI is green and the
readiness-only checkpoint is marked `completed`. It never closes
owner legal, real paid SaaS, supply eligibility, external ETP or
production access gates.

The independent 20/20 original historical EIS DEVELOPMENT E2E semantic
benchmark and its corrected case13 append-only original audit were
completed on a different Draft stacked branch and are **not** merged
into this readiness branch; avoid conflating their Git histories.
