# 21 November 2026 — Independent production DB PITR restoration proof

**Result: two databases physically restored successfully; seven-day history NOT PROVEN.** This is a non-production, no-network, read-only-source exercise. The private full receipt and replay script are stored on the Mac mini, not in this public repository.

## Critical cluster identity correction

The production Tender Agent backend's actual database `arvectum` and the Data Platform database `arvectum_data` belong to the **same PostgreSQL physical cluster** (verified by read-only `pg_control_system()` and database listing). Its physical backups are maintained under **DP-PITR**. The separately named **TA-PITR** covers a different physical cluster, with database `arvectum_local`. Therefore, counting TA-PITR as an independent second full physical backup of the current production `arvectum` would be incorrect.

## Actual independent restoration

On 21 November 2026, at 12:49:14–12:49:29 UTC, an offline container used the already integrity-verified DP-PITR base (taken 21 November 07:51 UTC) and the two archived 16-MiB contiguous WAL segments associated with its previously verified named restoration point. Docker settings: `--network none`, `--pull never`, no exposed TCP ports, both original base and WAL directory mounted **read-only**. The 2.5-GB cluster base was copied into ephemeral container-only storage before recovery; PostgreSQL was started with UNIX socket only, and the server log showed reaching the exact previously verified named recovery point. The isolated container exited and was removed.

Independent SQL reads from the **actual recovered physical cluster** (not mocked tables):

| Restored database | Verification at the archived target |
| --- | --- |
| `arvectum` — actual production business database | Recovery completed; PostgreSQL schema revision `122_company_cost_norms`; `63` `procurement_tenders`, original records intact as of the **pre-upgrade** backup |
| `arvectum_data` — Data Platform | Recovery completed; `72` DP collections, consistent with the earlier independently verified recovery receipt |

The SHA/identity of the physical base matches the current DP-PITR health proof; original base/WAL files were not changed. This additional restore is materially distinct from the prior DP-PITR test, which only queried `arvectum_data`. A separate private logical prewrite `pg_dump` of `arvectum` and full isolated migration/rollback cycle `122→127→122→127` were previously verified as part of release `9b650a2b`.

**Boundary:** the physical base and named recovery point predate the upgrade to live schema `127_private_review_link_corrections`; this exercise therefore does **not** certify a physical recovery to schema 127 *after the deployment*. A post-deployment physical restore is a remaining acceptance item in [#685](https://github.com/arvectum2/tender-agent/issues/685).

## Seven-day continuity admission

The oldest locally verified DP and TA full physical bases are dated **20 November 2026**. On 21 November, this does not span seven days. Current `health: pass`, an active WAL receiver, backup checksums and a successful single target restore do **not** prove that every requested point in the trailing seven days can be recovered. The next possible horizon condition for those oldest bases is **27 November 2026**, conditional on uninterrupted retention and sufficient archived WAL; it is not an automatic pass on that date. An exact seven-day window test and post-deployment schema127 restoration are tracked in [#685](https://github.com/arvectum2/tender-agent/issues/685).

Original-source incident [#679](https://github.com/arvectum2/tender-agent/issues/679) remains separately blocked by live EIS SOAP timeouts. No source archive downloaded; no DTR replay, tender status changes, database writes, external bids, source grant expansion or backend restart occurred during the offline physical restoration test.
