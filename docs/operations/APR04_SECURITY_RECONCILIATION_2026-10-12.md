# APR-04 — current-main merge and private onboarding gate (2026-10-12)

Integration branch: `feature/apr04-reconciled-20261012` (based on TA main 6e737d69, merged original PR #252 branch). No production deployment.

- Original APR-04 PR #252 had 419 main-side commits since its fork, but conflict in only three governance/roadmap files. The latest main versions were preserved. Source, UI, deployment and 50 original APR-04 test changes were integrated without source conflicts.
- Discovered security boundary: `/pilot/onboarding` and `/api/onboarding/customers*` were protected only when optional app-wide pilot authentication was correctly configured. Disabled/narrowed auth could expose company records and document endpoints. Added an explicit router-level fail-closed dependency checking enabled/safe Basic auth AND path-scope protection for both UI and API prefixes before any route executes. When misconfigured, these routes return HTTP 503.
- Added tests for auth disabled and mis-scoped prefixes. Existing domain/ownership tests use an explicitly overridden route gate within isolated unit fixtures, never in runtime.
- Focused integration/security tests: 57 PASS. Targeted Ruff PASS, Python compile PASS, `make check` PASS.
- Unexcluded full Python test suite with PostgreSQL 16 matching `pg_dump/pg_restore`: 3954 passed, 238 expected skipped, 0 failed, 305 warnings. Initial inherited Homebrew PG18 CLI produced the previously documented R9 backup/restore environmental failure; with PostgreSQL 16 CLI isolated R9 5/5 PASS and then full suite PASS. No global CLI reconfiguration.
- **Important:** This is code readiness only. APR-03B owner browser/semantic acceptance is still outstanding; APR-04 live organizational acceptance and any production or public rollout require separate explicit owner approval. No external bid action, signing, paid model transport, public access or watchdog restart.
