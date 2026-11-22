# 2026-11-22 — independent review of post-release physical PostgreSQL 17 backup

**Scope:** read-only audit against saved backup and isolated-clone receipts on Mac mini, linked to [PITR issue #685](https://github.com/arvectum2/tender-agent/issues/685). **Result:** a PostgreSQL 17 post-release *base* can be verified and the existing isolated restore receipt shows both actual production databases at schema 127. **Full seven-day PITR and exact post-base WAL replay remain NOT PROVEN.** Nothing was written to production, no source EIS retrieval, no production database connections, no Docker restore/restart, no new scheduled task.

## Evidence, 21-Nov physical archive rechecked 22-Nov

The actual business database `arvectum` and Data Platform `arvectum_data` share one PostgreSQL physical cluster (`system_identifier` `7692004809331994662`). The separate historical TA-PITR `arvectum_local` cluster does not double-backup this production pair. A new physical base was archived after the business schema upgrade on **2026-11-21 13:15 UTC** (`base-20261121T131504536797Z`). The original receipt and an independent isolated physical restore receipt dated 13:17:57 UTC agree on source cluster and base, read-only source mounts and `--network none`. The archived restore receipt records:

| Restored database | Verified as recorded at the isolated post-release restore |
| --- | --- |
| `arvectum` | Alembic `127_private_review_link_corrections`, 64 tender rows, seven new tables, same cluster ID |
| `arvectum_data` | 73 Data Platform collections, same cluster ID |

On 22-Nov the backup manifest file itself was observed under that original backup. SHA256 `470fb9d34ed5c49e75dd1516842392fc296ce6fcc3faf4e493dbd34a96234a46`. The `global/pg_control` file matches the exact SHA256 embedded in the backup manifest, not an arbitrary external filename. Independently executing **`pg_verifybackup 17.12 --no-parse-wal` against the entire saved physical base passed** without modifying source files. Its `--no-parse-wal` mode verifies the base files, not WAL temporal continuity.

An initial attempt using unqualified `pg_verifybackup` resolved to **PostgreSQL 18.7** and reported `pg_control CRC is incorrect`; this was a **binary-major mismatch**, not evidence of corruption of the PostgreSQL 17 archive. Running the matching installed PostgreSQL 17.12 binary completed successfully. Do not use an ambiguous `PATH` when validating major-specific physical backups.

## Repeatable safe audit

`python scripts/ops/audit_pitr_postrelease_receipts.py --source-receipt <operator-pinned-absolute-original-backup-receipt> --clone-receipt <operator-pinned-absolute-isolated-restore-receipt> --pg-verifybackup /opt/homebrew/opt/postgresql@17/bin/pg_verifybackup`

The operator supplies existing private receipt paths; they are **not** checked in. The script checks the trusted receipt, source cluster and two DB identities, schema 127, file metadata and manifest, runs the matching PG17 verifier without WAL parsing, and outputs only safe result codes/counts/manifest checksum. No DB, Docker, network or live source access is implemented. It will reject PG18 as a validator for PG17. Its successful output is restricted to **base-file integrity and consistency of historical restore receipts**, not a newly executed physical restore. Private raw receipts/logs/credentials stay on Mac mini.

Regressions: seven synthetic-only tests (PG17 pass, PG18 fail-closed, wrong physical cluster, wrong schema, base format mismatch, verifier failure sanitization, symlink path reject). Together with existing backup tests: **18 PASS**, 2 inherited warnings, targeted Ruff PASS, `make check` PASS, real saved physical PG17 source-verification PASS.

## Still not admitted under issue #685

- Exact archived recovery target **after** the schema127 physical base using complete WAL archive and log evidence: **NOT PROVEN** (`exact_archived_postbase_restore_target_tested: false`). A base copy restore is not PITR to an arbitrary later timestamp.
- A verified physically restorable continuous **seven-day** history including archive retention, WAL continuity and independent replay at a chosen target: **NOT PROVEN** (`continuous_7day_pitr_proven: false`). Earliest known physical bases dated 20-Nov, age condition not achievable before 27-Nov unless an older independently proven base exists.
- No widening of source retry gates, no acceptance of DTR three missing EIS originals, no tenant/operator financial/commercial GO and no production restart/deployment is granted by this check.

Track an exact postbase WAL target restoration separately with isolated network and source-readonly mounts, and later independently prove the seven-day interval; never convert `NOT_PROVEN` to `PASS` from folder age or a self-declared health receipt alone. This is a **partial evidence advancement**, not closure of #685.
