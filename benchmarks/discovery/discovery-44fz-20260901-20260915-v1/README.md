# DISCOVERY-QA-001 frozen 44-FZ benchmark release v1

This directory is the review evidence for `DISCOVERY-QA-001`.  It preserves a
45-case public EIS 44-FZ corpus, an independent blind label payload, the freeze
receipt index, and before/after Tender Agent ranking outputs.

## Anti-circularity order

The run order was fixed as:

`supplier profile -> independent query selection -> public EIS source acquisition -> source-only evaluator bundle -> independent local evaluator -> label freeze -> baseline SUT -> measured failure diagnosis -> bounded hardening -> same frozen corpus SUT rerun -> comparison`

The independent evaluator was `local-qwen2.5-14b-independent-discovery-evaluator-v1`.
It received only the source-only evaluator ZIP and evaluator instructions.  It did
not receive Tender Agent code, scores, previous labels, repository files, or web
access.  Query selection likewise occurred before SUT scoring and used only the
supplier profile plus source-only EIS result counts for feasibility.

## Cohort

- law: 44-FZ
- public source: EIS (`zakupki.gov.ru`), read-only
- fixed publication window: 2026-09-01 through 2026-09-15
- queries: `электротехническое оборудование`, `пусконаладочные работы`, `электротехнические услуги`
- 15 candidates/query; 45 query-candidate cases total
- frozen label counts: 10 `RELEVANT`, 16 `PARTIALLY_RELEVANT`, 19 `IRRELEVANT`, 0 `UNCLEAR`
- cohort manifest SHA-256: `286196ef1c10bdf5ded40dc434bc26b59eda271d3db02d95b8d96f15db8eaa7b`
- evaluator ZIP SHA-256: `79d2ee5a3e022926aa3aa60717e8d346edaeedc412d9dd46d473732ce0e68877`
- blind-label payload SHA-256: `a981a16d081fe1fafbdc0855843ad64ae65f84a4bac229f7db4dda0ed212cca5`
- cohort freeze SHA-256: `8a4f0898428b829698c53ed4e95a5276e2c52ece1f1a0c22622bcc13723a422e`

`blind_evaluator_input.zip` contains the immutable source-only evaluator inputs,
including the public EIS source snapshots needed to audit the labels.  The ZIP
contains no SUT output or benchmark answers.

## Baseline

Baseline runtime: `relevance_scoring@8827bdf1e0d6f0f1bb0de34ae06064cb3b3da407-baseline`.

| Metric | @5 | @10 |
|---|---:|---:|
| Precision | 0.7333 | 0.5667 |
| Recall | 0.4597 | 0.6355 |
| nDCG | 0.7305 | 0.7596 |
| False-positive rate | 0.2667 | 0.4333 |

Primary-K missed-relevant rate: `0.3645`; duplicate rate: `0.0`; explainability
coverage: `1.0`; supported deadline correctness: `1.0` (45/45). Status correctness
was not scored because the current card/detail surface did not expose a normalized
comparable status field.

Measured baseline failure inventory: 13 top-10 irrelevant placements and 9
missed-relevant cases.

## Measured failure classes and bounded fix

The frozen baseline exposed three concrete ranking defects before product code was
changed:

1. unrelated cards with zero supplier-topic evidence received enough neutral
   price/deadline/risk points to rank above genuinely relevant low-price cards;
2. one clear supplier keyword was diluted by division across the complete keyword
   list, underweighting strong single-capability matches;
3. broad prefix matching conflated derivationally different Russian words, e.g.
   `автоматизация` with `автоматизированная`, causing software procurements to
   inherit an electrical-automation signal.

The bounded hardening therefore does only the following:

- commercial/deadline features cannot create relevance without a supplier-topic
  match;
- unknown card-level risk is neutral instead of an unconditional positive score;
- one explicit profile keyword match gets a strong bounded semantic base, with
  only small incremental evidence for additional matches/category phrases;
- Russian morphology matching uses conservative inflection handling instead of a
  generic prefix heuristic.

No LLM reranker, vector database, new external service, or paid dependency was
introduced.

## Frozen-corpus rerun

Hardened runtime: `relevance_scoring@32d5ce3336af3c3ff9e79625f2a813b312941579-hardened`.

The post-fix run reused the exact same source corpus and frozen labels.  Comparator
and label-normalization code were not changed after observing SUT output.

| Metric | Baseline @5 | Hardened @5 | Baseline @10 | Hardened @10 |
|---|---:|---:|---:|---:|
| Precision | 0.7333 | 0.9333 | 0.5667 | 0.7000 |
| Recall | 0.4597 | 0.5885 | 0.6355 | 0.8120 |
| nDCG | 0.7305 | 0.7997 | 0.7596 | 0.8302 |
| False-positive rate | 0.2667 | 0.0667 | 0.4333 | 0.3000 |

Primary-K missed-relevant rate improved from `0.3645` to `0.1880`.  Top-10
irrelevant placements decreased from 13 to 9, and missed-relevant cases from 9 to
5. Duplicate rate remained `0.0`, explainability coverage remained `1.0`, and
supported deadline correctness remained `1.0`.

## Review boundary

This release is AI-curated benchmark evidence, not Product Owner gold truth.
`DISCOVERY-QA-001` retains `REVIEW` authority and `auto_merge=false`.  The code PR
must stop before merge for Product Owner review.  Nothing in this benchmark
creates, signs, submits, invites, purchases, or otherwise causes an external
procurement/commercial effect.
