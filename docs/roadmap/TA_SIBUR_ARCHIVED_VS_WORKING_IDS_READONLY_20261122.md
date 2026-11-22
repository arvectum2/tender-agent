# SIBUR — independently verified historical archive vs working PG16 ID gap, 22 Nov 2026

Child TA-SIBUR-HIST-GAP-READONLY-20261122, issue #692.
Exact historical identity discrepancy is now independently reproducible
from 4052 SHA-pinned original first-party archived pages and one bounded
READ ONLY working research PostgreSQL 16 snapshot. Root cause remains
UNKNOWN; no current active-procurement status or source rights are inferred.

## Independently re-read source evidence

Original first-party archive: nine categories under existing private
sibur-archive-discovery, 4052 original page receipts and matching raw bytes.
Saved archived-corpus proof SHA256
07c4ce310b28dec397aa927f9cbcbfaeb6d9374017038c03c2a59a0af25c7f0d.
Prior independent gap receipt SHA256
069a8ce4fd0b6d74b6f3866df3116b9019c5cf0b13f1c45a198c76d2efd81085.

Working local research DB arvectum_local (PG16 system identifier
7694400479046774822), distinct from production PG17.
Only an explicit REPEATABLE READ READ ONLY transaction using local
Docker Unix socket collected unique exact sibur_public source IDs.
No credentials, original IDs or raw SQL results were committed.

| Independent result | Observed |
| --- | ---: |
| Archived original first-party pages rechecked | 4052/4052 |
| Archived row observations | 48536 |
| Archived unique external IDs | 48332 |
| Working research DB unique source IDs | 30632 |
| Exact ID overlap | 30081 |
| Archived source IDs absent in working | 18251 |
| Working IDs not present in nine archived categories | 551 |

All three complete SHA256 sets (archive exact IDs, working exact IDs and
missing historical IDs) matched their separate prior receipts, as did all
nine source category missing counts: 107=2035; 108=4883; 109=1008;
112=3925; 132=3891; 999_08=653; 999_10=803; 999_11=994; 999_19=59.
Sum 18251. These are historical archive IDs, NOT 18251 active or
import-approved tender opportunities.

Proof created once privately (mode 0600, 1101 bytes):
sibur-archive-working-gap-exact-20261122.json, SHA256
4dae9e36df79dbbf678fab5264a4e60de378d71fd391e8b7d7e71280e39151a8.
Proof contains only counts and SHA fingerprints, zero exact source IDs.

## Repeatable constrained tool

The repository auditor
scripts/research/audit_sibur_archived_working_id_gap.py
defaults to no-database archived original replay. Explicit
--with-working-db-readonly requires --private-proof-output on a new
destination. The only database access is a fixed research PG16 container
arvectum-local-e2e-db-1, with REPEATABLE READ READ ONLY and explicit
cluster ID and ID-set SHA checks. It cannot insert, import, send,
download, enable ETP access or contact production PG17.

Eleven synthetic checks prove exact diff, count/SHA tamper fail-closed,
wrong cluster/write-mode denied, and single-create private proof.
No network requests, DB/DP/production mutations, bids or payments.

## Outstanding issue #692 acceptance

This result proves WHAT differs, not WHY. Neither importer filter
decisions, retention, category-specific omissions nor time-window
coverage causality were proven. The 551 working-only IDs may represent
other source categories, not corrupt data.

Continue only with separately scoped, read-only historic ingestion
checkpoint/provenance analysis and a proposed DRY RUN repair plan.
Mass importing 18251 historic IDs, new DP indexing or changing source
retention requires distinct Owner/MI/PITR/rollback authorization.
Issue #692 remains OPEN pending the root cause and authorized correction.
