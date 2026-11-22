# APR-06 / #406: source-bound competitive qualification risk — 22 November 2026

Scope: **read-only** decision screening, never legal eligibility ruling or
automatic ETP/bid action. This is an additive policy correction to the current
screening module, NOT a revision of October 2026 frozen human-gold datasets.

## Known first-party case and the separate decision dimensions

The saved original EIS CZN notice #0348100024426000039 revision 4 and
source-bound scoring DOCX were previously replayed in
TA_QUALIFICATION_OFFICIAL_SOURCE_REPLAY_2026-10-13.md with checked original
UID/hash. The source criterion is 70% completed-contract qualification,
30% price, based on qualifying completed 44-FZ/223-FZ web/information-system
modernization INCLUDING chatbot work and a signed final acceptance act
within five years of the bid deadline. No 70/30 values are hard-coded into
other tender scoring; the criterion is carried with exact source
procurement number, notice version, document UID and SHA256.

The owner-confirmed COMPLETE experience snapshot used in this historical
case has zero qualifying completed signed contracts. That is strong
**competitive disadvantage**, NOT proof of legal ineligibility, technical
infeasibility, a zero final award score or any numeric chance of winning.

| Evidence / source-bound case | Qualification assessment | Commercial screen | Legal Decision Core |
| --- | --- | --- | --- |
| Confirmed complete zero, original qualification share >=60% | HIGH_COMPETITIVE_RISK | DEFER, qualification_priority LOW, mandatory human review | Original legal status unchanged; no bid permission |
| Confirmed complete zero, share below 60% | COMPETITIVE_RISK_NOT_AUTOMATIC_NO_GO | HUMAN_REVIEW_REQUIRED | Unchanged |
| No valid reference snapshot / stale owner fact | QUALIFICATION_EVIDENCE_UNKNOWN | HUMAN_REVIEW_REQUIRED | Unchanged |
| Incomplete owner reference list | QUALIFICATION_EVIDENCE_PARTIAL | HUMAN_REVIEW_REQUIRED | Unchanged |
| Expired reference fact | QUALIFICATION_EVIDENCE_EXPIRED | HUMAN_REVIEW_REQUIRED | Unchanged |
| At least one potentially qualifying signed completed reference | QUALIFYING_REFERENCES_PRESENT_REVIEW_SCORE | HUMAN_REVIEW_REQUIRED | Unchanged |
| Independent EIS application deadline already expired | Competitive risk dimension remains as above | DEFER for competitive dimension only | Existing hard legal NO_GO remains NO_GO |

The >=60% rule is an **internal conservative prioritization heuristic**,
not a formula extracted from the CZN original or a legal requirement.
Legal admissibility and technical feasibility remain NOT_ASSESSED by
qualification screening and must be determined independently by original
procurement and contractor evidence. No estimator of a final score or
predicted win probability is introduced.

## Exact trust and compatibility boundaries

The current qualification-aware read API checks that the criterion and
source_binding agree exactly on EIS number, notice revision, UID, source
SHA and deadline. It does not itself download original EIS bytes, verify a
signature or establish that a self-supplied digest is a trusted original:
source receipt/bytes must be independently validated upstream by the
existing original source adapter and then separately reviewed. A matching
caller-provided string is never standalone proof of current official notice
edition.

Legacy v1 literal NO_GO_QUALIFICATION_COMPETITIVENESS is retained as a
schema-compatible historical enum for archived October reports, but the
new confirmed-zero/high-weight source-bound screening logic does NOT emit
it. Do not rewrite frozen CZN source/human-gold files, past report
snapshots, owner histories or previously signed judgments.

No data migrations, production deploy, automatic ETP/bid action, supplier
contact or paid access. Run 44/223 subject/law, signed final act,
five-year lookback, original UID/checksum, notice revision, tenant
isolation and legal-deadline regression tests before protected merge.

## Remaining acceptance

Engineering tests and protected CI can validate read-only semantics.
Issue #406 should remain OPEN until Owner explicitly reviews the
commercial DEFER policy and independent current-source attestation, and
approves any release in a separately authorized production change. The
frozen APR-06 human-gold commercial KPIs remain untouched.
