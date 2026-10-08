# ARV-061 — Fast cited pre-analysis

## Scope and reuse

The thin preliminary view is a read-only projection of the existing `build_decision_core()` output, not an independent procurement analysis engine. `GET /api/demo/tender-agent/pre-analysis?reference=<19-digit-number-or-EIS-URL>` resolves an exact 44-FZ registry number using the existing public EIS card parser. `GET /api/demo/tender-agent/runs/{run_id}/pre-analysis` projects the persisted Decision Core of an already analyzed document run. Neither endpoint authorizes tender participation or any external commercial action.

## Provenance and unsupported facts

The public-card path only exposes subject, deadline and starting price when the exact 44-FZ card and HTTPS EIS source URL agree. Citations explicitly identify **the public EIS search card**, not an attachment page. Essential contractual/technical requirements, licenses, securities, supplier-specific fit and deadline validity remain `UNKNOWN` or `NEEDS_REVIEW` until the canonical document-intake/analysis path is completed. Unsupported regimes, absent evidence, source errors and mismatched registry numbers never fall back to nearby/demo tenders. An already analyzed run can expose its existing source-bound requirements and blockers. Full source/page/fragment citations are limited by source evidence available in the canonical analysis; the fast path never fabricates them.

## Latency target and measurement

Target for the *in-memory projection* is <=100 ms p95 on a warm development machine, excluding EIS networking, database I/O and full document analysis. Measured on Mac mini 2026-10-08 with 1,000 calls and an injected deterministic public-EIS card: p50 0.009 ms, p95 0.009 ms, max 0.551 ms. This is a local microbenchmark **not** a measured live network or end-to-end SLA. End-to-end public EIS latency and availability remain provider-dependent and require production instrumentation and a live pilot; `latency_seconds` exposes the measured time for the direct endpoint call. The deterministic mock result is for regression and performance characterization only, never evidence that EIS was live.

## Validation

Focused `tests/test_arv061_fast_preanalysis.py` plus `tests/test_decision_core_v1.py`; verify strict URL matching, source-bound facts, unknown fallback, human control and bounded rendering. CI must pass on the exact PR head before merge.
