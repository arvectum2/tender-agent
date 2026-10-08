# Mac mini: canonical Tender Agent runtime on ArvectumSSD (2026-10-08)

## Source and deployment invariant

* Canonical GitHub repository: `arvectum2/tender-agent`, protected `main`.
* Canonical local checkout: `/Volumes/ArvectumSSD/Arvectum/repos/tender-agent`. Do not develop or launch production out of legacy `~/arvectum-runtime/AI-Corporation*` or ad-hoc `/tmp` clones.
* On 2026-10-08, GitHub `main`, local `main` and live backend SHA all matched `958e94c740e73a052f275d46fea713f01ab4d117`. CI for this exact GitHub SHA was green.
* Root cause fixed: prior LaunchAgent started `~/arvectum-runtime/AI-Corporation-next` at `f130703e`, **81 commits behind** GitHub `main`.
* LaunchAgent `com.arvectum.backend` now runs **/opt/homebrew/bin/node** with `/Users/master/.local/bin/tender-agent-backend-node.cjs`. The wrapper always executes `$CANONICAL/scripts/runtime/start.sh` with `cwd=$CANONICAL`; source, Python venv and running process cwd are on SSD.
* Private environment copied byte-for-byte to `/Volumes/ArvectumSSD/Arvectum/private/tender-agent/runtime/backend.env`, mode `0600`, with private parent mode `0700`. Legacy copy retained as rollback. DO NOT log or commit its values.
* Runtime identity marker: `/Volumes/ArvectumSSD/Arvectum/runtime/tender-agent/backend-active.json`, mode `0600`, includes pinned commit, start time, process PID and source directory.
* Verification: `python3 scripts/runtime/verify_macmini_backend.py` (source path on this branch; after PR merge this will be on canonical `main`). It reads GitHub `main`, Git `HEAD`, launchd config, listener cwd/PID, marker SHA and HTTP /health. All 13 checks passed following launchctl restart.

## macOS removable-disk gate

The user already approved several `node` binaries under Full Disk Access. After a Homebrew update, stale Desktop Commander Node process could not read SSD; restarting its launchd agent switched it to permitted Node 26.11.0. Direct `/bin/bash` as a LaunchAgent still got TCC `Operation not permitted` on SSD even though a terminal child could read it. A **Node.js LaunchAgent parent** was verified to read the SSD and launch a Python backend child from SSD. This is why the stable LaunchAgent points at the host Node wrapper, not directly at the SSD shell script. If a later Homebrew Node upgrade breaks access, recheck FDA for its actual executable and restart only the corresponding service.

## Live cutover verification and rollback

Canaries were tested on ports 18081 (interactive) and 18082 (launchd). Both returned HTTP 200; `/docs` was appropriately HTTP 401 without authentication. A failed first launchd switch was automatically reverted; root cause was the TCC denial from a direct `/bin/bash` LaunchAgent. The corrected Node-based deployment passed, and a forced `launchctl kickstart -k gui/501/com.arvectum.backend` successfully restored HTTP /health=200, with 13/13 runtime identity checks true.

Private rollback plist: `/Users/master/arvectum-ops/maintenance/com.arvectum.backend.plist.before-ssd-20261008` (chmod 0600). Protected host switch script: `/Users/master/arvectum-ops/maintenance/switch_backend_to_ssd.py`. If rollback is needed, stop `gui/501/com.arvectum.backend`, copy the saved plist into `~/Library/LaunchAgents/com.arvectum.backend.plist`, chmod it 0644, bootstrap it again and check `http://127.0.0.1:8001/health`.

## Current open work preserved ON SSD

* PR #227, latest `af132615`: `/Volumes/ArvectumSSD/Arvectum/worktrees/apr02-223fz-20261008`.
* PR #228, latest `f2113534`: `/Volumes/ArvectumSSD/Arvectum/worktrees/operator-workspace-roadmap-20261008`.
* PR #229: `/Volumes/ArvectumSSD/Arvectum/worktrees/ops-macmini-runtime-20261008`, a branch derived from current PR head.
* All are independent Git worktrees of canonical `tender-agent` repository; **do not treat open PR code as merged main**. Other worktrees contain unique changes or dirty files and were intentionally preserved.

## Future GitHub-to-Mac synchronization protocol

After a PR is reviewed and merged into GitHub `main`, **green CI on GitHub alone does not mean Mac mini has deployed that SHA**. The owner/host deployer must:
1. Check the target GitHub main SHA and exact-head CI/required checks; do not deploy a red or unreviewed commit.
2. Confirm canonical `main` clean with `git status --porcelain`; do not discard any local modifications.
3. `git -C /Volumes/ArvectumSSD/Arvectum/repos/tender-agent fetch origin main` then fast-forward **only**, never `git reset --hard` on the canonical checkout.
4. Run targeted regression and parallel canary on a separate local port with private runtime env. Confirm app starts, HTTP /health=200 and expected guarded routes.
5. Stop canary; reload `com.arvectum.backend` via `launchctl kickstart -k gui/501/com.arvectum.backend`. On failure, use rollback package before further changes.
6. Run `verify_macmini_backend.py`, require **all** checks pass. Compare **GitHub SHA = disk SHA = active backend SHA**, not merely local Git versus origin.
7. Retain previous deployed commit and backup until health and functional smoke are verified.

Never silently promote unmerged PRs or change production launch paths to a temporary clone. If a scheduled rollout is introduced, it MUST reproduce these exact-head CI, canary, clean-tree, fast-forward and rollback gates; a blind `git pull && restart` is not acceptable.

## Installed hourly read-only drift guard

A separate macOS health task «com.arvectum.tender-agent-drift-guard» runs every 3600 seconds (NOT a second ChatGPT roadmap watchdog). It invokes the source-versioned «macmini_backend_drift_guard.cjs» through the already authorized Node runtime. It does not pull, merge, change files, or restart a service. On transition from a fully healthy state to drift it requests a local macOS notification, with the detailed result in:

* «/Volumes/ArvectumSSD/Arvectum/runtime/tender-agent/backend-drift.json»
* «~/Library/Logs/Arvectum/backend-drift-guard.log»

First real launchd run: **13/13 checks PASS**, GitHub=disk=active «958e94c», exit 0. Its launch configuration points to «/Users/master/.local/bin/tender-agent-backend-drift-guard.cjs» and installed verifier «/Users/master/.local/bin/tender-agent-backend-verify.py», copied from this repo's versioned scripts. An unmerged or missing next GitHub deployment will be detected, not silently presented as current. Production auto-deploy is intentionally not enabled without separate CI/staging/rollback automation.

The obsolete original temporary clone «/tmp/tender-agent-roadmap-20261008» was removed after proving it had no dirty files and its SHA exactly matched the SSD APR-02 worktree «af132615». Active runtime and original private configuration backups remain available.
