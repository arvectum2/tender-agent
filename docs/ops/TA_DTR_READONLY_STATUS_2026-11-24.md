# Daily Tender Run — bounded read-only status probe, 24 November 2026

This is a diagnostic source-only change, not a production deployment or a way to start, resume, retry or modify Daily Tender Run.

## Why

The 24-Nov scheduled workflow legitimately remained RUNNING / ANALYZE while individual rows advanced to MANAGER_READY. Previous investigations used raw SQL or the full /api/daily-tender-runs/latest projection, which can include procurement/customer metadata. The dedicated local CLI reports only aggregate status.

## Safe invocation

From an authorised Tender Agent checkout with an already configured and separately approved existing runtime environment and Python interpreter:

    python -m scripts.ops.read_daily_tender_status

The command has no arguments and strictly limits scope to profile arvectum-it on PostgreSQL database arvectum and role arvectum. It starts REPEATABLE READ READ ONLY, then issues one database-identity SELECT, one latest-run SELECT, and at most one item-grouping SELECT. It always rolls the transaction back. It never accesses source documents, sends requests to EIS/ETP, calls an LLM, starts DTR, touches payment/bid routes, or prints raw error text.

JSON contains only allowlisted status/stage codes, structurally valid run ID, UTC timestamps, elapsed minutes since last recorded DB change, item-status counts and an error-present Boolean. Unknown status becomes OTHER; an unsafe run ID becomes REDACTED. Database failure prints only DTR_READONLY_STATUS_UNAVAILABLE and exits nonzero. Customer, URL, contract and file fields are not projected.

## Verified scope

- 24-Nov synthetic regressions: 16 PASS, including SQL transaction order, parameter binding, empty history, unrecognised statuses, invalid counts, wrong database/user and secret-safe failure handling.
- Affected DTR suite: 51 PASS (including new 16), Ruff/compile PASS, pinned Spec Kit structural check PASS.
- Real production read-only smoke 24-Nov approximately 09:08 MSK: DTR-20261124T050008Z-87f721ac in RUNNING/ANALYZE; aggregate 33 items: 3 MANAGER_READY, 1 PROCESSING, 4 SHORTLISTED, 21 SCREENED_OUT, 4 DUPLICATE; no run summary error at snapshot time. This is not a final/HEALTHY verdict.
- No service, schedule, production schema, original EIS, billing, model, ETP or database rows changed.

## Remaining gates

Protected PR exact-head CI/merge are required for code completion. Deployment of a different runtime or tool installation is separately approved. #679, #686 (source originals), #685 (seven-day PITR), Data Platform issue #133 (ingest SLO RED), pilot legal acceptance and physical iPhone remain independent gates.
