# Tender Agent ↔ Data Platform: two-mode ingest pilot

Date: 2026-11-23. Review-only branch `chore/ta-dp-dual-ingest-pilot-20261123` based on `origin/main` at `e92c948c`. **No live Tender Agent, Qwen, scheduler, production PostgreSQL or deployed SDK has been modified.** The canonical Tender Agent checkout contains separate, pre-existing uncommitted work and was not edited.

## Existing stable behavior

`DataPlatformTenderIndexer.build_for_tender()` and its established per-chunk `tender-chunk://` evidence mapping remain unchanged. The normal RAG retriever, local chunk projection and production pipeline still use synchronous `ingest_chunk`. The new opt-in bridge MUST NOT be enabled against an older Data Platform runtime or consumer SDK: the current Tender Agent dependency is pinned to the released SDK 0.3.0; this candidate pilot uses the new source-only SDK API from DP PR #135 and does not change the pinned dependency.

## New opt-in bridge

`src/tender_research/rag/two_mode_ingest.py` exposes `TwoModeTenderIndexer` with `async_enabled=False` by default, a 9-chunk default background threshold and bounded 8-job submission waves. For small tenders it delegates to the original synchronous indexer; larger tenders use `enqueue_ingest_document_bytes()` with the original canonical collection ID, `tender-chunk://{chunk_id}` source URIs, original title, UTF-8 text, pre-chunked flag, and SHA-256 idempotency keys derived from collection/chunk/content. This preserves evidence references and avoids submitting more than 8 new jobs in one wave.

Callers must persist returned `AsyncTenderIndexBatch` receipts and resume at `next_offset`. They must also confirm completion via `require_ready()` before invoking `search_when_ready()`. The readiness gate rejects missing/duplicate/stale-revision receipts, pending jobs, cancelled/dead-letter jobs, mismatched collection/job IDs, and completion without a committed resource/document/chunk result. This is a **new gated pilot workflow**; the unchanged general-purpose retriever does not yet enforce it globally. Do not switch the production pipeline on until its state persistence and all entrypoints enforce this gate.

## Evidence

- 11 isolated bridge unit tests PASS, including default synchronous behavior and fail-closed state tests.
- 75 targeted Tender Agent regressions PASS with the candidate DP SDK source made available only for the local test run (no deployed SDK replacement).
- Reproducible disposable cross-product HTTP + PG17 acceptance: `scripts/ta_dp_disposable_interop.py` starts an owned loopback PostgreSQL 17/pgvector container and candidate API, sends 9 source-faithful Tender Agent chunk jobs in bounded waves, proves search is blocked while incomplete, executes a finite worker against that disposable DB, and confirms 9 completed jobs and 9 evidence-mapped retrieval hits. Hashing embedding provider only; **no Qwen inference**.
- Synthetic source data only; own temporary container label is required for cleanup. The test runner demands an explicit `--execute-disposable-test` flag and a candidate DP worktree path; it does not use the production database or current service.

Reproduce only on an authorized Mac mini test checkout (not production):

```
PYTHONPATH=<DP_CANDIDATE>/sdk/python/src:<TA_CANDIDATE> \
  <TA_TEST_PYTHON> scripts/ta_dp_disposable_interop.py \
  --dp-worktree <DP_CANDIDATE> --execute-disposable-test
```

## Release gates / next actions

1. Publish and pin a **separately reviewed** compatible consumer SDK after DP PR #135 is accepted; do not replace the production Tender Agent SDK ad hoc.
2. Persist background batch receipts in a durable Tender Agent workflow, and route all relevant retrieval and decision-analysis entrypoints through the completion gate; a partial asynchronous index must not be treated as completed evidence.
3. Verify live Qwen 5/10/18/27-chunk format/concurrency cohorts in a separately approved resource-safe test window, retaining same dimensions and retrieval quality. Define an owner-approved background completion SLO independently of synchronous p95<=10 s.
4. Prepare a production migration/rollback and database backup/retention plan. DP migration 0014 refuses downgrade if any async job rows still exist; use an additive schema rollback or explicit reviewed export/drain, never silently delete user jobs.
5. Only then request explicit production deployment authorization. Do not merge/deploy from this pilot automatically.

**Pilot demonstrated; full runtime integration not yet released.** DP Issue #133 remains OPEN, production HOLD.
