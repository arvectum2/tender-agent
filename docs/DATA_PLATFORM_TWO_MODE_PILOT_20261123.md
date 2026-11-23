# Tender Agent ↔ Data Platform: two-mode ingest pilot

Date: 2026-11-23. Review-only branch `chore/ta-dp-dual-ingest-pilot-20261123` originally based on `origin/main` at `e92c948c`; merged current
`origin/main` at `c75a9356` on 23 Nov to include stricter source/receipt gates. The new
TA migration follows the upstream migration chain at revision **128**. **No live Tender Agent, Qwen, scheduler, production PostgreSQL or deployed SDK has been modified.** The canonical Tender Agent checkout contains separate, pre-existing uncommitted work and was not edited.

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

## Durable Tender Agent controller — completed candidate extension

The earlier `TwoModeTenderIndexer` remains a standalone, default-off SDK bridge for
compatibility. **New** `DurableTenderAsyncIndex` in
`src/tender_research/rag/durable_async.py` provides production-oriented metadata
persistence and bounded continuation. Alembic **128** adds
`tender_async_index_receipts` to Tender Agent's database. Each committed
receipt stores only its tender/collection/chunk IDs, SHA-256 content digest,
expected revision chunk count, DP job ID, status and committed result IDs;
**no source text, idempotency secret, provider credential or raw request** is
persisted in this table. Concurrent/retried submissions use the same stable
collection/chunk/content-derived DP idempotency key. A conflicting local
receipt blocks release rather than trusting a different job ID or changed
source.

The `rag_async_ingest_enabled` setting defaults to **false** (optional
`rag_async_ingest_min_chunks=9` and `rag_async_ingest_batch_size=8`). Only
when enabled and a tender has >=9 chunks does the existing preparation
service submit the next bounded background wave. It returns
`ready_for_analysis=false` and a pending readiness step until all chunk jobs
are fully completed; the existing <9-chunk and default-disabled synchronous
paths are unchanged. The status endpoint and Tender Agent analysis service
add a fail-closed **current-revision receipt** check, in addition to the
existing DP collection resource/embedding count. CLI per-tender and
all-tender searches also apply this gate when enabled, so incomplete sources
cannot silently become Decision Core context.

`python -m src.tender_research.rag.async_index_pump --allow-worker --once`
reconciles a bounded set of unfinished receipts and submits the next batch
when previous jobs complete; `--loop` repeats at a 5-second interval. A
**separately deployed DP worker** executes the queued embeddings. The TA pump
requires the opt-in flag, an installed candidate-compatible SDK and an
already-migrated DB. It never installs itself into launchd, starts Qwen or
changes production config. It reports counts only and fails closed on errors;
there is no automatic production daemon until separately approved.

### Additional verification

- 7 new candidate unit tests: metadata persisted across new SQL sessions,
  bounded batches, no extra jobs until prior wave completes, stale/changed
  revisions and failed job refusal, unindexed RAG search denial, preparation
  returns pending rather than ready, and pump excludes already completed jobs.
- Full cross-product isolated E2E now uses **two separate PostgreSQL 17
  databases** inside its owned disposable container: DP database with
  Alembic 0014 and Tender Agent database with Alembic 128. An independent
  SQLAlchemy engine/session is reopened mid-run to prove durability. Nine
  source-faithful chunks pass through both systems with 9/9 completed and 9
  mapped RAG hits; pending search remains blocked. TA migration 128 is also
  verified to refuse downgrade with a populated receipt journal. No active
  infrastructure, database or Qwen is modified.

### Remaining deployment dependencies

- Both candidate PRs require CI and review. No released SDK version or
  Tender Agent production pin has been changed yet.
- At staging rollout, deliberately apply **both** additive DB migrations,
  configure the enabled flags in the staging environment and run both
  opt-in workers with independent resource limits/monitoring. Never enable
  a background producer before the consumer/worker is demonstrably live.
- Follow `docs/QWEN_ASYNC_AB_WINDOW_PROTOCOL_20261123.md` in DP PR #135
  before adopting background completion SLOs. Shared Qwen on Mac mini has
  high swap pressure; no uncoordinated 160-case inference load is permitted.
- Existing DP synchronous ingest SLO <=10s remains active. Issue #133 stays
  OPEN; production release HOLD until numeric criteria, resource budget,
  rollback/backup and explicit owner deployment decision are verified.

## Upstream main integration and strengthened acceptance

The TA candidate has been reconciled with upstream main through revision 127;
our new metadata-only migration is **128**, not competing with the upstream
108--127 series. Existing upstream `complete_index_counts` requires exact
resources/documents/chunks/embeddings counts. The pilot now requires exactly
one indexed chunk per submitted tender chunk, unique resource and document IDs,
and exact source/receipt hashes and current revision, not merely nonzero counts.
The original synchronous path continues to respect upstream's stricter gates.
Updated disposable two-PostgreSQL E2E passed after the merge resolution.

The old CI quality failure on the pre-merge candidate (5387 tests PASS, one
failure) occurred in the independent legacy R9 backup/restore matrix with
`pg_restore failed with exit code 1`; the pilot was not deployed. The exact
current-head CI must be checked separately. No part of this release may
silently drop or weaken that backup gate.

## Compatibility with pre-existing indexed tenders (post-merge hardening)

On opt-in activation, an older **fully indexed synchronous** tender collection
with no asynchronous receipt journal must not be needlessly blocked. The
readiness gate accepts a zero-receipt collection only if live Data Platform
collection statistics match all four expected counts **exactly** (resources,
documents, chunks, embeddings) for the current tender source revision.
A partially journaled async collection can **never** take this fallback,
even if collection counts happen to look correct. When any background receipts
exist, they must cover every chunk, have the correct source hash and revision,
`completed` state, exactly one committed indexed chunk each, and distinct
resource/document identifiers. The active retriever checks both the local
journal and remote collection counts; the analysis service reuses its existing
read-only DP stats check. Before a stage rollout, verify this fallback
against real previously indexed test collections, not only synthetic ones.

Final scoped candidate validation after merging current main: **125 tests PASS**,
Ruff PASS, disposable two-PostgreSQL E2E PASS (9 accepted/9 complete/9
provenance-mapped retrieval hits; pending blocked). The full GitHub CI on the
current head remains the release authority. This pilot is draft and default-off.

## R9 backup/restore CI acceptance: PostgreSQL client version resolution

A reproducible unrelated full-CI blocker was traced to the R9 disposable
backup/restore acceptance test: the test uses **PostgreSQL 16 + pgvector** but
its host may have PostgreSQL **18** client utilities. The PG18 `pg_restore`
sends `SET transaction_timeout`, which PG16 rejects. The matrix failed with
`pg_restore failed with exit code 1` before testing later scenarios.

The change is strictly limited to the *test harness* at
`scripts/acceptance/run_r9_backup_restore.py` and its new guarded native-PG16
CLI adapter `r9_pg_container_client.py`: after the owned disposable compose
service starts, it verifies the exact Compose project label and PG16 client
version, and temporarily selects `pg_dump`/`pg_restore` executing inside that
same PG16 server container. The adapter rejects non-loopback targets and wrong
ports, streams archive bytes through explicit stdin/stdout, never logs
credentials or restores to an arbitrary server, and removes/clears its
scratch PATH and environment in the cleanup block.

**The production `scripts/ops/r9_recovery.py` code is unchanged**; it still
requires an empty restore target, performs a single atomic transaction,
checks exit codes, redacts underlying database errors, and rejects inconsistent
DB/filesystem/tenant snapshots. The full original disposable R9 restore matrix
was rerun and returned **PASS** (1 test), plus targeted tests of proxy
fail-closed behavior and unchanged restore/error-redaction contracts. The
exact latest-head GitHub CI is still the release gate; neither a local test
pass nor draft PR authorizes production migration/deployment.
