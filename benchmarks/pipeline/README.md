# BENCHMARK-PIPELINE-001

Shared benchmark contract and blind-evaluation workflow for Tender Agent discovery and document-analysis QA.

## Canonical contract

Contract version: `1.1.0`.

Machine-readable schema:
`benchmarks/pipeline/schema/1.1.0/benchmark-artifacts.schema.json`.

The previous `1.0.0` schema remains in the repository as historical evidence; new calibration artifacts use `1.1.0`.

Artifact classes:

- `case_manifest`
- `evaluator_bundle`
- `blind_discovery_label`
- `blind_document_truth`
- `frozen_label`
- `tender_agent_output_ref`
- `normalized_sut_output`
- `comparison_result`
- `review_state`
- `aggregate_scorecard`

Review states are explicit and machine-readable:

- `AI_CURATED_SILVER`
- `NEEDS_REVIEW`
- `HUMAN_VERIFIED_GOLD`

## Anti-circularity invariant

The enforced order is:

`public source bundle -> evaluator bundle -> blind labels -> freeze -> Tender Agent output -> comparator -> review routing`

The evaluator bundle is reconstructed from source-only manifest fields. SUT-derived keys such as ranking, scores, reports, extracted facts, artifact references and Tender Agent outputs are rejected recursively.

A freeze receipt binds all first-pass truth to immutable digests:

- source bundle;
- case manifest;
- evaluator bundle;
- blind discovery label;
- blind document truth;
- combined label set.

Tender Agent output is accepted only when it:

1. belongs to the same case and source bundle;
2. is explicitly bound to the frozen label-set digest;
3. has a normalized-output digest matching the referenced output;
4. was produced strictly after the blind-label freeze timestamp.

Changing the evaluator bundle, label, truth or manifest after freeze fails validation rather than silently changing benchmark truth.

## Discovery and document semantics

Discovery labels are exactly:

- `RELEVANT`
- `PARTIALLY_RELEVANT`
- `IRRELEVANT`
- `UNCLEAR`

`UNCLEAR` is not scored as a discovery error. Document truth supports:
`ASSERTED`, `UNKNOWN`, `INSUFFICIENT_EVIDENCE`, and `CONFLICTING_EVIDENCE`.

The deterministic comparator records:

- discovery exact match/mismatch or `NOT_SCORABLE`;
- document TP/FP/FN;
- contradictions;
- missed asserted facts;
- correct abstentions;
- unsupported/unresolved assertions;
- unlabeled SUT extras;
- precision, recall and F1.

Evaluator abstention is not converted into false benchmark certainty: an assertion against `UNKNOWN`, `INSUFFICIENT_EVIDENCE` or conflicting truth is marked unresolved rather than automatically counted as a false positive. Unlabeled SUT extras are unscored. Material unresolved assertions are routed for review.

A mechanically classifiable Tender Agent error (for example, a wrong frozen fact value) is scored as a SUT error but does **not** by itself invalidate a high-confidence benchmark label. This separation prevents the tested system from poisoning the independent truth set.

### Discovery-context binding

The first real Phase B calibration showed that relevance is not an intrinsic property of a procurement: it is relative to the supplier/query context used by the evaluator and the tested search/ranking path.

For every new real case whose discovery label is intended to be scored, bind `procurement.benchmark_discovery_context` into `case_manifest.json` **before** blind evaluation. The context contains the complete sanitized supplier-profile snapshot, its canonical digest, candidate-selection mode, registry number, source/law, optional query and an `as_of` timestamp. Because it is copied into the evaluator bundle and the manifest/evaluator bundle are frozen, the discovery semantics cannot drift after labeling.

A context-bound discovery label is scored only when `tender_agent_output_ref.artifact_refs.discovery_context_sha256` equals the frozen evaluator context digest. A missing or different context yields `NOT_SCORABLE`, not a false Tender Agent mismatch. Historical v1.1 artifacts without `benchmark_discovery_context` retain legacy behavior for compatibility and must not be used as new real discovery calibration evidence.

Use the calibration helper between source acquisition and independent evaluation:

```bash
python3 scripts/benchmark_calibration.py bind-context \
  --case-dir <fresh-phase-a-case-dir> \
  --case-id <new-unique-calibration-case-id> \
  --supplier-profile demo_data/tender_operator_agent/supplier_profile_electrical.json
```

The regenerated blind-evaluator ZIP is the only evaluator input that should be labeled/frozen.

### Repository-owned Phase B normalization

The first real Phase B calibration also showed that an ad-hoc local projector can silently drop claim-bearing runtime output and turn normalizer omissions into apparent document false negatives.

`scripts/benchmark_calibration.py normalize-phase-b` is the repository-owned projector for real calibration runs. It:

- maps known canonical runtime facts deterministically;
- extracts a structured NMCK value from the explicit `НМЦК:` economics line;
- preserves unmapped material recommendation/economics/risk claims as `runtime_claim.*` facts so the comparator can surface them as unclassified material extras;
- records questions, operator instructions and workflow decisions as intentionally ignored non-assertions in `normalization_audit.json`;
- fails closed when `final_recommendation` introduces an unclassified output surface;
- binds the normalization audit digest into `tender_agent_output_ref`;
- uses the actual analysis-completion event time where available.

If no separately produced discovery result is supplied, the analysis runtime normalizes discovery as `UNCLEAR`; a context-bound discovery case therefore stays unscored rather than pretending the document-analysis run executed supplier-relative search scoring.

## Review routing

`NEEDS_REVIEW` is used for benchmark-quality uncertainty, including:

- evaluator confidence below threshold;
- material source conflict;
- weak source provenance;
- material `UNKNOWN` / `INSUFFICIENT_EVIDENCE`;
- material disagreement that cannot be mechanically classified;
- schema/consistency failure.

Otherwise the independently labeled case remains `AI_CURATED_SILVER`. Only explicit Product Owner approval can create `HUMAN_VERIFIED_GOLD`; promotion changes review metadata, not frozen source truth.

`AI_CURATED_SILVER` describes the independent truth-set state, not a Tender Agent pass. A mechanically classifiable bad SUT result can coexist with silver truth. Unclassified material runtime claims are instead routed through the comparator/review reasons.

## CLI and batchability

The contract CLI is `scripts/benchmark_pipeline.py`.

It supports contract validation, source-file verification, blind-bundle preparation, label freeze, comparison, review routing, Product Owner promotion, scorecard generation and batch comparison.

Real calibration additionally uses `scripts/benchmark_calibration.py` for pre-label discovery-context binding and post-freeze runtime normalization/audit.

A batch case directory uses:

```text
case_manifest.json
evaluator_bundle.json
blind_discovery_label.json
blind_document_truth.json
frozen_label.json
sut_runtime_response.json       # real calibration only
normalization_audit.json        # real calibration only
tender_agent_output_ref.json
normalized_sut_output.json
comparison_result.json          # generated
review_state.json               # generated
```

`batch-compare` processes already-frozen cases without Product Owner per-case orchestration and writes an aggregate scorecard. It does not collect procurements or perform external procurement actions.

## Calibration gate

Repository tests exercise the original three workflow calibration paths plus regressions for the two gaps found by the first real Phase B run:

1. matching, high-confidence source truth -> `AI_CURATED_SILVER` -> explicit Product Owner gold promotion;
2. low-confidence/insufficient source evidence plus material unclassified SUT assertions -> `NEEDS_REVIEW`;
3. mechanically classifiable Tender Agent error -> scored SUT failure while independent truth remains `AI_CURATED_SILVER`;
4. supplier-relative discovery cannot be scored without an exact frozen context binding;
5. decision-bearing runtime claims cannot disappear silently during normalization.

Synthetic fixtures are workflow evidence, not procurement ground truth.

Do **not** scale to 30–50 procurements yet.

The first real 44-FZ calibration (`0848300045426000620`) successfully validated source hashing, blind-label freeze ordering and post-freeze SUT binding, but exposed discovery-context and normalization-coverage gaps. Preserve that run as calibration evidence; do not rewrite its frozen truth. Run a fresh uniquely identified iteration after this hardening, then add at most a second/third 44-FZ case only after the rerun is clean.

223-FZ/RSL source expansion remains out of scope for BENCHMARK-PIPELINE-001. Do not route a 223-FZ case through the accepted 44-FZ path merely to enlarge the corpus.

## Local Mac mini boundary

GitHub/CI owns the contract, context-binding logic, schemas, comparator, normalization rules, review logic, batch tooling and offline tests.

Mac mini/Codex is needed only where local execution is genuinely required:

- acquire the original public procurement artifacts through the accepted Tender Agent runtime/source path;
- compute and persist real file hashes/manifests;
- bind the selected source-controlled supplier profile before blind evaluation;
- run the real Tender Agent **after** the independent label freeze;
- persist the actual runtime response and run the repository-owned normalization/comparator commands on the 1–3 real cases.

The local runner is not a semantic source of truth and must not see or rewrite the blind evaluator answer on behalf of Tender Agent.
