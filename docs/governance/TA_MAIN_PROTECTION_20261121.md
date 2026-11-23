# Main branch protection — active and owner-accepted 2026-11-21

Scope: `arvectum2/tender-agent`, `refs/heads/main` only. GitHub ruleset [27788179](https://github.com/arvectum2/tender-agent/rules/27788179) `AM4 - protect main (PR and CI)` is **active** with **no bypass actors**. Effective GitHub rules and required contexts were reverified after PR #674 code merge and production release.

## Technical enforcement

- `pull_request`: merging into main requires a PR, all review discussions resolved. No direct pushes.
- `required_status_checks`: **strict** base freshness and exactly ten checks: `dependency-lock`, `docker-build`, `quality`, `p6-03-arvectum-os-bridge`, `migrations`, `security`, `r8-postgres-integration`, `r8-acceptance-integration`, `redis-integration`, `Mirror repository`.
- `non_fast_forward`: no force push/history rewrite. `deletion`: no main deletion.
- GitHub required approval count is deliberately **0**, since the sole GitHub account `arvectum2` is also PR author. No additional person or account will be invited solely to satisfy a GitHub self-review rule.
- Owner-approved review model: **ChatGPT checks code, tests, security and rollback; the company owner makes the final merge and deployment decision**. This two-party operating process is documented in the PR/issue; ChatGPT is not misrepresented as a second human GitHub user or as a GitHub approval event. Strict CI does not replace owner authorization for production, EIS/ETP operations, documents or bidding.

## Evidence and decision history

- `GET /repos/arvectum2/tender-agent/rulesets/27788179` and effective main branch rules confirm activation and ten checks, without bypass actors. PR #680 was initially blocked while required checks ran and later reached 19/19 green; no force push or direct main push was used to test the gate.
- The company owner decided on 2026-11-21: no independent external reviewer; owner and AI engineer are the two reviewers in the work process. [Issue #676](https://github.com/arvectum2/tender-agent/issues/676) was closed **completed** after enabling PR + CI protection. One-review threshold is **not** an outstanding requirement.
- [PR #674](https://github.com/arvectum2/tender-agent/pull/674) was owner-authorized and normally merged as commit `9b650a2b818032389cfd6e13799acad33c72089b`, with exact source CI 19/19. A separate subsequent owner authorization explicitly re-bound the *same existing 12 admitted records (9 excluded)* from the old private WSF-07B source release to the new release; database was migrated `122→127`, backend and daily runner coordinated, health 8001/8094 HTTP 200. [Release verification checkpoint](../../.agent/checkpoints/TA-PROD-ROLLOUT-20261121.yaml) records proof. No auto-bid or commercial activation was permitted by this event.
- Remaining independent work: original-document/source gaps [issue #679](https://github.com/arvectum2/tender-agent/issues/679), full backup retention evidence, product acceptance and separate PR candidates. These are not a requirement for a third-party reviewer.

## Verify on every future merge

1. Verify exact current `main`, target PR head and CI requirements, including GitVerse. Inspect source changes, risk and rollbacks; take the owner's explicit merge decision. Draft PRs are not automatically merged.
2. Never alter ruleset to bypass CI for normal operation. Keep a record of any authorized emergency security change.
3. Preserve independent protected MI checkout, single existing Tender Agent Watchdog, backups and immutable production releases. GitHub merge does not automatically deploy and does not authorize marketplace bids, new source grants, DB writes or payments.
