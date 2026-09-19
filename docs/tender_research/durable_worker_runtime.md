# ARV-008 durable worker runtime v1

This slice converts the existing Tender Research background-job execution boundary from an in-process-only `ThreadPoolExecutor` option into an explicit choice between the compatibility thread backend and a separate-process Redis worker.

It deliberately reuses the ARV-007 Redis foundation. Redis remains an **ephemeral delivery/coordination layer**; the `TenderAnalysisJob` row in PostgreSQL remains the durable source of truth for job status, request, progress and result.

## Backend selection

The API backend is selected explicitly:

```text
AI_CORP_TENDER_RESEARCH_JOB_BACKEND=thread
AI_CORP_TENDER_RESEARCH_JOB_BACKEND=redis
```

`thread` preserves the existing in-process behavior. It is not an implicit fallback.

`redis` publishes a versioned `QueueEnvelope` to a Redis Stream. If Redis is disabled or unavailable, job submission fails closed with HTTP 503 and the newly-created PostgreSQL job is marked failed with the sanitized `background_job_submission_failed` code. The API never silently switches to the thread executor.

## Redis transport

The transport uses the already-installed `redis-py` client and Redis Streams consumer groups. No Celery, RQ or Dramatiq dependency is introduced.

The stream key is namespaced by:

```text
{redis_namespace}:{redis_environment}:queue:{queue_name}
```

A delivery contains only the existing queue envelope plus the durable PostgreSQL job id and request payload. Consumer groups provide at-least-once delivery.

The worker:

- reads a new group delivery or first reclaims a stale pending delivery with `XAUTOCLAIM`;
- checks PostgreSQL before execution;
- acknowledges an already-terminal job without re-running it;
- refreshes the Redis lease on job progress using `XCLAIM`;
- executes the existing prepare/analyze runner;
- acknowledges terminal success/failure;
- on a retryable failed attempt, returns the PostgreSQL job to `queued` and atomically publishes the next attempt + acknowledges the old delivery in one Redis transaction;
- leaves an unexpected non-terminal delivery pending so a later worker can recover it.

The default visibility timeout stays aligned with ARV-007 at 300 seconds.

## Retry boundary

The initial envelope defaults to three attempts. Backoff is exponential from the configured base and capped at 300 seconds.

```text
AI_CORP_TENDER_RESEARCH_WORKER_MAX_ATTEMPTS=3
AI_CORP_TENDER_RESEARCH_WORKER_RETRY_BACKOFF_SECONDS=5
AI_CORP_TENDER_RESEARCH_WORKER_VISIBILITY_TIMEOUT_SECONDS=300
```

A final failed PostgreSQL job is not resurrected after its attempt budget is exhausted.

## Starting a worker

Redis mode is intentionally a separate process. A supervisor/deployment unit can run:

```bash
AI_CORP_TENDER_RESEARCH_JOB_BACKEND=redis python -m src.tender_research.rag.worker
```

For a bounded diagnostic run:

```bash
AI_CORP_TENDER_RESEARCH_JOB_BACKEND=redis python -m src.tender_research.rag.worker --once --block-ms 1000
```

This task does not enable or deploy the worker in production.

## Failure and restart semantics

A worker crash before acknowledgement leaves the message in the consumer group's pending set. After the visibility timeout another worker reclaims it. PostgreSQL is checked before dispatch, so a delivery whose durable job is already terminal is acknowledged without re-execution.

Long-running prepare/analyze jobs refresh their lease at runner start and on progress callbacks. A transport failure during lease refresh fails the current runner through the existing fail-closed job path, allowing the bounded retry/recovery contract to take over.

## Explicit residual ARV-008 scope

This is the first bounded ARV-008 implementation slice, not full ARV-008 completion. The canonical roadmap still requires separately bounded work for:

- pause/resume semantics;
- per-tenant worker concurrency limits;
- per-tenant/job cost budgets;
- any broader batch-runtime policy or deployment topology.

Those controls must not be inferred from this transport implementation.
