# ARV-075 revalidation — 2026-09-24

## Scope
Repository-only reconciliation plus explicitly read-only Mac mini capacity checks. No deletion, move, cleanup, symlink, mount, Docker, PostgreSQL, network, provider, procurement, or external action was performed.

## Canonical evidence
- `docs/ops/arv-009-storage-decision.md` approves the external 4 TB SSD for pilot storage.
- `docs/ops/storage-capacity-guardrails.md` requires the storage root to be on a separate filesystem from `/` and fails closed when that cannot be verified.
- ARV-075 historically asks for a system-disk baseline, classification of large/temp/cache/runtime data into DELETE / MOVE / KEEP, backup, then only confirmed cleanup/migration with post-change verification.

## Read-only Mac mini snapshot
At 2026-09-24 approximately 08:00 MSK, `df -h` reported the 460 GiB system filesystem with 281 GiB available, and `/Volumes/ArvectumSSD` as a separate 3.6 TiB filesystem with 216 GiB used and 3.4 TiB available. A targeted read-only `du` of `/Users/master/arvectum-runtime` showed the largest visible repository/runtime entries were approximately 313 MiB (`AI-Corporation`), 220 MiB (`tender-agent-pilot-main`), and 140 MiB (`venv`); pilot data was about 7.2 MiB.

These observations establish capacity posture only. They do not prove that all Arvectum heavy data has been migrated, that caches/old clones are safe to delete, or that Docker/PostgreSQL paths should be changed.

## Reconciliation result
There is no evidence of an immediate system-disk capacity emergency, and the approved external SSD is mounted with substantial free capacity. ARV-075 is therefore revalidated as a residual operational-cleanup/migration gap rather than a completed task.

The bounded successor candidate is `ARV-075-STORAGE-CLEANUP-PLAN-001`: produce a read-only path-level DELETE / MOVE / KEEP proposal plus backup/rollback and post-change verification plan. It is **not admitted** here. Any destructive cleanup or path/mount/runtime mutation requires separate applicable authority.

## Deterministic validation
`pytest -q tests/test_storage_capacity_guardrails.py tests/test_storage_readiness_mount_verified.py tests/ops/test_arv076_runtime_backup.py` passed **72 tests**. The warnings were pre-existing framework/SQLAlchemy warnings; no storage mutation occurred.
