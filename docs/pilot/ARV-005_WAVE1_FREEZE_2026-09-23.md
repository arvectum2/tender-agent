# ARV-005 Wave 1 freeze — 2026-09-23

## Freeze point

Wave 0 passed on exact main `189799ce4cc44a4e83e75169d689613bd14b55bf`.

Local controlled-provider proof:
- provider: `openai_compatible`
- model: `arvectum-gemma4-12b-it-qat-q4_0` on llama.cpp loopback
- embeddings: `Qwen3-Embedding-4B` on loopback
- four core sections: 4/4 schema-valid
- elapsed: 250.62s
- review status: `needs_human_review`
- trace count: 4

No counted real-procurement model output was inspected before this selection was frozen.

## Deterministic Wave 1 selection rule

Use public 44-FZ search-card metadata only. Do not inspect model outputs to choose cases.

1. **Simple exact-product case** — recent direct public 44-FZ result explicitly titled as automatic-breaker supply.
2. **Multi-position/specification proxy** — first active, direct-search-card `Поставка электротехнической продукции` result with NMCK at least 100,000 RUB in publication-date-desc order.
3. **Higher-materiality contract/risk proxy** — first active, direct-search-card cable-supply result with NMCK at least 1,000,000 RUB in publication-date-desc order.

Selection is a technical diversity proxy, not a claim about actual legal/commercial risk before documents are analyzed.

## Frozen registry numbers

| Slot | Registry number | Search-card title | NMCK | Search-card status |
|---|---|---|---:|---|
| W1-A simple | `0342200026726000083` | Поставка автоматических выключателей | 44,133.60 RUB | Работа комиссии |
| W1-B multi-position proxy | `0333300006126000121` | Поставка электротехнической продукции (Лот №1) | 133,766.60 RUB | Подача заявок |
| W1-C higher-materiality proxy | `0301200067526000236` | Поставка кабельной продукции | 1,361,068.80 RUB | Подача заявок |

Exact-number public EIS search returned all three before freeze.

## Counted-run rule

For each frozen case:
- acquire only through read-only public paths;
- persist source/document completeness evidence;
- run deterministic extraction + Decision Core;
- invoke the local controlled LLM path;
- require explicit `llm_invoked` / provider/model / validation or fallback provenance;
- generate the report if the source package is sufficient;
- record every operator correction and technical defect;
- perform no submission, signing, supplier/customer outreach or authenticated consequential ETP action.

A source-bound acquisition blocker counts as a recorded technical pilot outcome but not as a successful analysis.

## Wave 1 execution evidence

- W1-A `0342200026726000083`: reused the already acquired six-document public package (`toa-run-20260923092953-986c09`).
- Initial fallback was traced to the isolated pilot PostgreSQL prerequisite being stopped, not to a missing controlled-LLM code path.
- After restoring that local prerequisite, re-analysis completed in 487.66s with `analysis_mode=llm_tender_operator_provider`, `llm_invoked=true`, provider `openai_compatible`, model `arvectum-gemma4-12b-it-qat-q4_0`, and `fallback_reason=null`.
- Status remains `completed_with_warnings`; HUMAN review remains mandatory. No external procurement action occurred.

- W1-B `0333300006126000121`: read-only public acquisition attempted; run `toa-run-20260923140657-3d3613` returned `docs_required`, `manual_upload_required`, zero downloaded documents, so local LLM was not invoked and the case is not counted as a successful analysis.
- W1-C `0301200067526000236`: read-only public acquisition attempted; run `toa-run-20260923140728-f2b896` returned `docs_required`, `manual_upload_required`, zero downloaded documents, so local LLM was not invoked and the case is not counted as a successful analysis.
- These are source-bound acquisition outcomes. No authenticated EIS/ETP action or consequential external action was attempted.
