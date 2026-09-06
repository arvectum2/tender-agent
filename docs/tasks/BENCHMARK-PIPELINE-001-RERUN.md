# BENCHMARK-PIPELINE-001 — real calibration rerun

This runbook is the canonical local handoff after the first real Phase B exposed discovery-context and normalization-coverage gaps.

Use the same 44-FZ procurement first:

`0848300045426000620`

Do not reuse the first frozen calibration directory or its labels. Preserve that run as immutable calibration evidence.

## Stage A — source-only acquisition and context binding

Use a fresh unique case id and directory. Recommended id for the next rerun:

`calibration-44fz-0848300045426000620-rerun-20260906-01`

With the accepted Tender Agent backend already available at `http://127.0.0.1:8000`:

```bash
CASE_ID="calibration-44fz-0848300045426000620-rerun-20260906-01"
CASE_DIR="company_agent_runs/benchmark_calibration/${CASE_ID}"

python3 scripts/prepare_benchmark_calibration_phase_a.py \
  --registry-number 0848300045426000620 \
  --backend-url http://127.0.0.1:8000 \
  --case-dir "$CASE_DIR"

python3 scripts/benchmark_calibration.py bind-context \
  --case-dir "$CASE_DIR" \
  --case-id "$CASE_ID" \
  --registry-number 0848300045426000620 \
  --supplier-profile demo_data/tender_operator_agent/supplier_profile_electrical.json
```

The supplier profile is source-controlled benchmark context. Do not replace it with a guessed or hand-written local profile.

After `bind-context`, verify that the case still has no blind labels, no `frozen_label.json`, no SUT runtime output and no comparison/review artifacts. Compute SHA-256 of the regenerated `*-blind-evaluator-input.zip` and return that ZIP to the independent evaluator.

**STOP at this boundary. Do not run Tender Agent analysis before the independent labels are returned.**

The local handoff should report:

- repository HEAD;
- case id and absolute case directory;
- Phase A backend run id;
- source-file count and `source_bundle_sha256`;
- `discovery_context_sha256`;
- case-manifest SHA-256;
- evaluator-bundle SHA-256;
- evaluator ZIP path and SHA-256.

## Independent evaluator boundary

The evaluator receives only the regenerated context-bound evaluator ZIP and returns exactly:

- `blind_discovery_label.json`;
- `blind_document_truth.json`.

The local runner must not inspect those values to tune Tender Agent prompts, code, ranking, document extraction or normalization. The label ZIP SHA supplied by the evaluator is part of the handoff.

## Stage B — freeze, real SUT, audited normalization, comparator

After the independent label ZIP exists, run the repository-owned Phase B helper. It owns the critical ordering and refuses to create a retroactive freeze if the backend run was already analyzed.

```bash
CASE_ID="calibration-44fz-0848300045426000620-rerun-20260906-01"
CASE_DIR="company_agent_runs/benchmark_calibration/${CASE_ID}"
LABELS_ZIP="/absolute/path/to/blind-labels.zip"
LABELS_SHA256="<SHA256 supplied by the independent evaluator>"
RUNTIME_VERSION="llm_tender_operator_provider@$(git rev-parse HEAD)"

python3 scripts/run_benchmark_calibration_phase_b.py \
  --case-dir "$CASE_DIR" \
  --backend-url http://127.0.0.1:8000 \
  --runtime-version "$RUNTIME_VERSION" \
  --labels-zip "$LABELS_ZIP" \
  --labels-zip-sha256 "$LABELS_SHA256"
```

The helper performs, in order:

1. source/manifest/evaluator verification;
2. label ZIP hash/import and blind-label consistency validation;
3. verification that the Phase A run is still source-only when no freeze exists;
4. blind-label freeze;
5. real Tender Agent analysis of the exact Phase A run;
6. raw `sut_runtime_response.json` persistence;
7. repository-owned deterministic normalization and `normalization_audit.json`;
8. SUT/freeze/source hash binding verification;
9. deterministic comparator;
10. review routing;
11. complete Phase B artifact ZIP creation.

The document-analysis runtime is not the supplier-relative discovery/search SUT. Therefore this helper deliberately normalizes discovery as `UNCLEAR`; for a context-bound case, discovery remains `NOT_SCORABLE`. Do not fabricate a relevance result from document analysis. Discovery scoring belongs to DISCOVERY-QA-001 with a separately context-bound search/ranking output.

On success the marker is:

`BENCHMARK_CALIBRATION_PHASE_B_COMPLETE`

Return the complete stdout/result plus the generated `*-phase-b-artifacts.zip` and its reported SHA-256 to the Product Owner, then **STOP**.

Do not promote the case to gold locally, do not modify frozen truth, do not tune the system using the blind answers, do not start a second procurement, and do not scale to 30–50 cases until this rerun has been reviewed.
