# APR-02 — source-bound review prompts from original RI223 XML

Date: 2026-10-08. This increment does not produce GO/NO-GO, eligibility,
legal validity or customer commitments. It reuses the existing Tender Research
analysis and its RI223 source-fact projection in merged PR #237.

## Real original evidence

- Source 32616376947, RI223 ZIP SHA-256
  840927b8dddba00cc682e78192ffb263cbd89d3fec1acbaba3fa60af63fd3575:
  13 individually source-bound XML facts; three independently triggered
  human-review flags:
  1. OBSERVED_SUBMISSION_DEADLINE_CHANGE — notice versions 1, 2 and 3 publish
     different submitted-close values (2026-10-01, 2026-10-12 and
     2026-10-20 at 16:00 local source notation). Legally effective
     publication/status not inferred.
  2. EXPLANATIONS_REQUIRE_DOCUMENT_REVIEW — six separate source explanation
     XMLs observed; source question is not treated as a verified answer,
     and lot applicability remains UNKNOWN.
  3. MULTI_LOT_REQUIRES_SEPARATE_REVIEW — two source-bound lots with
     independent objects and sums. No global NMCK inference by summation.
- Independent negative control 32616445795, source ZIP SHA-256
  65004d53a4d198857a192ad21052c95cfa7d812208c3ac6702324e42d7487de3:
  3 source facts, zero derived review flags. The original RAR/Data Platform
  text extraction path is not modified.

## Architecture and safeguards

- Derive deterministic review prompts from the already source-bound
  RI223 observations; do not use a second document analyzer or Decision Core.
- Each flag has an unambiguous code, NEEDS_REVIEW status, explicit
  UNKNOWN legal effect and cited original XML member/hash/XPath evidence.
- Expose flags via the existing TenderAnalysisResult, AnalyzeResponse API,
  CLI JSON and Markdown report; keep source facts separate from RAG
  chunk citations and LLM analysis.
- No new time inference, eligibility assessment, automatic participation
  or EIS/ETP signing, posting or payments.
- Missing, unrelated or unverified source facts cannot trigger such flags.

## Validation

- Focused tests: 22 passed.
- Full Tender Research suite: 505 passed, 1 skipped, 42 warnings.
- make check, changed-file Ruff, git diff --check: PASS.
- Exact-head CI and Owner review required before merge.

## Next measured need

Combine the newly visible XML review points with document-text evidence
and source-cited human assessment of technical fit, qualification,
contractual risks and application readiness; do not promote source
observations into legal/participation decisions without review.
