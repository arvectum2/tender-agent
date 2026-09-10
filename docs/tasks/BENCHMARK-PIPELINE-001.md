# BENCHMARK-PIPELINE-001 — canonical issue #1

> Repository migration note (2026-09-10): canonical repository is now `arvectum2/tender-agent`. Historical issue `#52` and PR numbers `#56/#57/#58/#60/#61` refer to the previous GitHub repository/account and are retained only as git-history provenance.

## Status

The blind benchmark contract and the first methodologically clean real 44-FZ baseline are complete. The pipeline has already exposed concrete Tender Agent product defects, the first DOCUMENT-QA fixes were merged, and the current gate is a **same-case control rerun against the exact same frozen truth**.

Current canonical issue: `#1`.

Current product-code baseline before migration-doc commits: `81f77d5f97ae92733f5887136aa0c1f67ceb22ae`.

Historical canonical merges preserved in git history:

- old PR `#56` — blind benchmark contract hardening; merge `dec002926f0a996c537c854548e3636e905140ba`; CI PASS;
- old PR `#57` — safe source-only real-calibration Phase A; merge `0958505576cdcd8a7ed0a5d4973bf07f43cf76`; CI PASS;
- old PR `#58` — discovery-context binding + repository-owned audited normalization; merge `b8d22ce044c02fa034f7f13d8a260f55dbd9f2f1`; CI PASS;
- old PR `#60` — first benchmark-driven DOCUMENT-QA product fixes; merge `ab8ca415e1f08edfcb9edd28633d7958396af6d4`; CI PASS;
- old PR `#61` — frozen-truth control-rerun helper; merge `81f77d5f97ae92733f5887136aa0c1f67ceb22ae`.

Do not grow the corpus until the control rerun is complete and inspected.

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
- review: `NEEDS_REVIEW / UNCLASSIFIED_MATERIAL_DISAGREEMENT`.

This case is the frozen control baseline. Its source files, evaluator bundle, blind labels and `frozen_label.json` must not be regenerated or edited for the post-fix comparison.

## Product defects exposed by the baseline

The clean baseline exposed four product-quality classes:

1. **document parsing/source acquisition** — EIS attachments can contain OOXML under misleading or misspelled suffixes;
2. **source-role/entity resolution** — organizer was propagated as `customer_name` instead of the actual customer;
3. **reasoning/presentation contamination** — legacy healthcare/ЕРН/СМЭВ/СЭМД/Минобороны/СВО templates leaked into an unrelated software procurement;
4. **structured-fact coverage** — normalized product output exposed far fewer canonical procurement facts than frozen source truth contains.

Historical PR #60 / commit `ab8ca415e1f08edfcb9edd28633d7958396af6d4` addresses the first three classes. The fourth class must be measured again after those fixes rather than guessed from the old baseline.

## Frozen-truth control rerun — CURRENT

The control rerun is **not** a new calibration case and must not execute Phase A again. It reuses immutable benchmark inputs from the clean baseline and produces only a fresh SUT side of the comparison.

Repository helper:

```bash
python3 scripts/run_benchmark_control_rerun.py \
  --source-case-dir <clean-baseline-case-dir> \
  --output-dir <new-empty-control-dir> \
  --runtime-version 81f77d5f97ae92733f5887136aa0c1f67ceb22ae \
  --backend-url http://127.0.0.1:8000
```

The helper fails closed before analysis unless:

- the original case manifest, evaluator bundle, blind labels and freeze receipt validate;
- the current case manifest hash still matches the digest bound by `frozen_label.json`;
- source files still match frozen manifest hashes;
- only immutable benchmark inputs are copied into the new control directory;
- copied immutable artifacts remain byte-identical;
- the fresh backend run has not begun analysis;
- the fresh backend source-file SHA-256 multiset exactly equals the frozen source-file hash multiset.

Only after those checks does it call Tender Agent analysis and save `sut_runtime_response.json`. It never generates evaluator input, labels or a freeze receipt.

Expected marker:

`BENCHMARK_CONTROL_RUNTIME_READY`

## Post-runtime normalization and comparison

For the current document-only control, omit `--discovery-result` unless a genuine context-bound discovery result exists.

```bash
CONTROL=<new-empty-control-dir>
RUNTIME_VERSION=81f77d5f97ae92733f5887136aa0c1f67ceb22ae

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

Preserve both the original baseline directory and the new control directory. Inspect baseline revision `33cbc7...` versus the current post-fix runtime under exactly the same source and frozen truth.

## Discovery-context rule

Every new discovery-scored case must bind a complete sanitized supplier/query context before blind evaluation. Discovery is scorable only when the SUT artifact declares the exact same `discovery_context_sha256`; otherwise the comparator outcome is `NOT_SCORABLE`, not `MISMATCH`.

The current control does not invent a discovery result. Its purpose is DOCUMENT-QA regression measurement.

## Normalization rule

Repository-owned `scripts/benchmark_calibration.py normalize-phase-b` remains mandatory. It maps known canonical facts, preserves unmapped material claims as runtime facts, records intentionally ignored non-material workflow surfaces, fails closed on unclassified decision-bearing output, binds the normalization audit digest and keeps unsupported/contaminated material claims visible to the comparator.

## Review-state semantics

`AI_CURATED_SILVER` describes independent truth quality, not whether Tender Agent passed. `NEEDS_REVIEW` is for benchmark/source uncertainty or unclassified material disagreement. `HUMAN_VERIFIED_GOLD` requires explicit Product Owner review and changes review metadata only; it never rewrites frozen truth.

## Anti-circularity contract

Canonical new-case order:

`public source bundle -> context-bound source-only evaluator bundle -> independent labels -> freeze -> Tender Agent output -> audited normalization -> comparator -> review routing`

Control-rerun order:

`existing frozen source/truth -> immutable copy + hash verification -> fresh source-only backend run -> exact source-byte equality -> Tender Agent output -> audited normalization -> comparator -> review routing`

Fail closed on leakage, evidence outside bundle, pre-freeze SUT output, digest mutation, discovery-context mismatch, unclassified decision-bearing output, copied prior SUT artifacts, or source-byte mismatch.

## Scope boundary

223-FZ/RSL `32616312799` remains outside this accepted 44-FZ path. Supplier/TKP acceptance and external procurement actions remain out of scope.

## Exit criteria before a second procurement / 30–50 cases

Do not grow the corpus until all are true:

- post-fix product code is present in the tested runtime;
- the same real procurement completes the frozen-truth control rerun;
- baseline vs fixed revision is compared without changing source/truth labels;
- source/evaluator/freeze/SUT hashes remain tamper-evident;
- discovery is either legitimately context-scored or explicitly `NOT_SCORABLE`;
- normalization cannot silently drop material runtime claims;
- the three fixed defect classes are verified as fixed or reopened with concrete evidence;
- remaining structured-fact recall is measured/classified;
- review-state behavior remains separate from SUT pass/fail;
- Product Owner inspects final artifacts before corpus expansion.
