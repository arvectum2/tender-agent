# Tender Agent + Data Platform: seven-day PITR window acceptance gate

Observed read-only on **21 Nov 2026 12:44 UTC**, without restore or production changes. Current TA/DP health state and *independent real-WAL restore proof* both `pass`; both physical WAL receivers active (`async`), no backups removed.

| Property | Tender Agent | Data Platform |
| --- | --- | --- |
| Visible verified physical bases | 3 | 4 |
| Earliest visible physical base | 2026-11-20 09:47:06 UTC | 2026-11-20 08:46:41 UTC |
| Complete archived 16-MiB WAL segments | 1024 | 1014 |
| Missing segments in visible sequential 24-hex WAL range | 0 | 0 |
| Standby receiver and current restore-point check | PASS | PASS |
| Continuous **seven days** of PITR available now | **NOT PROVEN** | **NOT PROVEN** |
| Earliest theoretical date 7 days after first verified base | 2026-11-27 09:47:06 UTC | 2026-11-27 08:46:41 UTC |

`ta_pitr_maintenance.py` and `dp_pitr_maintenance.py` are configured to refresh a restore-tested base after >=23 hours and perform periodic WAL health checks; the observed maintenance code explicitly states **No pruning**. The installed LaunchAgents have `StartInterval=300` seconds. Older standalone logical `.dump` files exist for DP back to early November; they are **NOT** proof of continuous physical WAL replay/PITR for a seven-day interval. Current PITR base snapshots and matching WAL only begin 20 Nov. Full day-seven proof must be checked **no earlier than 27 Nov 2026** and must not be backdated.

## Acceptance on/after 27 Nov (no shortcuts)

1. Locate actual owner-private verified physical base receipt for each database at or before the start of the requested 7-day window, with exact source cluster system identifier, timestamp, checksum and timeline. Reject symlinks/modified receipts and backups pointing at a different database.
2. Independently re-read the complete archived WAL sequence through a fresh end restore point. Verify every required segment belongs to the same cluster/timeline, is exactly 16 MiB, contiguous, has no gaps, and is physically on disk; filename continuity alone does not prove the content is valid.
3. Use the existing network-isolated restore verifier on an independent restore target, testing the archive and at least the oldest in-window restorable point plus current point; compare physical identity and business table invariants. Do not mutate the live source or stop WAL receiver to perform proof.
4. Retain prior verified bases, archive and prewrite receipts; do not prune while continuity or restoration has not been verified. Persist **actual** result separately for TA and DP. On any missing original WAL/base or failed restore, mark `blocked`, not `pass`.
5. Ensure the next scheduled daily tender task on live pinned release `9b650a2b` is assessed from its real run receipt; `--preflight` PASS alone is not proof of a completed scheduled run.

This document is an audit of the current evidence, **not** a claim that the 7-day gate passed. No backup deletion, policy change or live database write is authorized by this audit.
