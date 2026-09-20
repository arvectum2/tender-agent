# ARV-010 revalidation — 2026-09-20

Task: `ARV-010-REVALIDATION-001`
Base main: `2a5e03bac8c4a6a821152c31599164e631d1e0a7`

## Historical requirement

ARV-010 retained a repository-side follow-up after storage guardrails: monitoring/alert-state, backup freshness, disk-threshold visibility and an incident runbook.

## Current merged evidence

- Storage capacity guardrails remain in current main with warning/critical/ingestion-protected states and fail-closed ingestion enforcement.
- `OPS-OBSERVABILITY-V1-001` merged in PR #76 as `c335c60fa92742d7c464739e057df7eac89fa191`.
- PR #76 final head `3dd3da7bccc2370952813b4b1f2f9af3bc44b55c` passed GitHub CI run `35143817721` with 9/9 jobs successful.
- `GET /api/ops/observability` exposes versioned queue, ingestion, document-failure, storage, backup and worker-error state.
- Queue age, document/worker failures, storage state and backup age use deterministic warning/critical reasons. Unknown/unavailable dependencies do not silently become healthy zeroes.
- Backup freshness uses ARV-076 `BACKUP_COMPLETE` + `MANIFEST.json` metadata when `ARVECTUM_BACKUP_ROOT` is configured; warning begins after 24h and critical after 48h.
- `docs/ops/OPS_OBSERVABILITY_RUNBOOK.md` covers non-destructive diagnosis/recovery for stale queue, ingestion/document failures, storage guard, backup state and unavailable dependencies.
- No third-party telemetry, automatic restore, external notification delivery, production/network/provider mutation or secret access is introduced by this revalidation.

## Current deterministic verification

Local focused/relevant run:

```text
113 passed, 1 deselected
```

The deselected case is the Docker-backed R9 backup/restore acceptance. A preceding run reached that test and failed only because the Mac mini Docker daemon was unavailable; the repository code did not fail. Current-main PR #99 exact-head CI run `35470123590` passed 9/9 on GitHub, including the repository's full CI environment where the Docker-backed acceptance runs.

`uv run make check`: PASS.

## Reconciliation result

ARV-010 is `confirmed_done` for its repository-side historical umbrella.

The historical phrase “disk threshold notifications” is satisfied here only as machine-readable warning/critical operational alert state and reason codes. This revalidation does not reinterpret it as authority to send external notifications. Live email/webhook/CRM delivery and third-party telemetry remain separate gated scopes under the roadmap.
