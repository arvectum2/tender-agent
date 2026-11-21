# Tender Agent — repository consolidation and operational reconciliation, 21 November 2026

This is a read-only management audit, not production acceptance, procurement authorization or permission to delete worktrees. Scope: `arvectum2/tender-agent`, canonical main `abcd8727` (verified GitHub remote and successful CI/GitVerse).

The historical 20-Nov/early 21-Nov counts and approval statuses below are retained as an audit snapshot, NOT current production state. The independently verified update is appended below.

## PR history and integration
- Initial open PR count: 129. Exactly 81 open PRs whose pinned HEAD commits were already ancestors of main were retired dependency-safely, without deleting source branches or repositories. After creating review-only PR674: 49 open PRs observed.
- PR673 documentation-only reconciliation: exact head `5905e3c1`, CI 20/20 PASS before this follow-up audit.
- PR674: the exact PR657 source stack (contains PR640 and PR632), PR662 extension and PR618 standalone Workspace source. Initial candidate CI 19/19, 6569 PASS / 288 SKIP. Next extension `0720f079`: CI 19/19, 6649 PASS / 293 SKIP. Latest `c0efa7e6` integrates WSF07B read-only event projection, no registered route, no transport, no backend authorization assumed; exact final CI still being evaluated when recorded.
- PR660 is not equivalent to the current `private_review_bundle` module: its plan types (`FormPlan`, `AttachmentPlan`, `ReviewBundlePlan`) and test cases differ from current `ReviewItem`/`ReviewPlan`. Do not replace shared functions without compatibility acceptance.
- PR599 uses a different release-chain registry and endpoint (`reviewed-contract-registry`) from current event-sourced `reviewed-contracts` publication model and client pins. No direct overwrite, no publication; retain until independent feature comparison.
- PR637 is a historic immutable-release verifier/launcher branch; current system's daily launcher has evolved. Reconcile deployment source pin and current acceptance before reuse, not an automatic rollback.
- Remaining SIBUR/GEH/PQ, Gemma and B2B branches retain distinct scopes; no merge by inference.

## Git worktrees and local protection
- MI Git common repository registry: 183 worktrees; all checked worktrees clean. 114 HEADs ancestors of main and 69 not ancestors.
- Preliminary archive pool: 114 ancestor worktrees without open-PR branch references, active checkpoint directory markers or matching process argv. This **does not** prove safe deletion: inspect launchd definitions, process working directories, active immutable releases, delayed jobs, external references and checkpoint paths; verify recoverability before any removal.
- Additional SSD clone, separate Git common directory: 4 tracked modified files and 3 untracked paths; preserve as-is. MI checkout has 9 local commits beyond its upstream; preserve.
- Live launchd references include `tender-agent-mi`, `ta-gpb-discovery-20261114`, `ta-roadmap-tracks-20261114`, `ta-pitr-gate-20261120`, `ta-pg16-recovery-20261120`, and `ta-fresh-compute-turn-20261120`. None are deletion candidates without explicit revalidation.

## Runtime evidence, not acceptance
- Backend `127.0.0.1:8001/health` HTTP 200; Data Platform `127.0.0.1:8094/health` HTTP 200.
- Release fairness activation receipt records `state=activated` and `commit=abcd8727`. Research executor active. Governor records show normal batch limit 10, reduced limit 3 under sustained 99% GPU and recovery to normal; per-check exit 0 is not daemon failure.
- Dual TA PITR activation receipt shows `activated_pending_backup_observation`. Independently verify first live TA prewrite, rolling WAL and seven-day restore/retention gate; preserve old archives.
- Daily Tender Run launchd last exit code 20; older stderr has Data Platform indexing timeouts and historic docker-command failures, latest successful complete run not established. Do not blindly retry or assume all failures are current; reconcile source-scoped run/receipt, valid lock, prewrite and deployed script before changes.

## Remaining gates
1. PR674 exact full CI, focused source/tenant/privacy tests, independent integration review; PR673 new exact documentation CI.
2. Safe review of PR660 and PR599 incompatible alternatives, PR637 runtime safeguards and the remaining unique PRs.
3. Active original-source analysis, TA PITR recovery receipts, real company profile and legal/commercial acceptance.
4. Worktree archival only after reference audit and verifiable reversible backup.
5. Explicit owner/AM4 gates for merges, runtime changes and first paid pilot. No human GO, bid, payment, migration, signing, private data publishing or production deployment implied.

Canonical master roadmap and original Spec Kit source remain unchanged by this audit.

## 21-Nov verified correction

- PR #674 code merged as `9b650a2b`; PRs #681/#682 subsequently merged release/checkpoint proof. Owner separately approved production deployment, now live at backend SHA `9b650a2b` and DB revision 127. Daily `--preflight` PASS; health 8001/8094 HTTP 200. Main protected by PR and 10 strict CI checks, **no external GitHub reviewer required** (technical AI reviewer plus owner authority).
- The source grant covers **12 old admitted records, 9 excluded**, not 21 allowed. Three missing-original cases remain `WAITING_HUMAN` [#679](https://github.com/arvectum2/tender-agent/issues/679). One official SOAP response returned archive metadata, later bounded requests timed out without ZIP; no fabricated originals.
- Independent no-network and read-only-mounted DP-PITR physical restoration recovered **both** live-business-cluster DBs: `arvectum` pre-release schema 122/63 tender rows and `arvectum_data` with 72 collections. Separate TA-PITR protects another `arvectum_local` cluster, **not** a second copy of production. A physical post-schema127 restore and seven-day coverage remain NOT PROVEN [#685](https://github.com/arvectum2/tender-agent/issues/685).
- The earlier 183 worktree and PR inventory is **historical**; no automatic archival or deletion is authorized. No new ETP, legal, paid, DB/write or production mutation by this management correction.
