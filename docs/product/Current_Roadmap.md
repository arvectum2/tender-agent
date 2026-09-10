# Tender Agent — Current Roadmap

Updated: 2026-09-10
Canonical repository: `arvectum2/tender-agent`
Current canonical main at this status update follows the migration-doc sequence after product baseline `81f77d5f97ae92733f5887136aa0c1f67ceb22ae`.

## 1. Migration / recovery status

The previous GitHub account was blocked. The repository has been restored from the mirror into the new canonical GitHub owner `arvectum2`.

The git history is preserved through product baseline `81f77d5f97ae92733f5887136aa0c1f67ceb22ae`; GitHub-native issue/PR metadata did not migrate with the clone. Historical issue/PR numbers embedded in commits and older docs are provenance references only.

Current canonical tracking:

- #1 `BENCHMARK-PIPELINE-001 — resume frozen-truth control rerun`;
- #2 `DISCOVERY-QA-001 — procurement search quality benchmark and relevance hardening`;
- #3 `DOCUMENT-QA-001 — source-grounded document analysis quality benchmark`.

## 2. Executive product status

Tender Agent is past architecture recovery, Commercial MVP packaging, ARV-001 quality acceptance, real Mac mini read-only E2E, PILOT-001 analysis hardening, and Supplier Engine integration through `SUPPLIER-ENGINE-004`.

The real Supplier/TKP/Economics acceptance remains `WAITING_FOR_REAL_TKP / INPUT-BLOCKED`. Do not substitute synthetic quotations for real commercial acceptance.

The active product phase remains:

**PROCUREMENT INTELLIGENCE QUALITY — SEARCH + DOCUMENTATION**

The Product Owner is not expected to manually label 30–50 procurements. Benchmark construction is AI-assisted and source-grounded, with blind independent evaluation and final Product-Owner verification.

## 3. Benchmark programme — completed foundation

`BENCHMARK-PIPELINE-001` already includes:

- versioned benchmark contract and schemas;
- blind-evaluation ordering and anti-circularity controls;
- deterministic comparator and scorecard;
- review-state routing (`AI_CURATED_SILVER / NEEDS_REVIEW / HUMAN_VERIFIED_GOLD`);
- real source-only Phase A;
- discovery-context binding;
- audited Phase B normalization;
- safe real Phase B runner;
- first methodologically clean 44-FZ baseline;
- first benchmark-driven DOCUMENT-QA fixes;
- frozen-truth same-case control-rerun helper.

Canonical new-case order:

`public source bundle -> context-bound source-only evaluator bundle -> independent labels -> freeze -> Tender Agent output -> audited normalization -> comparator -> review routing`

## 4. First real frozen baseline

Registry: `0848300045426000620`

Case: `calibration-44fz-0848300045426000620-rerun-20260906-01`

Frozen baseline runtime revision: `33cbc7b285dad5faa0ad21b46cd5823499d58ea5`

Source bundle: 8 original public files.

Baseline document score:

- TP: 2;
- FP: 1;
- FN: 24;
- precision: 0.6667;
- recall: 0.0769;
- F1: 0.1379;
- 14 material runtime extras;
- contradiction: `customer_name`;
- review: `NEEDS_REVIEW / UNCLASSIFIED_MATERIAL_DISAGREEMENT`.

Discovery was correctly `NOT_SCORABLE` because no separately context-bound discovery SUT result existed.

The source bundle, evaluator bundle, blind labels and `frozen_label.json` are immutable benchmark evidence.

## 5. Baseline defect classes and first fixes

The baseline exposed four product-quality classes:

1. document parsing/source acquisition — EIS attachments may contain OOXML under misleading/misspelled suffixes;
2. source-role/entity resolution — organizer propagated as `customer_name` instead of actual customer;
3. reasoning/presentation contamination — unrelated legacy healthcare / ЕРН / СМЭВ / СЭМД / Минобороны / СВО claims leaked into unrelated software procurement;
4. structured-fact coverage — normalized output exposed far fewer canonical procurement facts than frozen truth.

Historical product fix commit `ab8ca415e1f08edfcb9edd28633d7958396af6d4` attempted to address the first three classes. In particular, it added explicit customer extraction and source-bound filtering of legacy software output. These fixes must be judged by the frozen-truth control, not by unit tests alone.

## 6. Frozen-truth control rerun — COMPLETED, GATE NOT PASSED

The same-case control rerun was completed on 2026-09-10 against canonical runtime revision `7d78cb5d49177fa8a1e07c9cbb444a65be148e01`.

Integrity / methodology checks passed:

- repo remote: `https://github.com/arvectum2/tender-agent.git`;
- tracked tree clean;
- product-code diff after `81f77d5...`: migration/docs only;
- control status: `BENCHMARK_CONTROL_RUNTIME_READY`;
- exact source-byte equality: PASS, 8/8;
- same immutable frozen truth reused;
- no Phase A / truth regeneration;
- discovery remained `NOT_SCORABLE` rather than fabricated.

Control document result:

- TP: 2;
- FP: 1;
- FN: 24;
- precision: 0.6667;
- recall: 0.0769;
- F1: 0.1379;
- contradiction: `customer_name` still present;
- actual `customer_name`: `МКЦ Одинцовского ГО`;
- expected `customer_name`: `МК "Служба кладбищ" Одинцовского ГО`;
- runtime extras: 13;
- review: `NEEDS_REVIEW / UNCLASSIFIED_MATERIAL_DISAGREEMENT`.

Therefore the control rerun is methodologically valid but **does not demonstrate the expected product-quality improvement**. The scored document metrics are unchanged from baseline, and the customer/organizer contradiction survives.

The corpus-growth gate remains CLOSED.

## 7. Product Owner inspection decision

Decision: **DO NOT CLOSE #1. DO NOT GROW TO A SECOND PROCUREMENT YET.**

What is already proven:

- benchmark harness can perform a same-case frozen-truth rerun safely;
- source/truth integrity is preserved;
- comparator/review routing remain operational.

What is not proven:

- fix #1 OOXML/source parsing effectiveness in this control;
- fix #2 customer/organizer correction — current evidence indicates it is still ineffective on the real case;
- fix #3 legacy contamination removal — cannot be accepted from the aggregate count alone because the 13 preserved runtime extras were not semantically inspected;
- structured-fact coverage improvement — no improvement is visible in scored recall; 24/26 expected fields remain missed.

The next work is therefore a **diagnostic comparison on the same control artifacts**, not corpus expansion and not blind new tuning.

## 8. CURRENT GATE — diagnose why the post-fix runtime did not improve the frozen score

Before changing product code, inspect baseline-vs-control artifacts and the live runtime path.

Required diagnostic questions:

1. Did the backend process actually load the post-`ab8ca415...` DOCUMENT-QA runtime patch, rather than a stale process/import state?
2. Where exactly does control `customer_name = МКЦ Одинцовского ГО` originate: source extraction, intermediate normalized entity, fallback, serialization, or normalization projector?
3. Did the explicit customer extractor run on the source containing `МК "Служба кладбищ" Одинцовского ГО`? If not, why not?
4. Which of the baseline 14 runtime extras disappeared in the control (14 -> 13), and do any healthcare/ЕРН/СМЭВ/СЭМД/Минобороны/СВО contaminants remain?
5. Is low recall caused by Tender Agent failing to extract facts, or by `normalize-phase-b` failing to project already-present runtime facts into canonical benchmark fields?
6. For each of the 24 FN fields, classify the loss at `source acquisition -> parsing -> extraction -> reasoning -> serialization -> benchmark normalization`.

No product fix should be merged until this attribution is known.

## 9. Exit gate before corpus growth

Do not add a second procurement or grow toward 30–50 cases until all are true:

- the surviving `customer_name` contradiction is traced to a precise stage and fixed or correctly reclassified;
- legacy-contamination status is verified from actual runtime claims, not aggregate counts;
- the 24 false negatives are stage-classified;
- benchmark normalization is proven not to hide already-extracted canonical facts;
- any required product/normalizer fix is rerun against the same immutable frozen truth;
- the rerun shows the intended defect correction without new unsupported material claims;
- Product Owner inspects the updated artifacts and explicitly opens corpus growth.

## 10. P0 after #1 gate

### #2 DISCOVERY-QA-001

After #1 passes, build the real 44-FZ discovery corpus through the blind benchmark pipeline. Target 30–50 AI-curated real cases, scalable to 50–100+.

Minimum metrics: Precision@5, Precision@10, Recall@K, nDCG/equivalent, top-K false-positive rate, missed-relevant rate, duplicate rate, status/deadline correctness where source-backed, explainability coverage.

### #3 DOCUMENT-QA-001

After #1 passes, grow the document truth-set corpus and measure factual accuracy, material-fact recall, grounding precision, unsupported material claim rate, contradiction rate, correct abstention and completeness classification.

Error taxonomy:

`source acquisition -> completeness -> parsing -> extraction -> scope/category -> evidence binding -> reasoning -> serialization/reporting -> benchmark normalization`

D05 incomplete document sets and D06 `unsupported_layout` remain diagnostic targets without weakening fail-closed behavior.

## 11. Supplier / Finance branch

Supplier Engine remains implemented through `SUPPLIER-ENGINE-004`. Real integrated acceptance remains parked until genuine TKP input exists:

`real supplier offers/TKP -> comparison -> economics -> contract risk -> GO/NO-GO -> owner decision record`

## 12. Boundaries

No autonomous bid submission, ETP mutation/login, EDS/signature, supplier email automation, autonomous ordering/purchase, or unattended external execution. 223-FZ source expansion remains after stable 44-FZ quality acceptance.

## 13. Updated critical path

```text
Supplier Engine 001..004 ✅
  ↓
REAL TKP ACCEPTANCE — WAITING FOR INPUT

PROCUREMENT INTELLIGENCE QUALITY
  ↓
BENCHMARK PIPELINE + first frozen baseline ✅
  ↓
first DOCUMENT-QA fixes ✅
  ↓
frozen-truth control rerun ✅ methodology
  ↓
CONTROL QUALITY RESULT ❌ unchanged metrics / customer contradiction persists
  ↓
BASELINE-vs-CONTROL DIAGNOSTIC ← CURRENT
  ↓
smallest evidence-backed product/normalizer fix
  ↓
same frozen-truth rerun again
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
```

## 14. Roadmap principle

A benchmark pipeline is only useful if it can distinguish harness defects from product defects. The first valid control has now done that: infrastructure integrity passed, but product-quality improvement was not demonstrated. Stay on the same frozen case until the discrepancy is attributed and corrected; only then scale the corpus.