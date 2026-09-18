# Tender Agent branch hygiene — 2026-09-18

## Result

Repository branch cleanup was performed conservatively against canonical `main`.

- Starting remote branch count: **143 including `main`**.
- Stale open PRs closed as superseded: **#12, #45, #48**.
- First safe-delete batch: **93 branches**, all either direct ancestors of `main`, backed by merged canonical PRs, or explicitly superseded by completed work.
- Second safe-delete batch: **11 branches** whose branch-touched final files were byte-identical to `main`.
- Additional completed maintenance branches removed after merge: `owner/roadmap-sync-20260918`, `chore/project-watchdog-config`, and stale checkpoint-only `agent/reuse-first-001`.
- Roadmap sync PR #82 merged as `edd35979` after exact-head CI `35312663415` success.
- Project Watchdog binding PR #78 refreshed to current main, updated with the 2026-09-16 AM-4 renewal source, and merged as `aa5aa7a` after exact-head CI `35313488952` success.
- Before merging this bookkeeping branch: **36 remote branches including main and this branch**.
- Expected after merging/deleting this branch: **35 remote branches = main + 34 preserved historical branches**.

## Why 34 historical branches remain

They were **not** deleted because they still contain unique unmerged commits relative to current main, or represent unrelated recovery history. Branch-name age alone is not sufficient evidence for destructive deletion.

Preserved areas include:
- reproducible dependency/lock experiments;
- EIS diagnostics and older production-ingestion experiments;
- benchmark/control hardening variants;
- ARV-001 and PILOT recovery/quality experiments;
- old Redis/storage OpenCode work;
- MacBook recovery history;
- two supplier-engine discovery adapter variants whose current-main implementation is newer but whose branch documentation/history is not fully byte-equivalent.

A future archive pass may inspect these semantically and either port missing value, tag/archive them, or delete them with explicit evidence. Automatic deletion is prohibited until that review.

## Next development increment

Recommended next bounded task: **issue #83 — PROCUREMENT-KANBAN-V1-001**, mapped to historical **ARV-019** with strategy **COPY_PATTERN**.

Rationale:
- canonical `Deal`, `DealStatus`, status history/rules and Commercial Operator Console already exist;
- the roadmap explicitly classifies kanban as commodity operator UX, so the correct move is a thin board over existing state rather than another workflow/CRM subsystem;
- v1 can be repository-only, reversible, and free of procurement/external side effects;
- human status changes, if exposed, must use the existing status-engine gate and cannot create automatic participation/submission behavior.

Issue #83 is a recommendation/candidate only until Product Owner queue admission.
