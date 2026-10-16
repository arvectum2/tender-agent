# APR06/07: original EOK №0349100009326000005 — append-only source-backed correction

## Reason for corrective publication

The real historical original 44-FZ source/model run was successful:
4 actual local Gemma4 provider calls in 366.21s, 9/9 original
EIS XML + official DOC/DOCX source SHA/text verified, source-bound
EIS XML citations (original object, archived submission deadline,
original NMCK 130,000 RUB), stored read-only report/history, no
fallback or external ETP action.

The original legacy deterministic report incorrectly treated
an incidental 24/7 hosting/support requirement as a 24-hour
training program, hallucinated lecturers/classrooms and inherited
vehicle servicing/repairs/equipment next actions. In addition,
administrative rows of the actual 32,150-character application
evaluation-order document were mistaken for procurement service items.
A textual find/replace would not adequately correct these invented
scope details.

## Published source-only revision

A strictly additive, source-verified original report revision
`source-correction-v1` has been published to the **private
isolated original run directory**, without any LLM replay and without
rewriting any original model artifact. The version manifest
`output/report-revision.json` binds the procurement ID, original
run ID, all 9 source-file paths/SHA, original metadata SHA, old JSON
and HTML SHA, corrected new JSON and HTML SHA, and 0 new model calls.

| Invariant | SHA-256 / observation |
|---|---|
| Original HTML unchanged | `20ee85843d42f47acab1dbced2c318aedc06aa8c431040bad6a47afcbfde80d3` |
| Original JSON unchanged | `a77874d7aa367172ca31990e1b815b68a3d1bbe226ce42cae15e67a69680ae2a` |
| Original metadata unchanged | `f1979a0271ea0201934e40903606d983426f3b55b95dafb939dd57c4c0dd8725` |
| Source-only corrected report JSON | `b7af73f51fafc80ad851f1eaac0b1291b8f372206f585635938fffa12b360f3e` |
| Source-only corrected report HTML | `6130efde7fab320269ac35cbdab85ffc7f7390d94213b95478dd154ee45febad` |
| Source evidence | 9/9 original files, 3 originally sourced XML citations |
| Model provenance | four old genuine provider calls, **zero** new model calls |

The revision conservatively states only the verified archival source
subject (technical support and web hosting for the authority site),
historical 02.03.2026 07:00+03 deadline, historical 130,000 RUB
NMCK and the presence of the original contract. The actual source
file inventory is displayed. It does not guess service volumes,
training duration, staffing resources, required licences or unit
costs. Missing margin, internal resources and current EIS revision
are explicit and **human review remains mandatory**.

The original saved report is retained unchanged for audit;
the versioned source-only report is now the *active* read-only
projection for operator report JSON, HTML page, HTML download,
and run history step cards. A corrupted version pointer, original
source or either old/new report hash fails closed with HTTP409.

## Verifications

Actual FastAPI TestClient with the private original source run,
operator Basic authorization, all four routes:
JSON report 200, HTML report 200, HTML download 200,
read-only run history 200; unauthorized requests all 401.
The revised HTML has three official original XML source citation
rows. All four API outputs are free of fabricated education,
classrooms, vehicle repairs, learning hours and inaccurate
evaluation-order service items. The original HTML SHA stayed exact.
55 focused source/version anti-tamper and domain regression tests
PASS, plus 28 exact old R3/R5 compatibility and new fail-closed
revision tests PASS, Ruff PASS. **Full Mac mini suite 4,286 PASS /
238 SKIP / 0 FAIL (328 warnings, 150.41s)**. The first full
regression found three compatibility issues; all were corrected by
restoring byte-for-byte R3 projection AST and preserving legacy
HTML read hooks for runs without a corrected version, with green
targeted and then green full rerun. GitHub CI exact source-code commit
81481ea70a9f9ae42fa9c609f7d523cf5a15fe7c, run38861649220
**9/9 jobs SUCCESS**. Private actual FastAPI acceptance
receipt: runtime isolated output/apr067_case13_appendonly_corrected_real_api_receipt.json.
It captures 4 authenticated200/unauthorized401 route pairs,
immutable old/updated report SHA, 9 original files, 3 EIS XML cites,
and zero new real model calls.

The original 20-case cohort metric is preserved immutable with
historical 19/20 semantic status. The additional corrected
snapshot `docs/quality/APR067_R4_TWENTY_DISTINCT_TRUE_GEMMA_E2E_CORRECTED_COHORT_2026-10-16.json`
records the actual append-only correction separately. This allows
the **developmental** semantic report status to become 20/20
without rewriting the historical record or inventing an extra
model inference. The cumulative source/model count stays
20 distinct actual runs, 210 original SHA files, 80 real Gemma4
calls, 60 official XML evidence fact citations.

No qualified independent human legal-gold review, commercial price
approval, current live EIS verification, bid, signature, payment,
production deployment or rolling production SLA is implied.

## Final closure

Source-code CI 9/9 succeeded, the complete suite passed 4286/238 skipped, and the original case13 checkpoint status is **completed**. Repeated execution of the correction publisher was idempotent (old/new/pointer SHA all unchanged). The corrected source-only report is published, original model evidence preserved. The DEVELOPMENT report corpus is now 20/20, not independent signed legal gold, commercial bidding approval, ETP or production release. Draft PR449 remains unmerged.
