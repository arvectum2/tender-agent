# Tender Agent — Current Roadmap

Updated: 2026-09-10
Canonical repository: `arvectum2/tender-agent`
Product-code baseline before this roadmap update: `81f77d5f97ae92733f5887136aa0c1f67ceb22ae`

## 1. Migration / recovery status

The previous GitHub account was blocked. The repository has been restored from the mirror into the new canonical GitHub owner `arvectum2`.

The git history is preserved through current product baseline `81f77d5f97ae92733f5887136aa0c1f67ceb22ae`, but GitHub-native issue/PR metadata did not migrate with the clone. Historical issue/PR numbers embedded in commit messages and older docs remain provenance references to the previous repository only.

Current canonical tracking recreated in this repository:

- #1 `BENCHMARK-PIPELINE-001 — resume frozen-truth control rerun`;
- #2 `DISCOVERY-QA-001 — procurement search quality benchmark and relevance hardening`;
- #3 `DOCUMENT-QA-001 — source-grounded document analysis quality benchmark`.

## 2. Executive product status

Tender Agent is past architecture recovery, Commercial MVP packaging, ARV-001 quality acceptance, real Mac mini read-only E2E, PILOT-001 analysis hardening, and Supplier Engine integration through `SUPPLIER-ENGINE-004`.

The real Supplier/TKP/Economics acceptance remains `WAITING_FOR_REAL_TKP / INPUT-BLOCKED`. Do not substitute synthetic quotations for real commercial acceptance; synthetic data remains valid only for regression and edge-case tests.

The active product phase is therefore:

**PROCUREMENT INTELLIGENCE QUALITY — SEARCH + DOCUMENTATION**

The Product Owner is not expected to manually label 30–50 procurements. Benchmark construction is AI-assisted and source-grounded, with blind independent evaluation and final Product-Owner verification.

## 3. Benchmark programme — what is already complete

`BENCHMARK-PIPELINE-001` has progressed materially beyond the initial design stage.

Completed in preserved git history:

- benchmark package and versioned contract;
- JSON schemas and validation;
- blind-evaluation ordering and anti-circularity controls;
- deterministic comparator and scorecard;
- review-state routing (`AI_CURATED_SILVER / NEEDS_REVIEW / HUMAN_VERIFIED_GOLD`);
- source-only real calibration Phase A;
- discovery-context binding;
- repository-owned audited Phase B normalization;
- safe one-command real Phase B runner;
- first methodologically clean real 44-FZ baseline;
- first benchmark-driven DOCUMENT-QA product fixes;
- dedicated frozen-truth control-rerun helper.

Canonical new-case order remains:

`public source bundle -> context-bound source-only evaluator bundle -> independent labels -> freeze -> Tender Agent output -> audited normalization -> comparator -> review routing`

The evaluator must not see Tender Agent ranking/report/output before its first-pass labels are frozen.

## 4. First real frozen baseline

Registry: `0848300045426000620`

Case id: `calibration-44fz-0848300045426000620-rerun-20260906-01`

Frozen baseline runtime revision: `33cbc7b285dad5faa0ad21b46cd5823499d58ea5`

Source bundle: 8 original public source files.

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

Discovery was correctly `NOT_SCORABLE` because no separately context-bound discovery SUT result was supplied.

The frozen source bundle, evaluator bundle, blind labels and `frozen_label.json` are immutable benchmark evidence and must not be regenerated for the control comparison.

## 5. Defects exposed by the baseline

The first clean baseline separated benchmark-harness defects from Tender Agent product defects and exposed four product-quality classes:

1. document parsing/source acquisition — EIS attachments may contain OOXML under misleading or misspelled suffixes;
2. source-role/entity resolution — organizer was propagated as `customer_name` instead of the actual customer;
3. reasoning/presentation contamination — unrelated legacy healthcare / ЕРН / СМЭВ / СЭМД / Минобороны / СВО claims leaked into an unrelated software procurement;
4. structured-fact coverage — normalized output exposed far fewer canonical procurement facts than frozen source truth.

Historical product fix commit `ab8ca415e1f08edfcb9edd28633d7958396af6d4` addressed the first three classes. The fourth class still needs post-fix measurement rather than assumption.

## 6. CURRENT GATE — frozen-truth control rerun

This is where work stopped before the GitHub account block.

Current product baseline already contains the control-rerun helper:

`81f77d5f97ae92733f5887136aa0c1f67ceb22ae — BENCHMARK-PIPELINE-001: add frozen-truth control rerun`

The next action is **not new coding and not a new procurement**. It is one local same-case replay against the exact frozen truth.

Run on the Mac mini against the preserved baseline artifacts:

```bash
python3 scripts/run_benchmark_control_rerun.py \
  --source-case-dir <clean-baseline-case-dir> \
  --output-dir <new-empty-control-dir> \
  --runtime-version 81f77d5f97ae92733f5887136aa0c1f67ceb22ae \
  --backend-url http://127.0.0.1:8000
```

Expected marker: `BENCHMARK_CONTROL_RUNTIME_READY`.

Then execute repository-owned `normalize-phase-b`, comparator and `route-review` exactly as documented in `docs/tasks/BENCHMARK-PIPELINE-001.md`.

Control-rerun methodology:

`existing frozen source/truth -> immutable copy + hash verification -> fresh source-only backend run -> exact source-byte equality -> Tender Agent output -> audited normalization -> comparator -> review routing`

Do not rerun Phase A, regenerate evaluator labels, edit frozen truth, or invent a discovery result.

## 7. Exit gate before corpus growth

Do not add a second procurement or grow toward 30–50 cases until all are true:

- post-fix product code is present in the tested runtime;
- the same procurement completes the frozen-truth control rerun;
- baseline and current revision are compared against identical source/truth;
- source/evaluator/freeze/SUT hashes remain tamper-evident;
- discovery is either genuinely context-scored or explicitly `NOT_SCORABLE`;
- normalization does not silently drop material runtime claims;
- the three fixed defect classes are verified as fixed or reopened with concrete evidence;
- remaining structured-fact recall is measured and classified;
- review-state semantics remain separate from SUT pass/fail;
- Product Owner inspects the control artifacts and decision before corpus expansion.

## 8. P0 after control gate

### #2 DISCOVERY-QA-001

After #1 passes, build the real 44-FZ discovery corpus through the blind benchmark pipeline. Target 30–50 AI-curated real cases, scalable to 50–100+.

Minimum metrics: Precision@5, Precision@10, Recall@K, nDCG/equivalent, top-K false-positive rate, missed-relevant rate, duplicate rate, status/deadline correctness where source-backed, explainability coverage.

Only benchmark-measured failures justify changes to subject/title/OKPD2/document/profile matching, aliases/transliteration, article/model/brand/manufacturer signals, category penalties, lifecycle/deadline filters, duplicate handling or score breakdown.

### #3 DOCUMENT-QA-001

After #1 passes, grow the truth-set corpus and measure factual accuracy, material-fact recall, grounding precision, unsupported material claim rate, contradiction rate, correct abstention and completeness classification.

Error taxonomy remains:

`source acquisition -> completeness -> parsing -> extraction -> scope/category -> evidence binding -> reasoning -> serialization/reporting`

D05 incomplete document sets and D06 `unsupported_layout` remain diagnostic targets inside this programme without weakening fail-closed behavior.

## 9. Supplier / Finance branch

Supplier Engine is implemented through `SUPPLIER-ENGINE-004`: position matching, public discovery, RU/EN identifier normalization, bounded product-page enrichment, comparison-ready offer set and controlled M-021/TKP handoff.

Real integrated acceptance remains parked until genuine TKP input exists:

`real supplier offers/TKP -> comparison -> economics -> contract risk -> GO/NO-GO -> owner decision record`

Public-offer dry runs and synthetic quotation regressions may continue, but they are not a substitute for real business acceptance.

## 10. First-wave lifecycle maturity

- Platform skeleton — implemented and operationally exercised.
- Intake & analysis — most mature; active quality-hardening target.
- Supplier Engine — implemented through SE-004; real TKP validation pending.
- Finance / risk / approval — implemented in bounded operator form; real integrated validation pending TKP.
- Bid package / completeness — canonical coverage exists.
- Submission — manual only.
- Outcome audit — follows manual submission path.

First-wave business target remains:

`tender -> analysis -> supplier-side -> economics/risk -> owner approval -> bid package -> manual submission -> receipt -> outcome`

## 11. Deferred / boundaries

Do not open yet:

- autonomous bid submission;
- ETP mutation/login automation;
- EDS/signature;
- supplier email automation;
- autonomous ordering/purchase;
- unattended external execution;
- broad agent autonomy;
- self-serve SaaS claims;
- 223-FZ expansion before the 44-FZ quality baseline is stable.

## 12. Updated critical path

```text
Supplier Engine 001..004 ✅
  ↓
REAL TKP ACCEPTANCE — WAITING FOR INPUT

PROCUREMENT INTELLIGENCE QUALITY
  ↓
BENCHMARK-PIPELINE core + first real baseline ✅
  ↓
first benchmark-driven DOCUMENT-QA fixes ✅
  ↓
frozen-truth control helper ✅
  ↓
SAME-CASE CONTROL RERUN ← CURRENT
  ↓
PRODUCT OWNER INSPECTION
  ↓
  ├────────────────────┐
  ↓                    ↓
DISCOVERY-QA (#2)   DOCUMENT-QA (#3)
30–50 corpus        truth-set growth
  └─────────┬──────────┘
            ↓
INTEGRATED SEARCH -> DOCS -> ANALYSIS ACCEPTANCE
            ↓
when genuine TKP arrives
            ↓
SUPPLIER -> ECONOMICS -> RISK -> GO/NO-GO
            ↓
BID PACKAGE -> MANUAL SUBMISSION -> OUTCOME
```

## 13. Immediate next step

Execute issue #1 locally on the Mac mini: reconcile local clone to exact canonical `arvectum2/tender-agent` main, locate the preserved frozen baseline case directory for registry `0848300045426000620`, run the same-case frozen-truth control replay, then return the generated comparison/review artifacts for Product Owner inspection.

No further product-code change should be made before that measurement unless the local migration/reconciliation itself exposes a concrete blocker.