# MI-013 — Read-only dry-run and guarded import into production Data Platform

Date: 2026-10-27. Target machine: Mac mini only, via Arvectum Remote Cloud. **Do not touch MacBook Air or Windows devices.**

## Verified runtime

- Data Platform local API: `127.0.0.1:8094/health` returned production status `ok`.
- Correct DB: **`arvectum_data`** inside existing Docker container **`arvectum-postgres`**, PostgreSQL role **`arvectum`**.
- Schema: `dp_collections`, `dp_resources`, `dp_records` verified. Counts as inspected: 26 collections, 2192 resources, 2192 documents, 0 structured records. No MI-013 target collection exists, target resource count zero.
- The **different** database `arvectum` belongs to Tender Agent. The old assertion that Data Platform had not been deployed was incorrect; prior probes targeted the wrong database.
- Canonical source repo checkout is **dirty** on branch `feature/apr07-quality-slo-evidence` (4 changed tracked files), so DO NOT checkout the research branch in the current worktree.
- Branch `research/mi013-pq-corpus-20261027-pass2` exists on GitHub but is not fetched into this Mac mini repo yet; it must be fetched and staged in a *separate* worktree for runtime use.
- Backup directory already exists: `/Volumes/ArvectumSSD/Arvectum/runtime/data-platform-backups`.

## Data contract and counting

Read the v12 manifest. The dataset consists of **71 lot-level canonical research IDs**, not necessarily 71 independent EIS notices or 71 signed contracts. Its sources retain confidence tiers; mixed EPC/NMC must not be promoted to equipment sales. Source records must live as 71 `dp_records` with linked 71 `dp_resources`, isolated in collection `arvectum-market-pq-6-35kv` owned by `tender-agent`. Stable ID = SHA256(canonical procurement ID) prefix; reimport updates only modified records and maintains revision.

The importer at `scripts/market_intelligence/import_pq_postgres_v12.py` uses **standard library only**; Docker psql authenticates through the existing local container rather than reading or printing DB credentials.

## Distinct gates

### Gate A — source review and READ-ONLY check

Obtain owner consent for the *exact* Mac mini branch fetch/worktree command before executing via ARC (filesystem mutation). Preserve dirty current checkout by using a separate worktree:

```sh
git -C /Volumes/ArvectumSSD/arvectum/repos/tender-agent fetch origin research/mi013-pq-corpus-20261027-pass2
git -C /Volumes/ArvectumSSD/arvectum/repos/tender-agent worktree add --detach /Volumes/ArvectumSSD/arvectum/runtime/mi013-pq-import FETCH_HEAD
python3 /Volumes/ArvectumSSD/arvectum/runtime/mi013-pq-import/scripts/market_intelligence/import_pq_postgres_v12.py --check-db
```

Expected before import: 71 staged rows, database `arvectum_data`, 3 required tables, 0 PQ resources, 0 PQ structured records. Run the targeted offline tests before any write:

```sh
python3 -m pytest -q /Volumes/ArvectumSSD/arvectum/runtime/mi013-pq-import/tests/test_mi013_pq_corpus_v12.py /Volumes/ArvectumSSD/arvectum/runtime/mi013-pq-import/tests/test_mi013_pq_data_platform_export_v12.py /Volumes/ArvectumSSD/arvectum/runtime/mi013-pq-import/tests/test_mi013_pq_postgres_import_v12.py
```

If pytest unavailable, run the standard pinned `uv` venv from Tender repo only after confirming its dependencies; NEVER install packages as a side effect of preflight.

### Gate B — production backup and EXACT WRITING COMMAND

**Requires the owner's explicit approval of the specific production data mutation**, separately from generic "продолжай" consent. The approved operation is exactly: back up database `arvectum_data` via the existing Data Platform PostgreSQL backup script; in a single transaction create collection `arvectum-market-pq-6-35kv` and upsert 71 resource/structured-record pairs into the three already deployed dp tables; check read-back; no schema migrations, no delete, no restart, no other collection touched.

```sh
python3 /Volumes/ArvectumSSD/arvectum/runtime/mi013-pq-import/scripts/market_intelligence/import_pq_postgres_v12.py --apply --approved-command MI013-71-20261027 --backup-directory /Volumes/ArvectumSSD/Arvectum/runtime/data-platform-backups
```

The Python tool auto-creates a verified SHA256 custom-format `pg_dump` backup before any SQL mutations, refuses a missing or contradictory schema and aborts on identity collisions. It refuses unexpected existing PQ counts (unless empty or the complete previously imported set); all SQL is in one transaction with guards. On success it expects `resources=71`, `records=71` and unchanged existing collection counts except +1.

### Gate C — search / embeddings

**Structured ingestion is NOT a semantic indexing acceptance.** A record stored in `dp_records` is queryable by SQL and retained as original JSONB, but not necessarily retrievable from `dp_chunks` or `pgvector`. Follow-on task: use the native Data Platform ingestion API to create search documents/chunks and embeddings scoped to the new collection, retaining the same provenance. Benchmark exact identifiers, model names and numeric financial entries. Do NOT add embeddings during Gate B.

## Rollback

A custom-format backup of `arvectum_data` precedes Gate B. Do not restore the entire database over an active production state without a maintenance window. The importer is strictly idempotent for its own collection. If a rollback is needed, compare the new collection content and design a *collection-scoped* validated reversal first; never truncate all dp resources or disable other users.

## Blockers

- Branch not yet fetched to Mac mini, tests for v12 importer not yet CI-green.
- No explicit command-level approval for ARC's production-writing tool call; owner action is required at Gate B.
- Live import not run; do not claim those 71 records already in PostgreSQL.
