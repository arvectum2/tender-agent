# Coordinated Mac mini maintenance — PostgreSQL / LLM / EIS Daily Tender

Status: **PREPARATION ONLY — NO DOWNTIME AUTHORIZED**, 23 Nov 2026 (Europe/Moscow). Owner requested careful preparation for a temporary all-LLM stop, PostgreSQL restart and deployment of a precise EIS deadline parser. This document is an operator-controlled maintenance gate, not a script that may be run blindly.

## Verified starting point

- Production Docker PostgreSQL: `arvectum-postgres`, PG **17.11**, image `pgvector/pgvector:pg17`, host loopback `127.0.0.1:55432`, Docker named volume `arvectum-postgres_arvectum_postgres_data`, restart policy `unless-stopped`. Production system identifier **7692004809331994662**; SQL identity `arvectum/arvectum`, Alembic `127_private_review_link_corrections`. Shared databases include `arvectum`, `arvectum_data`, and `postgres`.
- Distinct test PostgreSQL: `arvectum-local-e2e-db-1`, PG16. **Do not restart this test container by conflating it with production PG17**. There are two running archived-WAL receiver containers, `arvectum-ta-wal-receiver` and `arvectum-dp-wal-receiver`. Verify their receiver continuity both before and after any planned interruption; do not prune WAL.
- Production Tender Agent backend pinned to exact checkout `9b650a2b818032389cfd6e13799acad33c72089b`, wrapper `/Users/master/arvectum-ops/arv-075/scripts/tender-agent-backend-ssd.sh`. Daily Tender wrapper `/Users/master/arvectum-ops/arv-075/scripts/daily-tender-ssd.sh` **independently verifies the identical pinned SHA against the active backend marker and production DB identity**. A one-file hot-patch into a running server would violate the release boundary.
- Active model/AI services discovered: `local.llama-server-8081` (Gemma), `com.arvectum.embeddings` (Qwen3 Embedding, 4B), `sh.brew.ollama` (Ollama), `com.arvectum.reranker`, plus model consumers including `com.arvectum.ai-eng-001`, `com.arvectum.data-platform`, `com.arvectum.backend` and other workers. Many model services have `KeepAlive=true`: killing a PID alone can immediately restart it. **No LLM has yet been stopped**.
- Backup job `com.arvectum.docker-pg-backup` runs at **03:45 MSK** and backs up both PG containers. Latest independently hash-verified generation at **23-Nov 03:45 MSK** has 5 custom-format dumps + 2 global SQL files (7 files total, approximately 1.68 GB); TOC verification was performed. An additional **fresh no-prune** premaintenance generation is being prepared in a separate private destination. On-disk artifacts and restore keys must never be published into Git.
- PG17 physical WAL integrity was previously independently verified for archived full segments; **seven-day PITR / complete historical dual-db restore is NOT PROVEN** (issue #685). A valid archive checksum is not proof that any arbitrary prior state can be restored.
- Live core runtime replacement from the current `main` is **blocked** by separate DP ingest SLO / Gemma acceptance gates. Do not roll out unrelated Core changes as part of a parser fix (TA-CORE-RUNTIME-RELEASE checkpoint). The parser must be a selective hotfix based on the **currently pinned release**, not an unrestricted promotion of `main`.

## Parser release boundary

The new source-only parser:
1. Returns unknown instead of invented `00:00 МСК` when the EIS listing supplies only a calendar date.
2. Fetches only a bounded set (at most 12) of potentially relevant EIS shortlist details via strict first-party `https://zakupki.gov.ru` GET, explicit registry identity, TLS, no redirects and finite byte/time limits.
3. Parses the *detailed* field “Дата и время окончания срока подачи заявок” with explicit `МСК±N`; independently verified against 196 archived real EIS originals.
4. Writes the official raw HTML and SHA-256 source receipt to a private 0700 root under `ARVECTUM_DAILY_EIS_EVIDENCE_ROOT` before storing exact time; a missing archive, invalid response or source mismatch remains **unknown** (manager review), never fictitious precision.
5. Re-screens exact known expired deadlines before expensive analysis; preserves real published midnight times.
6. Does **not** submit bids or change existing 299 historic rows, previously corrected 35 manager deadlines or two genuine midnights.

Source PR and pinned-base release candidate have separate identities. Only an approved pinned hotfix can replace the production backend release; any release must retain a clean immutable checkout, compatible venv, DB identity and access-manifest admission, source and runtime receipts.

## Hard NO-GO — abort before touching running services if any apply

- Owner has not explicitly declared **maintenance window started** and approved expected downtime / affected projects.
- No *fresh* independently SHA-verified backup after the latest production changes, no successful isolated restore acceptance, or insufficient independent recovery space.
- Unexpected PostgreSQL database system identity, schema revision, active DDL/migration, non-idle or unreconciled jobs, current backlog/in-flight queue effects, stale or broken WAL receiver.
- Active Tender Agent analysis, uncommitted business transaction, MAX2TG delivery ambiguity, data-platform ingest, scheduled task crossing the window, or any unapproved interruption to the 07:00 MSK commercial digest / 08:00 MSK Tender Agent cycle.
- Resource governor signals unacceptable pressure, disk shortage, non-AC power, no proven old-revision backend rollback or new-version source/venv mismatch.
- Pinned Core/PRICE01 full release is confused with parser-only hotfix; 9/9 CI and GitVerse mirror for exact parser release candidate have not passed.
- A PostgreSQL **upgrade** or destructive migration is proposed; user authorized preparing for a *restart*, not a new major version.

## Proposed controlled execution **after separate maintenance-start approval**

1. Record timestamp; preserve full before-state `launchctl` jobs and Docker IDs, active backend marker, current exact SHA, queue/receiver statuses, private source receipts and business run checkpoints. Verify single existing Tender Agent Watchdog will not resume a write in the maintenance window. Do not create a second watchdog.
2. Confirm new no-prune backup and independently verified isolated restore, latest WAL receiver checkpoints and PostgreSQL transaction/drain readiness. Stage old and new backend wrappers, source/venv and private manifest with verified rollback snapshots (0700/0600).
3. Temporarily block new model/DB work at sanctioned service boundaries; allow in-flight transactions to finish. Drain, do not purge or replay MAX2TG queues. Suspend scheduled Daily Tender, any applicable LLM-consuming workers and timers that overlap window. Keep ARC reachable and retain its own daemon; do not boot out ARC, UPS monitor or unrelated OS network services.
4. Stop **all** confirmed local model-serving LaunchAgents (Gemma, Qwen embeddings, Ollama and reranker) using their service managers, not just `kill` (several auto-restart). Confirm PIDs and localhost model endpoints are absent. Do not load a second Qwen. Preserve previous jobs and settings for exact reverse restore.
5. Stop/drain PG17-dependent workers and backend, prove no active write transactions; only then restart **`arvectum-postgres` PG17, same image and same named data volume**. Do not remove container/volume, `down -v`, `prune`, apply migrations or reset WAL. PG16 test instance remains untouched absent separate owner instruction.
6. Verify the same PG17 system identifier and databases, Alembic revision, read-only counts and updated 35 manager deadlines, `pg_isready`, WAL receiver archive continuity and no recovery/replay errors. If any hard check fails, hold off consumer restarts and follow documented rollback.
7. In a separate pinned-release transaction, switch backend and Daily Tender wrapper **together** to the new selective parser hotfix: exact source SHA, clean readonly checkout, matching venv, private workspace admission and backend marker. Preflight old/new checks and source archive 0700; run focused parser dry/smoke (no bids and no arbitrary database writes).
8. Resume DB clients, LLMs and scheduled jobs **in reverse dependency order**; confirm existing queues retain cursor/ACK identity. Independently verify Data Platform and Tender Agent health/readiness and one safe source-backed EIS parsing acceptance; avoid declaring overall HEALTHY without proof. Keep the 07:00 and 08:00 scheduled cycles unchanged.
9. Finalize `.agent/current-task.yaml` with exact release hash, backups and rollback handles, timestamps, read-only database proofs, smoke results and unresolved gates. If a check fails, restore **the original pinned backend code/wrappers and all previous service states**, not unrelated projects. Preserve evidence. A PG restart should be reversible by restarting the same intact container/volume; full DB restore is a separate high-impact action requiring its own evidence/authorization.

## Acceptance conditions

The checkpoint may be `completed` only after independently verified actual downtime/cutover, PG17 database/recovery identity and WAL, model resume and ready state of relevant consumers, one complete 07:00/08:00 production schedule, original backups, and source-bound parser proof. Staging and synthetic tests alone are not an operational deployment.
