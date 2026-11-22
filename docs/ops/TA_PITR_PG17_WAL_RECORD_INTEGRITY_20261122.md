# 22-Nov-2026 — production PG17 archived WAL content preflight

This is a bounded historical content audit, not seven-day PITR acceptance.
No database access, backup change, network, historic restore or new watchdog.

## Verified backup and archive evidence

- Original physical base from 2026-11-20 08:47:31.139954 UTC:
  data-platform-pitr/base-20261120T084731139954Z.
- Its restore-verified.json confirms status pass, physical system ID
  7692004809331994662, manifest verified, original data path, and no
  live database mutation.
- The locally installed PostgreSQL17 image digest matches this receipt:
  sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d.
- Exactly 1,758 completed 16-MiB WAL segments, 29,494,345,728 bytes
  (~27.47 GiB), timeline 00000001; first full archive segment
  000000010000000200000079, last full segment
  000000010000000900000056.
- All complete-segment filenames and lengths are ordered contiguously;
  one receiver in-progress .partial was excluded from counts and checks.
- SHA256 of ordered *file names and file sizes* (NOT of WAL body bytes):
  e646aebff2651f8fb434157be90def41d7677e95b6758016f71b20fd57283e19.

## Actual PostgreSQL17 record-content verification

Source-only script: scripts/ops/audit_pitr_wal_record_integrity.py.
Default dry-run validates cluster receipt, WAL path, symlink exclusion,
archive segment order, exact lengths and partial handling; it never
claims record integrity without decoding records.

Explicit --verify-records runs the exactly pinned local PG17 image with
Docker --pull never, --network none, --read-only, --cap-drop ALL,
--security-opt no-new-privileges, and a read-only WAL bind mount.
PostgreSQL17 pg_waldump --quiet successfully processed the entire
bounded 1,758-segment archive, exiting 0 in about 22 seconds.

Result: PASS_BOUNDED_WAL_RECORD_PREFLIGHT_NOT_SEVEN_DAY_PITR.
No production changes, no source HTTP requests, no network access.
The independent private 0600 immutable proof, outside Git, has SHA256
90213cb4b1cc98d0309e1f5a0a3743c7868359e30618f9b3557ed8ad790f3c38.

31 focused tests across WAL record preflight and earlier exact PITR
proof PASS (2 inherited warnings). Ruff and make check PASS.
The new synthetic tests reject gapped, truncated, symlinked, mixed,
wrong-cluster inputs and any false seven-day acceptance.

## Seven-day PITR is still BLOCKED

The oldest confirmed physical base was only about 2.24 days old at
this run. Earliest possible seven-day age condition is 2026-11-27
08:47:31 UTC, conditional upon source archive retention. Successful
PG17 record decoding of this limited observed archive does NOT prove
seven-day backup history, seven-day uninterrupted WAL, or any actual
seven-day historical recovery point.

Final acceptance still requires verifying the real seven-day base
and continuous WAL, then independently restoring BOTH production DBs
arvectum and arvectum_data at a dated historical target in an isolated
PG17 clone, with verified target recovery logs and business+DP SQL.
Issue #685 remains OPEN and blocked. EIS originals issue #679 separate.
