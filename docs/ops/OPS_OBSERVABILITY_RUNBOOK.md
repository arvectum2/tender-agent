# Operational observability runbook

`OPS-OBSERVABILITY-V1-001` exposes a repository-native snapshot at `GET /api/ops/observability`. It reuses existing database/job state, the storage guard and ARV-076 backup metadata; it does not upload telemetry or perform recovery actions.

## Snapshot contract

The schema version is `ops-observability-v1`. Every signal has an explicit `status` (`ok`, `warning`, `critical`, `unknown`, or `unavailable`) and a machine-readable `reason`. Unsupported or inaccessible sources are never converted to a zero value.

Queue state comes from `TenderAnalysisJob`: queued depth, running count and oldest queued age. Queue age is warning at 10 minutes and critical at 30 minutes.

Ingestion state comes from `DocumentIngestionRun` over the last 24 hours. No recent runs is `unknown`; any failed/partial run is warning and three or more failed runs are critical. Document download/text-extraction failures are counted over 24 hours; any failure is warning and ten or more are critical.

Storage state reuses the existing public storage guard snapshot. `warning` remains warning; `critical` and `ingestion_protected` are critical; `storage_unknown` stays unknown. The endpoint does not expose storage paths.

Worker errors use failed `TenderAnalysisJob` rows from the last hour. Any failure is warning and five or more are critical.

Backup status is optional. Configure `ARVECTUM_BACKUP_ROOT` only when the application can read the ARV-076 backup root. A completed set must contain `BACKUP_COMPLETE` and `MANIFEST.json` with a valid `created_at`. Backup age is warning after 24 hours and critical after 48 hours. Missing configuration is `unavailable`; no completed set is `unknown`. No filesystem path is returned.

## Diagnosis and non-destructive recovery

For a stale queue, inspect queued job IDs and worker logs before restarting anything; confirm whether workers are running and whether the queue item is safe to retry. Do not delete queued rows as a recovery shortcut.

For ingestion or document failures, inspect the recorded run/document status and sanitized error context, then rerun the existing read-only acquisition/processing path only after the source/dependency is available. Preserve provenance and do not replace failed source facts with guessed values.

For storage warning/critical states, use the existing storage guard diagnostics. Free or relocate data only through an approved operational procedure; this endpoint never deletes files and never bypasses ingestion protection.

For backup warning/critical states, verify the latest backup with the existing ARV-076 verification tooling before taking corrective action. A missing or invalid backup is evidence for operator review, not permission to run an automatic restore.

For unavailable dependencies, fix configuration/access first and re-read the snapshot. `unknown`/`unavailable` must not be interpreted as healthy.
