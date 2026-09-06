# BENCHMARK-PIPELINE-001 (#52)

## Status

The shared blind benchmark contract is implemented on `1.1.0`, and the first real 44-FZ calibration completed the required source -> blind label -> freeze -> SUT ordering. The real Phase B run exposed two benchmark-harness gaps, so #52 remains open and corpus growth is still blocked.

Canonical completed merges:

- PR `#56` — blind benchmark contract hardening; merge `dec002926f0a996c537c854548e3636e905140ba`; CI PASS.
- PR `#57` — safe source-only real-calibration Phase A; merge `0958505576cdcd8a7edeb0a5d4973bf07f43cf76`; CI PASS.
- docs baseline after Phase A helper: `c22803c4b38400bf7be2393c5c66c28f6d754288`.

Current hardening after real Phase B adds discovery-context binding and repository-owned runtime normalization. Do not mark this increment complete until its PR/CI passes and the same procurement is rerun as a fresh uniquely identified calibration case.

## First real calibration evidence

Primary real case:

- law: 44-FZ;
- registry number: `0848300045426000620`;
- source bundle: eight original public files acquired through the accepted read-only path;
- Phase A produced no Tender Agent analysis before blind evaluation;
- independent labels were frozen before SUT generation;
- the real SUT output was generated after freeze and remained bound to the frozen source and label digests.

The original calibration run must be preserved as evidence and must not have its frozen truth rewritten.

### Finding 1 — discovery context was not bound

The independent discovery judgment was supplier-relative, but the document-analysis SUT run had no loaded supplier profile. Contract `1.1.0` originally froze source data and labels but did not explicitly bind the supplier/query context used to interpret relevance. The resulting discovery mismatch was therefore not an apples-to-apples product score.

Hardening rule for every new real discovery-scored case:

- bind a complete sanitized supplier-profile snapshot before blind evaluation;
- bind its canonical SHA-256 plus query/candidate-selection/source/law/`as_of` semantics into `procurement.benchmark_discovery_context`;
- let that context flow into the evaluator bundle and therefore the frozen manifest/evaluator digests;
- score discovery only when the SUT artifact declares the exact same `discovery_context_sha256`;
- otherwise return `NOT_SCORABLE`, not `MISMATCH`.

The context is prepared with:

```bash
python3 scripts/benchmark_calibration.py bind-context \
  --case-dir <fresh-phase-a-case-dir> \
  --case-id <new-unique-calibration-case-id> \
  --supplier-profile demo_data/tender_operator_agent/supplier_profile_electrical.json
```

This command must run after source-only Phase A and before the evaluator ZIP is sent for blind labeling.

### Finding 2 — Phase B normalization silently omitted runtime claims

The first local Phase B projector normalized only a small subset of the real runtime response. That made document false negatives mix true Tender Agent misses with normalizer coverage omissions.

The repository now owns the calibration projector in `scripts/benchmark_calibration.py normalize-phase-b` / `src/modules/benchmark_pipeline/calibration.py`. It:

- maps known canonical facts deterministically;
- maps explicit `НМЦК:` economics output to `initial_max_price_rub`;
- preserves unmapped material economics/requirement/risk claims as `runtime_claim.*` facts;
- records intentionally ignored questions/operator instructions/workflow decisions in `normalization_audit.json`;
- fails closed when a new `final_recommendation` output surface has no classification;
- binds the audit digest into `tender_agent_output_ref`;
- derives `produced_at` from the actual analysis-completion event when available.

This is required so unsupported or contaminated material claims become visible to the comparator instead of disappearing before scoring.

### Finding 3 — genuine SUT quality failures were also observed

Independently of the normalization gap, the real runtime contained unrelated domain claims and propagated the procurement organizer as `customer_name` instead of the actual customer. Keep these as DOCUMENT-QA evidence. They are product-quality failures, not a reason to rewrite frozen independent truth.

The first calibration also showed that free-text truth values intended for exact deterministic comparison must be source-canonical rather than evaluator paraphrases. Do not mutate the already frozen truth. In the fresh rerun, the independent evaluator should copy canonical source wording for exact-text fields and use structured facts for semantic scope/category assertions.

## Review-state semantics

`AI_CURATED_SILVER` is a state of the independent truth set, not a Tender Agent pass/fail flag. A mechanically classifiable SUT error can coexist with silver truth. `NEEDS_REVIEW` is reserved for benchmark/source uncertainty or unclassified material disagreement. Product Owner promotion to `HUMAN_VERIFIED_GOLD` changes review metadata only and never rewrites frozen truth.

## Anti-circularity contract

Canonical order:

`public source bundle -> context-bound source-only evaluator bundle -> independent labels -> freeze -> Tender Agent output -> audited normalization -> comparator -> review routing`

Fail closed when:

1. evaluator input contains SUT/ranking/report leakage;
2. evidence points outside the source bundle;
3. labels predate evaluator-bundle preparation or mutate after freeze;
4. manifest/evaluator/source digests mutate after freeze;
5. SUT output is generated at/before freeze or against another source/label digest;
6. normalized output does not match its declared digest;
7. Phase A sees analysis/recommendation events before freeze;
8. a new real discovery case lacks a frozen supplier/query context;
9. a context-relative SUT result claims a different context hash;
10. Phase B runtime introduces an unclassified decision-bearing output surface.

## Next real rerun

Use the same procurement first. Do not add a second case until this rerun is clean.

1. Run `scripts/prepare_benchmark_calibration_phase_a.py` into a **fresh** case directory.
2. Run `scripts/benchmark_calibration.py bind-context` with a **new unique case id** and the source-controlled supplier profile.
3. Send only the regenerated context-bound evaluator ZIP to the independent evaluator.
4. Freeze the new labels.
5. Run the real Tender Agent after freeze.
6. Save its raw response as `sut_runtime_response.json`.
7. Run repository-owned `normalize-phase-b`.
8. Run comparator and review routing.
9. Inspect the artifacts before considering a second/third 44-FZ calibration case.

If the document-analysis runtime has no separately context-bound search/relevance result, do not fabricate one: omit `--discovery-result`, which normalizes discovery as `UNCLEAR` and leaves context-relative discovery unscored. DISCOVERY-QA can later supply a real search/ranking result bound to the same context.

## Scope boundary

223-FZ/RSL `32616312799` is not part of this task's accepted source path. Do not route it through 44-FZ merely to enlarge the corpus. Supplier/TKP acceptance and external procurement actions also remain out of scope.

## Exit criteria before 30–50 cases

Do not grow the corpus until all are true:

- current hardening is merged with green CI;
- at least one fresh real calibration case completes the full blind order with context binding and audited normalization;
- source/evaluator/freeze/SUT hashes detect tampering and mismatch;
- discovery becomes either legitimately scored under an identical frozen context or explicitly `NOT_SCORABLE`;
- normalization cannot silently drop material final runtime claims;
- comparator outcomes on real data distinguish true SUT errors from harness omissions;
- review-state behavior remains separate from SUT pass/fail;
- Product Owner can inspect the final artifacts and promote verified truth to gold without rewriting it.
