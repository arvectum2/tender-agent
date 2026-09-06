# BENCHMARK-PIPELINE-001 (#52)

## Status

The blind benchmark contract and the first methodologically clean real 44-FZ baseline are complete. The pipeline is now being used as intended: the clean baseline exposed concrete Tender Agent product defects, DOCUMENT-QA fixes were merged, and the next gate is a **same-case control rerun against the exact same frozen truth**.

Canonical merges:

- PR `#56` — blind benchmark contract hardening; merge `dec002926f0a996c537c854548e3636e905140ba`; CI PASS.
- PR `#57` — safe source-only real-calibration Phase A; merge `0958505576cdcd8a7edeb0a5d4973bf07f43cf76`; CI PASS.
- PR `#58` — discovery-context binding + repository-owned audited normalization; merge `b8d22ce044c02fa034f7f13d8a260f55dbd9f2f1`; CI PASS.
- PR `#60` — first benchmark-driven DOCUMENT-QA product fixes; merge `ab8ca415e1f08edfcb9edd28633d7958396af6d4`; CI PASS.

#52 remains open. Do not grow the corpus until the post-#60 control rerun is complete and inspected.

## Clean first real baseline

Case:

- case id: `calibration-44fz-0848300045426000620-rerun-20260906-01`;
- law: 44-FZ;
- registry number: `0848300045426000620`;
- frozen product revision: `33cbc7b285dad5faa0ad21b46cd5823499d58ea5`;
- source bundle: eight original public source files;
- labels were generated independently and frozen before Tender Agent analysis;
- discovery context was bound before blind evaluation;
- runtime normalization was repository-owned and audit-bound;
- discovery was correctly `NOT_SCORABLE` because no separately context-bound discovery SUT result was supplied.

Document baseline:

- TP: 2;
- FP: 1;
- FN: 24;
- precision: 0.6667;
- recall: 0.0769;
- F1: 0.1379;
- 14 material runtime extras preserved;
- contradiction: `customer_name`;
- review: `NEEDS_REVIEW` / `UNCLASSIFIED_MATERIAL_DISAGREEMENT`.

This case is now the frozen control baseline. Its source files, evaluator bundle, blind labels and `frozen_label.json` must not be regenerated or edited for the post-fix comparison.

## Product defects exposed by the baseline

The clean baseline separated harness defects from Tender Agent defects and exposed four product-quality classes:

1. **document parsing/source acquisition** — EIS attachments can contain OOXML under misleading or misspelled suffixes;
2. **source-role/entity resolution** — organizer was propagated as `customer_name` instead of the actual customer;
3. **reasoning/presentation contamination** — legacy healthcare/ЕРН/СМЭВ/СЭМД/Минобороны/СВО templates leaked into an unrelated software procurement;
4. **structured-fact coverage** — the normalized product output exposed far fewer canonical procurement facts than the frozen source truth contains.

PR #60 addresses the first three classes with source-bound parsing/entity/output fixes. The fourth class must be measured again after those fixes rather than guessed from the old baseline.

## Frozen-truth control rerun

The control rerun is **not** a new calibration case and must not execute Phase A again. It reuses the immutable benchmark inputs from the clean baseline and produces only a fresh SUT side of the comparison.

Repository helper:

```bash
python3 scripts/run_benchmark_control_rerun.py \
  --source-case-dir <clean-baseline-case-dir> \
  --output-dir <new-empty-control-dir> \
  --runtime-version <current-main-sha> \
  --backend-url http://127.0.0.1:8000
```

The helper fails closed before analysis unless all of the following are true:

- the original case manifest, evaluator bundle, blind labels and freeze receipt validate;
- the current case manifest hash still matches the digest bound by `frozen_label.json`;
- source files still match the frozen manifest hashes;
- only immutable benchmark inputs are copied into the new control directory;
- copied immutable artifacts remain byte-identical;
- the fresh backend run has not begun analysis;
- the fresh backend source-file SHA-256 multiset exactly equals the frozen source-file hash multiset.

Only after those checks does it call the existing Tender Agent analysis endpoint and save `sut_runtime_response.json`. It never generates evaluator input, labels or a freeze receipt.

Expected marker:

`BENCHMARK_CONTROL_RUNTIME_READY`

## Post-runtime normalization and comparison

After the helper returns READY, keep discovery unscored unless a genuine context-bound discovery result exists. For the current document-only control, omit `--discovery-result`.

```bash
CONTROL=<new-empty-control-dir>
RUNTIME_VERSION=<current-main-sha>

python3 scripts/benchmark_calibration.py normalize-phase-b \
  --case-dir "$CONTROL" \
  --runtime-version "$RUNTIME_VERSION"

python3 scripts/benchmark_pipeline.py compare \
  --bundle "$CONTROL/evaluator_bundle.json" \
  --discovery "$CONTROL/blind_discovery_label.json" \
  --truth "$CONTROL/blind_document_truth.json" \
  --freeze "$CONTROL/frozen_label.json" \
  --sut-ref "$CONTROL/tender_agent_output_ref.json" \
  --sut-output "$CONTROL/normalized_sut_output.json" \
  --output "$CONTROL/comparison_result.json"

python3 scripts/benchmark_pipeline.py route-review \
  --manifest "$CONTROL/case_manifest.json" \
  --discovery "$CONTROL/blind_discovery_label.json" \
  --truth "$CONTROL/blind_document_truth.json" \
  --freeze "$CONTROL/frozen_label.json" \
  --comparison "$CONTROL/comparison_result.json" \
  --output "$CONTROL/review_state.json"
```

Preserve both the original baseline directory and the new control directory. The comparison to inspect is baseline revision `33cbc7...` versus the current post-#60 main under the same source and same frozen truth.

## Discovery-context rule

Every *new* real discovery-scored case must bind a complete sanitized supplier/query context before blind evaluation. Discovery is scorable only when the SUT artifact declares the exact same `discovery_context_sha256`; otherwise comparator outcome is `NOT_SCORABLE`, not `MISMATCH`.

The post-#60 control does not invent a discovery result. Its purpose is DOCUMENT-QA/product regression measurement.

## Normalization rule

Repository-owned `scripts/benchmark_calibration.py normalize-phase-b` remains mandatory. It:

- maps known canonical facts deterministically;
- maps explicit `НМЦК:` economics output to `initial_max_price_rub`;
- preserves unmapped material economics/requirement/risk claims as `runtime_claim.*` facts;
- records intentionally ignored questions/operator instructions/workflow decisions in `normalization_audit.json`;
- fails closed when a new decision-bearing `final_recommendation` surface is unclassified;
- binds the audit digest into `tender_agent_output_ref`;
- derives `produced_at` from the actual analysis-completion event when available.

Unsupported or contaminated material claims therefore remain visible to the comparator instead of disappearing in projection.

## Review-state semantics

`AI_CURATED_SILVER` describes independent truth quality, not whether Tender Agent passed. `NEEDS_REVIEW` is used for benchmark/source uncertainty or unclassified material disagreement. Product Owner promotion to `HUMAN_VERIFIED_GOLD` changes review metadata only and never rewrites frozen truth.

Do not promote the current clean baseline truth to gold implicitly. Promotion still requires explicit Product Owner approval.

## Anti-circularity contract

Canonical new-case order remains:

`public source bundle -> context-bound source-only evaluator bundle -> independent labels -> freeze -> Tender Agent output -> audited normalization -> comparator -> review routing`

The control-rerun order is deliberately different because truth is already frozen:

`existing frozen source/truth -> immutable copy + hash verification -> fresh source-only backend run -> exact source-byte equality -> Tender Agent output -> audited normalization -> comparator -> review routing`

Fail closed when:

1. evaluator input contains SUT/ranking/report leakage;
2. evidence points outside the source bundle;
3. labels predate evaluator-bundle preparation or mutate after freeze;
4. manifest/evaluator/source digests mutate after freeze;
5. SUT output is generated at/before freeze or against another source/label digest;
6. normalized output does not match its declared digest;
7. Phase A sees analysis/recommendation events before freeze;
8. a new discovery-scored case lacks a frozen supplier/query context;
9. a context-relative SUT result claims a different context hash;
10. Phase B runtime introduces an unclassified decision-bearing output surface;
11. a control rerun attempts to regenerate/copy prior SUT artifacts instead of reusing only immutable truth/source inputs;
12. a fresh control backend run does not reproduce the exact frozen source-byte hash multiset before analysis.

## Scope boundary

223-FZ/RSL `32616312799` is still outside this task's accepted source path. Do not route it through 44-FZ to enlarge the corpus. Supplier/TKP acceptance and external procurement actions remain out of scope.

## Exit criteria before a second procurement / 30–50 cases

Do not grow the corpus until all are true:

- PR #60 product fixes are represented in the tested runtime revision;
- the same real procurement completes the frozen-truth control rerun;
- baseline vs fixed revision can be compared without changing source/truth labels;
- source/evaluator/freeze/SUT hashes remain tamper-evident;
- discovery is either legitimately context-scored or explicitly `NOT_SCORABLE`;
- normalization cannot silently drop material runtime claims;
- the three fixed defect classes are verified as fixed or re-opened with concrete evidence;
- remaining structured-fact recall is measured and classified;
- review-state behavior remains separate from SUT pass/fail;
- Product Owner can inspect the final artifacts before any corpus expansion.
