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
- All 34 remaining historical branches with unique commits were **renamed losslessly** into `archive/2026-09-18/*`: each archive ref points to the exact original commit SHA, and only after successful archive creation was the original branch deleted.
- Before merging this bookkeeping branch: **36 remote branches = `main` + this temporary hygiene branch + 34 archive branches**.
- Expected after merging/deleting this branch: **35 remote branches = `main` + 34 explicitly archived historical refs**. There will be no other active-looking remote branch.

## Why 34 archived historical refs remain

They contain unique unmerged commits relative to current main, or represent unrelated recovery history. Instead of deleting recoverable work or leaving it mixed with active branches, every one was moved to the `archive/2026-09-18/` namespace at the identical commit SHA.

Preserved areas include:
- reproducible dependency/lock experiments;
- EIS diagnostics and older production-ingestion experiments;
- benchmark/control hardening variants;
- ARV-001 and PILOT recovery/quality experiments;
- old Redis/storage OpenCode work;
- MacBook recovery history;
- two supplier-engine discovery adapter variants whose current-main implementation is newer but whose branch documentation/history is not fully byte-equivalent.

A future semantic pass may inspect these archived refs and either port missing value or delete the archive refs with explicit evidence. They no longer appear as active development branches.

## Next development increment

Recommended next bounded task: **issue #83 — PROCUREMENT-KANBAN-V1-001**, mapped to historical **ARV-019** with strategy **COPY_PATTERN**.

Rationale:
- canonical `Deal`, `DealStatus`, status history/rules and Commercial Operator Console already exist;
- the roadmap explicitly classifies kanban as commodity operator UX, so the correct move is a thin board over existing state rather than another workflow/CRM subsystem;
- v1 can be repository-only, reversible, and free of procurement/external side effects;
- human status changes, if exposed, must use the existing status-engine gate and cannot create automatic participation/submission behavior.

Issue #83 is a recommendation/candidate only until Product Owner queue admission.
