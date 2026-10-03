# BASE-012 revalidation — 2026-10-03

## Scope

Repository-only reconciliation of the historical Quality R1–R5 golden loop, provenance and source-graph baseline after completion of `ARV-005-CONTROLLED-PILOT-EVIDENCE-001`. This does not rewrite frozen pilot evidence, rerun counted inference, or infer human usefulness/commercial acceptance.

## Current evidence

The controlled pilot expanded the historical five-procurement baseline to:

- 12 unique 44-FZ procurements with completed technical reports in frozen waves 3 + 5 + 4;
- three separately scored exploratory 223-FZ procurements, all retained as source-bound blockers;
- explicit provider/model/fallback provenance for every counted or supplemental result;
- zero observed silent fallback after the provenance remediation;
- zero observed cross-procurement source-ownership violation in the frozen Wave 3 confirmation set;
- an aggregate technical report at `docs/pilot/ARV-005_TECHNICAL_PILOT_REPORT_2026-10-03.md`;
- regression capture for source-link selection, revision handling, document-kind aliases, deadline timezone, report/Decision Core consistency, LLM failure provenance and cross-domain line-item contamination.

The final pilot code/evidence head `8e14fe5106062b68cf6feb3a61613a80b36623de` passed GitHub Actions CI run `37138206676`; its nine required jobs succeeded. Queue closeout is commit `215a9651e8abb14b651edeaea8c9029e29fba064`.

## Reconciliation

BASE-012 is no longer merely a five-procurement baseline. Its repository-side expansion and provenance/source-ownership validation are established by durable pilot evidence.

Residual gaps remain explicit:

- only 3 of 11 LLM-invoked 44-FZ cases completed the controlled-LLM path without fallback;
- eight later LLM-invoked cases failed all four controlled sections and correctly failed closed into deterministic fallback;
- the three 223-FZ exploratory cases remained source-incomplete;
- human usefulness, commercial acceptance and participation decisions were not evaluated.

Any model/prompt/performance work or 223-FZ semantic pilot must begin as a newly admitted, newly frozen evaluation phase. This revalidation does not authorize either implementation.

## Boundaries

No procurement submission or modification, authentication to EIS/ETP, signing, external communication, payment, production mutation, benchmark-truth change, counted inference rerun, or human/commercial acceptance claim occurred.
