# APR-06 independent source and owner attestation release gate — 13 October 2026

**Safety outcome: do not report commercial acceptance from self-attested JSON inputs.**

## Independent source review

`score()` previously returned `ACCEPTED` when all synthetic observations, matching hash strings and text-only `approval.state=approved` were present. The unit test deliberately constructed invented EIS notice/document digests and an invented owner name; this should test calculation mechanics, **not prove customer-safe commercial acceptance**.

APR-06 still lacks independently authenticated current EIS notice revision, verified collector receipt with original official document bytes, and attributable real-human signoff. PR #394 rejects unreviewed application packages and duplicated claim IDs. PR #396 verifies local bytes against the self-declared frozen manifest; its output explicitly states that official origin is **not** verified.

This change preserves deterministic metric calculation while guaranteeing a complete passing metric set produces only `PENDING_EXTERNAL_SOURCE_AND_OWNER_ATTESTATION`, not `ACCEPTED`. A `FAILED_ACCEPTANCE`, `PENDING_OWNER_THRESHOLD_APPROVAL`, or `INSUFFICIENT_REVIEW_EVIDENCE` remains unchanged in meaning. The report carries `owner_approval_authenticated=false`, `independent_official_eis_provenance_verified=false`, `commercial_release_authorized=false`. The `score` CLI exits nonzero, even for synthetic fully passing records. Validation and freeze commands preserve their existing semantics.

**This is intentionally a conservative temporary gate**, not an assertion that no future case can qualify. Only a separate independent official-source attestation and owner-confirmed real review should be allowed to unlock an actual `ACCEPTED` result in a later explicitly tested change (see issue #395). A caller-provided bool or unsigned approval string must never bypass this guard.

## Adversarial regression requirements

- With all 28 synthetically labeled cases, arbitrary 64-hex notice digests and a synthetic `approval.state=approved`, calculated thresholds can pass but status **must not** be `ACCEPTED`.
- Even when invoked via the command line, writing the report must not return exit code zero for these synthetic inputs.
- Every output must visibly declare official EIS provenance and authenticated owner approval unknown, even when all seven metric values are good.
- No live EIS requests, supplier contacts, model downloads, signatures, ETP bids, payments or deployment in this patch.

## Remaining external acceptance work

Human: verify 20–30 unique original official EIS cases, procurement number/revision, archive completeness, attached bytes and legally relevant citations, collect attributable real expert choices, approve meaningful comparison coverage and seven KPI thresholds, and independently authenticate owner signoff. The existing **28 are candidates**; the **nine machine outputs are not human review**; APR-07's earlier quality snapshot is neither Russian procurement model gold nor measured production SLO.

The actual trusted release-attestation workflow is not implemented by this patch; commercial and legal approval remain **BLOCKED**.
