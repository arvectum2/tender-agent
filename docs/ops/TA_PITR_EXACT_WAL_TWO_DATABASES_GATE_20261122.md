# 22 November 2026 — exact WAL recovery for two real production-cluster databases

Scope: Tender Agent issue #685. This is a prepared, tested exact-target
non-production recovery tool, NOT a completed restore or a seven-day PITR proof.

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
- The exact target has NOT been independently restored and queried for
  BOTH databases by this task. Do not infer business-schema recovery from
  the older DP-only target receipt.
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

## Exact operator command requiring approval before execution

Working directory:
/Users/master/ArvectumSafe/worktrees/ta-pitr-exactwal-20261122

    uv run --no-sync python scripts/ops/verify_pitr_exact_wal_both_databases.py \
      --base-receipt /Volumes/ArvectumSSD/Arvectum/storage/tender-agent-safe-20261115/data-platform-pitr/base-20261121T131504536797Z/restore-verified.json \
      --target-receipt /Volumes/ArvectumSSD/Arvectum/storage/tender-agent-safe-20261115/data-platform-pitr/arvectum_pitr_check_20261121T131900487923Z.json \
      --execute-isolated \
      --proof-output /Volumes/ArvectumSSD/Arvectum/private/tender-agent/restore-audit-20261121/verified-postrelease-wal127-two-databases-20261122.json

Execution approval is not yet obtained. No new proof file may be represented
as existing before an actual isolated run. Recheck source receipts, disk space,
image cache and private destination vacancy immediately before execution.

## Preflight and regression outcome

ARC on Mac mini: real backup dry run preflight PASS,
isolated_restore NOT_EXECUTED, exact_postbase_target NOT_PROVEN.
Pinned image is locally cached. Focused local tests: 32 PASS; Ruff PASS;
make check PASS. GitHub exact-head CI and protected merge remain separate.
Issue #685 stays open until an actual isolated WAL restore and proof of
seven-day historical coverage.
