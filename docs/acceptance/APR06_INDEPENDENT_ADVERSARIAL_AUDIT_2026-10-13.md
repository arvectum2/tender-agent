# APR-06 adversarial acceptance audit — 13 October 2026

**Verdict: NOT ACCEPTED. Engineering tests are green, but a passing metric report is not proof of procurement-law compliance or original EIS provenance.** This review independently inspected the APR-06 scorer and its synthetic tests, not the live EIS files. It does not record or impersonate human procurement experts.

## Source-derived findings

| Severity | Finding in current code | Consequence | Required action |
|---|---|---|---|
| HIGH | `acceptance.py` validates SHA-256 **syntax** and allowed EIS host, but does not independently read the file bytes to check their digest or verify the current EIS revision. Its unit-test fixture deliberately supplies arbitrary hashes and a general EIS search URL. | A self-declared `eis_verified` manifest can pass the format checker even when no original notice/attachment was retrieved. An `ACCEPTED` status is only as reliable as the external evidence process. | Require an independently collected per-procurement source receipt: official notice identity and revision, immutable original bytes, actual SHA-256 equality, timestamps and provenance; bind reviewer observations to the exact archived revision. Do not call current files EIS-verified without these checks. |
| HIGH | `evaluate_observation` allows `application_package.reviewed=false` as a valid observation. In `score`, rework uses only reviewed packages as denominator; with 27/28 reviewed packages and otherwise passing data, the old algorithm can report full case eligibility. | Partial package reviews can be hidden behind an apparently good rework rate. | Reject unreviewed packages on every required case (not only when the denominator is zero), and regression-test a single unreviewed item amid otherwise complete cases. |
| MEDIUM–HIGH | `evaluate_observation` requires a nonempty `claim_id` but does not check uniqueness. | Duplicate verified claim IDs could artificially raise citation coverage. | Reject duplicate claim IDs within each report and regression-test mixed verified/unverified copies. |
| HIGH (governance) | Threshold `approval.state=approved` accepts any nonempty approver, timestamp and decision reference. The test fixture deliberately generates synthetic owner-approval text. | An arbitrary JSON field is not an independently authenticated approval by the owner. | Keep real approval external, attributable and authenticated. Do not infer approval from a proposed threshold document or a unit-test `ACCEPTED` result. |
| MEDIUM | An `UNKNOWN` / `DEFER` machine decision is excluded from the false-GO/NO_GO comparison denominator, which can make a low observed error rate hard to interpret. | Reporting accuracy only for a narrow comparable subset may conceal abstention. | Report numerator and denominator, coverage/abstention share, and preapprove minimum-comparable-case thresholds with the owner before claiming acceptance. |

## What the existing measurements actually establish

- APR-06 public corpus contains **28 candidate** procurement numbers (20 under 44-FZ and 8 under 223-FZ), **not** 28 verified original EIS document sets.
- The machine prefill records **9 model/operator-system reports**, not independent expert decisions. No case has an attributable verified human review.
- The APR-07 frozen snapshot reports **20 historical 44-FZ intakes**, 17 with any downloaded file, nine analyzed; it is a small, earlier historical *technical* sample, not continuous production SLO.
- The Data Platform embedding benchmark uses Arvectum website pages and Search Console queries; this does not establish Russian procurement-domain model quality.
- A reproducible SHA of this snapshot confirms deterministic recomputation, **not** external evidence truth.

## Acceptance threat model and conservative gates

A green unit test demonstrates that the implementation obeys the programmed test assertions, not that synthetic documents, signoffs or evaluator choices correspond to an independently checked procurement. The project must reject three forms of circular validation: the same system producing its recommendation and its "human" verdict; a hash claimed without checking the file content; and a passing average that excludes incomplete cases.

Before releasing APR-06 or promoting APR-07 models, require a frozen 20–30-case official-source corpus, independent source receipts per revision, genuine reviewer identities and evidence references, complete package checks, and owner-authorized metric definitions/thresholds. **Neither this audit nor any automatic code patch authorizes bids, purchases, signatures, legal GO or production deployment.**

Audit method: static inspection of `src/modules/commercial_acceptance/acceptance.py`, `tests/test_apr06_commercial_acceptance.py`, `src/modules/quality_slo/snapshot.py`, APR-06 protocol and existing JSON sources in APR-06/07 PR branches. Findings are source-based analyses; do not cite them as already executed adversarial CI regressions until new tests have passed.
