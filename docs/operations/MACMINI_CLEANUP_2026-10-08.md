# Mac mini cleanup and canonical Git discipline — 2026-10-08

## Single source of truth

For **Tender Agent**, the canonical Mac mini repository is:
`/Volumes/ArvectumSSD/Arvectum/repos/tender-agent`.

It is a clean checkout of `arvectum2/tender-agent` at GitHub main commit `958e94c` (verified on 2026-10-08). `/Users/master/arvectum-runtime/AI-Corporation` and `/tmp/tender-agent-roadmap-20261008` are **not** canonical. Never run new product work in these legacy/temporary clones by default. Other company canonical repositories are siblings in `/Volumes/ArvectumSSD/Arvectum/repos/`.

## Fixed macOS Removable Volumes / Desktop Commander access

The desktop agent used an older deleted Node.js executable `/opt/homebrew/Cellar/node/26.10.0_2/bin/node`, even after `/opt/homebrew/bin/node` advanced to `26.11.0`. A simple permission list showed multiple `node` entries with FDA enabled but filesystem reads still received `EPERM`. A controlled `launchctl kickstart -k gui/501/com.arvectum.remote-desktop-commander` restarted the existing KeepAlive service under Node.js `26.11.0`; it reconnected and subsequently listed the canonical SSD successfully. Do not add more broad FDA grants unless a *new* access failure is confirmed.

## Verified Mac mini cleanup and evidence

| Item | Work | Measured release |
|---|---|---:|
| Homebrew downloads | Deleted 77 files older than 45 days, only regenerable downloads | 2.648 GiB |
| Xcode DerivedData | Removed six stale duplicate build-output directories for PhotoPodRazmerIOS and HabitsByArvectumIOS; kept latest two per app and all archive/release files | 6.026 GiB |
| Service diagnostic logs | Kept private last-16-MiB snapshots; truncated live Desktop Commander stdout and backend stderr logs in place | 1.620 GiB |
| Tender Agent worktrees | Removed four clean August-era worktrees with `HEAD` ancestor of `origin/main`; no `--force`, no branch removal | Separate SSD cleanup |

**Total regenerable file content removed from internal volume:** approximately 10.294 GiB by file measurements. Filesystem `df -h /System/Volumes/Data` changed from ~311 GiB used / 110 GiB free to **302 GiB used / 120 GiB free**. Canonical SSD remains 232 GiB used / 3.4 TiB free.

## Worktree and runtime dependency safety

Before removal, `git worktree list --porcelain` yielded 62 Tender Agent worktrees; four had working-tree changes. After the four safe removals, 58 remain. These are **not all duplicates**; many hold unique branch commits or test/runtime state. Do not broadly `rm -rf` them, even if the directory names look old.

The running `com.arvectum.backend` LaunchAgent refers to `/Users/master/arvectum-runtime/AI-Corporation-next` (a registered canonical-repo worktree on branch `runtime-deploy`). A separate `data-platform` process and `reranker` have dedicated runtime trees. Moving/removing those without a tested deployment/rollback could cause an outage. This task did **not** repoint or restart those services.

Xcode 27.0 is the only installed Xcode app; keep watchOS 27.0 and the currently booted iOS 26.5 simulator. Other iOS 27.0 simulators have recently been used. `~/.cache/uv` is held by a live process; do not force-clear it.

## Local private evidence (do not commit raw logs)

The Mac mini contains manifests and logs under `/Users/master/arvectum-ops/maintenance/`:
`git-copies-audit-20261008.json`, `tender-worktrees-audit-20261008.json`, `old-worktrees-prune-20261008.json`, `homebrew-prune-20261008.json`, `deriveddata-prune-20261008.json`, `active-log-trim-20261008.json`. Private 16-MiB log tails stay only on Mac mini.

## Pending higher-risk work

1. Review four dirty worktrees and 54 other registered worktrees, including unique commits, active agent references and downstream workflow paths.
2. Coordinate backend runtime migration away from `AI-Corporation-next` to a vetted, reproducible deployment from canonical SSD with tests and rollback.
3. Decide retention for current simulator test data, CoreDevice data, `uv` caches and still-recent worktrees. Never purge them based on size alone.
4. Restore the APR-02 223-FZ work from existing GitHub PR #227, rather than inventing an unrelated clone.

This report is a **safe-cleanup milestone**, not authorization to remove active service directories or force-delete unmerged code.
