# Tender Agent Watchdog — Maximum Productive Run (ChatGPT via ARC)

Owner directive, 2026-10-27. Applies to hourly **existing** Tender Agent Watchdog, task `TA-MI-AUTONOMY-20261027`. No OpenAI API or local LLM: reasoning is done by the ChatGPT model executing the scheduled task; ARC is the Mac mini execution channel.

## Work-conserving execution

1. On entry, honor the existing GitHub issue #57 run-start comment requirement. Read canonical task checkpoint, real git state, source receipts, queue and existing lease; do not overwrite the unrelated roadmap `.agent/current-task.yaml`.
2. Run repeated bounded batches: discover original procurement sources, prioritize PQ candidates, extract and hash documents, enqueue source-bound packets, reason over excerpts in the current ChatGPT scheduled execution, validate exact quotations and SHA, persist decisions and provenance, ingest to authorized tenant-scoped Data Platform only after checks, then immediately process the next batch.
3. Do not stop at one case, commit, test or progress message. Continue until platform/tool execution limits approach, no safe executable work remains, or a genuine blocker is reached. Target 50–55 minutes **only if the platform permits**; reserve 3–5 minutes when remaining time is observable. Do not sleep to pad runtime or assert guaranteed duration.
4. Persist checkpoint and receipts after each completed batch, including counts, source IDs, hashes, classification, verification state, last tested commit and exact resume instruction. Every stage must be idempotent or safely reconciled on replay.
5. Use a **short cooperative lease** (300-second TTL, periodic renewal, unique owner). Only the owner may renew/release. Expired/unreadable leases require inspection of actual process/transaction state before recovery; expiry alone is **not** permission to delete locks, kill jobs or start conflicting mutations. If safe recovery cannot be proven, work on independent read-only batches or report blocked. Never block indefinitely waiting for a lease.
6. Avoid large irreversible operations near run end; atomically persist results and release owned resources. No automatic signature, procurement application, supplier outreach, spending, production mutation or fabricated contract evidence.
7. On exit update the same issue #57 report comment, checkpoint and next-step instruction. The next hourly invocation resumes verified unfinished work rather than repeating it.

## Implementation boundary

`src/modules/market_intelligence/pq_run_lease.py` provides lease acquire/renew/release/inspect. It **does not** implement stale-lease takeover: that must be coordinated with a process-aware runtime supervisor and verified state before adding automatic recovery. Scheduled ChatGPT invocations can be shorter than the target runtime. This document cannot override platform execution limits or guarantee no overlap at the ChatGPT scheduler level.
