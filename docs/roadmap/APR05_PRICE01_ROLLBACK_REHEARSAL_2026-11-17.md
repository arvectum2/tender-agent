# APR-05 — PRICE-01 rollback and entitlement rehearsal

Synthetic, in-process HTTP acceptance against the actual SaaS API and disposable SQLite fixture. No real users, payment, production deployment, source acquisition, or external traffic.

## Evidence

- Owner-approved PR #603 merge: `b843f92ca129dcf9a57bd7935fb53ec31c1372dc`, exact pre-merge CI 19/19, full quality 5987 passed / 288 skipped / 0 failed.
- Test `test_price01_pilot_entitlement_and_nondestructive_rollback` creates two synthetic tenants and one estimate, actual snapshot, approved internal norm in the first tenant. It saves the eight read responses and tests seven valid write/preview requests; disables PRICE-01 master flag and SaaS master flag separately (404), expires trial (402), suspends tenant (403), verifies unacknowledged member legal hold (428). Re-enabling preserves all exact read payloads and idempotent saves; foreign tenant sees no protected records and empty own catalog. No new immutable versions or payment evidence.
- 79 passed, 2 skipped (APR05 / migration / packaging / Node UI); focused rerun 1 passed; Ruff and diff check PASS. Test-only commit `d5cc68a48979d587f43efc94db84a121d8950c58`.

## Deployment boundary and next gate

This is application-level rehearsal, not process restart, physical device or backup/restore acceptance. For isolated deployment, use a dedicated disposable Postgres instance/directory and fresh application settings, verify actual migration to revision 122, saved-history backup and restore on a separate database, exact image packaging and kill-switch restart. Do not downgrade populated immutable histories. Never enable new flags on a live tenant or use actual legal acceptance without separate Owner approval. No live commercial/production decision follows from this rehearsal.
