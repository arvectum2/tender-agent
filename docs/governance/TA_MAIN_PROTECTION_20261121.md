# Main branch protection — activated 2026-11-21

Scope: public GitHub repository `arvectum2/tender-agent`, **only** `refs/heads/main`. Ruleset [27788179](https://github.com/arvectum2/tender-agent/rules/27788179), name `AM4 - protect main (PR and CI)`, mode **active**, no bypass actors. This is a repository-settings change, not a production deployment or an amendment of corporate AM-4 decision authority.

## Effective GitHub checks

- `pull_request`: all changes to existing main through a PR; required review discussions must be resolved. Direct pushes do not meet this rule.
- `required_status_checks`: **strict** merge-base freshness, ten named statuses:
  `dependency-lock`, `docker-build`, `quality`, `p6-03-arvectum-os-bridge`, `migrations`, `security`, `r8-postgres-integration`, `r8-acceptance-integration`, `redis-integration`, `Mirror repository` (GitVerse).
- `non_fast_forward`: reject history rewrites/force pushes.
- `deletion`: prevent deleting main.

Verified with both `GET /repos/arvectum2/tender-agent/rulesets/27788179` and `GET /repos/arvectum2/tender-agent/rules/branches/main`. The ten contexts are shared by existing CI-green PRs #673, #674, #675, #677, #678; `criterion-review` is a separate, conditional job and intentionally is **not** globally required. GitVerse is required intentionally to keep the GitHub/GitVerse mirrors in sync; if it fails transiently (e.g. provider HTTP 502), repeat the failed mirror job after checking the cause, never bypass its evidence.

## Reviewer limitation (not satisfied)

`GET /repos/arvectum2/tender-agent/collaborators` returned exactly one person, `arvectum2`, who authored PR #674. GitHub cannot count an author's self-approval as an independent review. A one-review minimum today would make every owner-authored PR permanently blocked until a second eligible collaborator is invited. Therefore this *initial technical policy* uses `required_approving_review_count=0`, no bypass. This does **not** waive the separate AM-4/owner independent-review release gate. Before raising the threshold to 1, a named independent collaborator must be added and accept the invitation; then update rule 27788179 and prove both an unreviewed PR is blocked and a valid independent review can unblock it. Do not fabricate a reviewer or treat a green CI as authorization.

## Release and recovery limits

- [PR #674](https://github.com/arvectum2/tender-agent/pull/674) remains draft and **unmerged** with 19/19 CI checks and 6,683 hosted tests passed. Independent review/AM-4 authorization, migration rehearsal, pinned runtime deployment/rollback, source-original [#679](https://github.com/arvectum2/tender-agent/issues/679) and ongoing PITR/retention criteria remain separate.
- A repository admin may modify/disable ruleset 27788179 in GitHub Settings > Rules > Rulesets, but that is an **audited emergency change**, not a routine merge bypass. To revert, restore the prior conditions explicitly and document why. Keep the single Tender Agent Watchdog and protected local MI checkout unchanged.
- The setting does not silently authorize an ETP application, live source fetch, migration, production activation, archive deletion or any payment.

## Verification procedure

1. Read `GET /repos/arvectum2/tender-agent/rulesets/27788179` and `GET /repos/arvectum2/tender-agent/rules/branches/main`; require the exact active main target, rules, empty bypasses and ten named contexts.
2. Review the green exact-head CI and GitVerse mirror for a PR; verify no `main` commit changed merely from enabling protection.
3. Use a normal **non-draft** documentation-only PR, confirm required checks are not satisfied while it is newly opened and later show verified completion; do not attempt a direct real write to `main` just to test rejection.
4. Leave issue [#676](https://github.com/arvectum2/tender-agent/issues/676) open until the independent reviewer and one-review rule are installed and negative/positive review gating tested.
