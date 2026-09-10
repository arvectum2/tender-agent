# BENCHMARK-PIPELINE-001 — canonical issue #1

> Repository migration note (2026-09-10): canonical repository is now `arvectum2/tender-agent`. Historical issue `#52` and PR numbers `#56/#57/#58/#60/#61` refer to the previous GitHub repository/account and are retained only as git-history provenance.

## Status

The blind benchmark contract and first methodologically clean real 44-FZ baseline are complete. A same-case frozen-truth control rerun was completed on 2026-09-10 with source-byte equality PASS, but the **product-quality gate did not pass**: scored document metrics were unchanged and the `customer_name` contradiction remained.

Canonical issue: `#1`.

Product-code baseline before migration/docs commits: `81f77d5f97ae92733f5887136aa0c1f67ceb22ae`.

Current phase: **baseline-vs-control diagnosis before any corpus growth**.

## Historical completed implementation

Preserved git history includes:

- old PR `#56` — blind benchmark contract hardening; merge `dec002926f0a996c537c854548e3636e905140ba`; CI PASS;
- old PR `#57` — safe source-only real-calibration Phase A; merge `0958505576cdcd8a7edeb0a5d4973bf07f43cf76`; CI PASS;
- old PR `#58` — discovery-context binding + audited normalization; merge `b8d22ce044c02fa034f7f13d8a260f55dbd9f2f1`; CI PASS;
- old PR `#60` — first benchmark-driven DOCUMENT-QA product fixes; merge `ab8ca415e1f08edfcb9edd28633d7958396af6d4`; CI PASS;
- old PR `#61` — frozen-truth control-rerun helper; merge `81f77d5f97ae92733f5887136aa0c1f67ceb22ae`.

## Frozen baseline

Case:

- case id: `calibration-44fz-0848300045426000620-rerun-20260906-01`;
- law: 44-FZ;
- registry: `0848300045426000620`;
- baseline revision: `33cbc7b285dad5faa0ad21b46cd5823499d58ea5`;
- source bundle: 8 original public files;
- discovery: `NOT_SCORABLE`.

Baseline document score:

- TP 2;
- FP 1;
- FN 24;
- precision 0.6667;
- recall 0.0769;
- F1 0.1379;
- runtime extras 14;
- contradiction `customer_name`;
- review `NEEDS_REVIEW / UNCLASSIFIED_MATERIAL_DISAGREEMENT`.

Frozen source/evaluator/labels/freeze are immutable.

## Defects exposed by baseline

1. misleading/misspelled file suffix with OOXML payload;
2. organizer propagated as `customer_name` instead of actual customer;
3. unrelated healthcare/ЕРН/СМЭВ/СЭМД/Минобороны/СВО template contamination;
4. low structured-fact coverage.

Old PR #60 / commit `ab8ca415...` attempted fixes for 1–3.

## Frozen-truth control rerun — completed

Control runtime revision: `7d78cb5d49177fa8a1e07c9cbb444a65be148e01`.

Integrity:

- remote: `https://github.com/arvectum2/tender-agent.git`;
- tree clean;
- post-`81f77d5...` tracked product diff: migration/docs only;
- status: `BENCHMARK_CONTROL_RUNTIME_READY`;
- exact source bytes: PASS 8/8;
- same frozen truth reused;
- no Phase A / truth regeneration.

Control result:

- TP 2;
- FP 1;
- FN 24;
- precision 0.6667;
- recall 0.0769;
- F1 0.1379;
- runtime extras 13;
- contradiction still present:
  - actual `МКЦ Одинцовского ГО`;
  - expected `МК "Служба кладбищ" Одинцовского ГО`;
- review `NEEDS_REVIEW / UNCLASSIFIED_MATERIAL_DISAGREEMENT`.

Interpretation: benchmark methodology passed, but expected product-quality improvement was not demonstrated.

## Product Owner inspection decision

**DO NOT CLOSE #1. DO NOT GROW CORPUS.**

The control proves that the benchmark harness can safely compare the same immutable truth across revisions. It does not prove the intended DOCUMENT-QA fixes work on the real case.

Specific current conclusions:

- OOXML fix: not accepted from this aggregate result alone;
- customer/organizer fix: current real evidence indicates it is still ineffective or bypassed;
- legacy contamination fix: cannot be accepted until the 13 runtime extras are semantically diffed against the baseline 14;
- structured-fact recall: no scored improvement; 24/26 expected facts remain false negatives.

## CURRENT next action — diagnostic only

Before any code changes, compare the baseline and control artifacts and trace each disagreement to its stage.

Required local diagnostic:

1. Verify the backend process used for the control actually loaded post-`ab8ca415...` code and the `document_qa_runtime_patch` install path; record executable, cwd, imported module path and loaded function/module identity where practical.
2. Diff baseline vs control `normalized_sut_output.json`, `normalization_audit.json` and raw `sut_runtime_response.json`.
3. Trace `customer_name` end-to-end: source text -> extraction -> intermediate payload -> final runtime payload -> benchmark normalizer. Identify the exact function/surface where `МКЦ Одинцовского ГО` enters or survives.
4. Identify exactly which runtime extra disappeared between 14 and 13. List all remaining control extras and flag any healthcare/ЕРН/СМЭВ/СЭМД/Минобороны/СВО contamination.
5. For all 24 false-negative truth fields, classify the loss stage:
   - source acquisition
   - parsing
   - extraction
   - reasoning
   - serialization
   - benchmark normalization
6. Specifically determine whether canonical facts are already present in raw runtime but omitted by `normalize-phase-b`.
7. Do not edit frozen truth, do not add a second procurement, and do not tune search/document logic during diagnosis.

Return an evidence table with one row per contradiction/FN/runtime-extra delta and exact source/runtime field references.

## Exit criteria before another frozen rerun

A code/normalizer fix is justified only after diagnostic attribution identifies the smallest responsible surface. Then rerun the exact same frozen case again.

## Exit criteria before second procurement / 30–50 corpus

Do not grow until:

- customer contradiction is precisely attributed and corrected/reclassified;
- legacy contamination is explicitly checked from runtime claims;
- all 24 FNs are stage-classified;
- benchmark normalization is proven not to hide already-extracted facts;
- the smallest evidence-backed fix is applied;
- another same-frozen-truth control demonstrates the intended correction without new unsupported claims;
- Product Owner explicitly approves corpus expansion.

## Anti-circularity contract

New case:

`public source bundle -> context-bound source-only evaluator bundle -> independent labels -> freeze -> Tender Agent output -> audited normalization -> comparator -> review routing`

Control case:

`existing frozen source/truth -> immutable copy + hash verification -> fresh source-only backend run -> exact source-byte equality -> Tender Agent output -> audited normalization -> comparator -> review routing`

## Scope boundary

223-FZ/RSL `32616312799` remains outside this accepted 44-FZ benchmark path. Supplier/TKP acceptance and external procurement actions remain out of scope.