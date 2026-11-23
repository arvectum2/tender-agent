# 22 November 2026 — exact WAL recovery for two real production-cluster databases

Scope: Tender Agent issue #685. This is a prepared, tested exact-target
non-production recovery tool, now independently verified for BOTH databases at one named WAL point. Continuous seven-day PITR remains NOT_PROVEN.

## Evidence from saved receipts and ARC-only read-only preflight

- Actual PostgreSQL 17 production cluster: 7692004809331994662; both
  arvectum and arvectum_data belong to it.
- Original post-release physical base: base-20261121T131504536797Z.
  Verified manifest SHA256:
  470fb9d34ed5c49e75dd1516842392fc296ce6fcc3faf4e493dbd34a96234a46.
  Matching pg_verifybackup 17.12 passed in previous issue #685 audit.
- A previously saved DP-only named-target restore receipt records point
  arvectum_pitr_check_20261121T131900487923Z; base-end LSN 6/7B288058,
  target LSN 6/7E000090, and four consecutive 16-MiB source WAL segments
  00000001000000060000007B through 00000001000000060000007E.
- The historical DP-only receipt was insufficient for business recovery proof.
  A new ARC-authorized single-run 22-Nov independent restore now verifies
  BOTH databases at this exact named point (see recorded evidence below).
- Historical seven-day PITR completeness is NOT_PROVEN; known physical base
  history starts on 20 November 2026, not 15 November.

## Tool and safety contract

scripts/ops/verify_pitr_exact_wal_both_databases.py defaults to
preflight-only mode without Docker/DB/network or write capability. It
validates exact backup source receipt, PG17 format, manifest SHA256, container
image digest, named WAL target and ordered, present, size-bounded WAL segments.

A second mode requires explicit --execute-isolated and private immutable
--proof-output. It starts a temporary container with
--pull never --network none --rm; source base and WAL are mounted readonly.
It copies the base to disposable container-local storage, starts PG17 with
UNIX sockets only, replays to the named target, requires that exact point
in the PostgreSQL server log, and queries both databases in the SAME
recovered cluster. Expected business revision is
127_private_review_link_corrections with seven post-release tables,
64+ tender rows; expected Data Platform is 73+ collections.
Proof stores only counts and schema; it is created once without overwrite.

Never claim seven-day PITR from a single point. No production DB, EIS, ETP,
payment, deployment, watchdog or backup archival changes.

## Exact operator command — completed once after owner approval

Working directory:
/Users/master/ArvectumSafe/worktrees/ta-pitr-exactwal-20261122

    uv run --no-sync python scripts/ops/verify_pitr_exact_wal_both_databases.py \
      --base-receipt /Volumes/ArvectumSSD/Arvectum/storage/tender-agent-safe-20261115/data-platform-pitr/base-20261121T131504536797Z/restore-verified.json \
      --target-receipt /Volumes/ArvectumSSD/Arvectum/storage/tender-agent-safe-20261115/data-platform-pitr/arvectum_pitr_check_20261121T131900487923Z.json \
      --execute-isolated \
      --proof-output /Volumes/ArvectumSSD/Arvectum/private/tender-agent/restore-audit-20261121/verified-postrelease-wal127-two-databases-20261122.json

Owner authorization was obtained and the exact command above executed ONCE
via ARC on 22 November 2026. The proof file now exists with mode 0600;
do not re-run and do not overwrite this immutable proof.

## Preflight and regression outcome

ARC on Mac mini: dry-run preflight PASS, 32 focused local tests PASS,
Ruff and make check PASS. PR #697 exact-head CI 19/19 PASS and merged to
protected main 6b49cbba4ffcbb62630fe78e1c118c2bfe96f2a1.
After owner approval, a single real isolated restore of both databases
succeeded (see proof below). Issue #685 remains open only for the
unproven seven-day recovery horizon.


## Actual verified exact post-base WAL restoration — 22 November 2026

After owner approval and all 19 exact-head CI checks passed, ARC launched a
SINGLE temporary Docker container with --pull never, --network none, --rm.
The original PostgreSQL physical base and four WAL segments were mounted
read-only. Disposable container storage held the recovered cluster.
No TCP ports were exposed. The container exited successfully.

The PostgreSQL recovery log inside the container contained the exact named
restore-point marker; independent SQL queries in that SAME restored cluster
verified:

| Database | Independently verified at WAL target |
| --- | --- |
| arvectum | Alembic 127_private_review_link_corrections, 64 tenders, 7 postrelease tables |
| arvectum_data | 73 Data Platform collections |

Target: arvectum_pitr_check_20261121T131900487923Z.
The private immutable proof is retained in restore-audit-20261121 as
verified-postrelease-wal127-two-databases-20261122.json.
Verified at UTC 2026-11-22T09:45:45.595499+00:00.
Receipt mode: 0600; 637 bytes; full SHA256:
8f0692b3f37cf94b76c04d3ce81795a0215f3c8ecea7d67146beb6fb83ad9b08.
The receipt was re-read and reconciled to the original full manifest SHA256,
schema, recovered DP count, exact named target, and the seven-day status.
No original SQL bodies, signed URLs or recovery logs were committed.

This demonstrates exactly ONE post-base WAL restore of BOTH databases,
not every historical point across seven days. Continuous seven-day PITR
is still NOT_PROVEN, because the oldest independently receipted base starts
on 20-Nov-2026. The earliest seven-day age candidate is 27-Nov-2026;
even then a complete WAL integrity check and independent historical target
restore are needed. Keep issue #685 open; no production deployment or
authorization change follows from this isolated proof.
