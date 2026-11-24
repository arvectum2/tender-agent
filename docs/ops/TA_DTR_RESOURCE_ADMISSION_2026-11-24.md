# Full Daily Tender Run resource-admission gate — 24 November 2026

This is a source-only candidate for the existing pinned local daily launcher. No production deploy, launchd change, restart or new DTR was performed.

## Live evidence

At 10:30 MSK the host used roughly 82 GiB swap; the existing owner-controlled resource governor health.json had schema 1, status pass, mode paused, batch_limit 0. Status pass means a valid sample, NOT capacity admission. An already-running DTR continued; at 10:35 MSK its durable DB status became WAITING_HUMAN: 8 MANAGER_READY, 21 SCREENED_OUT, 4 DUPLICATE, zero processing and no current run error. Separately observed historical DTR errors remain flagged for 19 and 20 November and explain why the pinned runner can report last exit code 20 while the new run has no error.

## New source behavior, not deployed

Before backend or DB probes, the full daily launcher requires fresh trusted resource telemetry: an owner-controlled regular file opened read-only with NOFOLLOW, checked file owner, link count, permissions and bounded size; exact schema 1, status pass, mode normal, integer batch_limit 10, timezone-aware UTC checked_at_utc within 0 to 100 seconds. Missing, stale, malformed, insecure, paused or reduced samples fail closed.

Reduced capacity (batch_limit 3) does not admit an unrestricted full daily job. A denied preflight produces generic exit 75 without revealing telemetry, paths or secrets. The guard does not modify files, database rows, current processes or locks. Existing mutual exclusion still releases the lock on denial. Preflight remains read-only.

## Verification and outstanding gates

The source-only synthetic regression suite passed 37 tests, plus Ruff and compile. Negative tests cover paused/reduced, stale and future timestamps, malformed data, unsafe permissions, symlink, bad types and lock release. Direct read-only evaluation of actual governor telemetry returned NEW_FULL_DAILY_ADMISSION_DENIED, with running-state unchanged.

A protected exact-head CI merge is required to complete this *code* stage. The changed source is not the currently pinned production release: owner-authorized deployment, exact release checks and rollback are separate. No changes to existing watchdog, provider, models, current runs, ETP, bids, payments or original procurement documents. Issues #679, #685, #686 and Data Platform #137 remain open.
