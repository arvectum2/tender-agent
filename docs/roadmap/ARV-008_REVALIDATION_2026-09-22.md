# ARV-008 revalidation — 2026-09-22

## Canonical historical scope

ARV-008 is the historical P0 item **“Фоновые задания и workers с прогрессом и повторным запуском”**. The active Owner continuation directive permits a bounded repository-only REVALIDATION slice when no admitted executable queue item exists; it does not authorize production/runtime mutation or architecture invention.

## Repository evidence checked

- Canonical `main` current-task is completed at ARV-030 and the execution queue contains no later ready/in-progress executable item.
- The continuation matrix places ARV-008 first in `PRODUCTION-RUNTIME` after the expert-gated ARV-067 tail of `CORE-QUALITY-PILOT`.
- Existing merged `OPS-OBSERVABILITY-V1-001` covers queue/ingestion/storage/recovery observability, but its canonical scope is observability and non-destructive recovery guidance, not proof of a durable background-worker execution contract.
- Existing merged `INGEST-RESILIENCE-V1-001` covers resumable/idempotent source sync and revision-aware dedupe, but does not by itself prove generic worker lifecycle/progress/retry semantics.
- Default-branch code searches for `worker retry progress background job`, `Celery`, and `task status progress` returned no durable implementation evidence attributable to ARV-008.

## Reconciliation

Historical ARV-008 is **not proven satisfied** by current repository-owned evidence. Adjacent foundations exist (resumable ingest and operational observability), but the repository evidence inspected does not establish the historical result “background jobs/workers with progress and restart/retry”.

This revalidation intentionally does **not** choose Celery/RQ/Arq/Temporal, a broker, process topology, deployment target, retry policy, progress schema, or production operating model. Those would be material architecture/acceptance decisions not supplied by the historical item or active Owner directive.

## Bounded residual

Record `ARV-008-WORKER-CONTRACT-001` as **candidate_not_admitted** only: define a repository-owned, implementation-neutral worker lifecycle contract covering job identity/state, observable progress, idempotent retry/restart semantics, failure evidence and compatibility with the existing resumable ingest/observability primitives. Implementation requires separate canonical admission with measurable acceptance criteria.

## Safety / gates

No production worker was started, stopped or deployed; no queue/broker/network/provider state was mutated; no external service was contacted; no secrets/private/customer data were broadened. The prior 10/10 Company AM-4 blocker was superseded by attributable Owner renewal on 2026-09-22. The renewed cycle is active; after PR #116, 3/10 automatic merges are consumed. This repository-only revalidation remains eligible for guarded AUTO merge only after rebased exact-head CI and all ordinary Product/Company gates are rechecked.
