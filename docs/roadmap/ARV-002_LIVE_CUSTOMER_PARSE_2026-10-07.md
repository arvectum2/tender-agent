# ARV-002 live customer parsing residual closure — 2026-10-07

Task: ARV-002-LIVE-CUSTOMER-PARSE-001

Authority: explicit Owner directive on 2026-10-07.

## Scope

Close the single concrete residual proven by ARV-002-REVALIDATION-001: the 44-FZ public EIS search-card parser could scan raw card HTML for Заказчик and cross into embedded JavaScript, producing script text as customer_name.

The bounded change does not alter procurement participation, production deployment, benchmark truth, source priority, or any consequential external action.

## Implementation

- Removed the raw-HTML regex fallback for search-card customer_name.
- Search cards now project customer_name only from explicit customer-scoped label/value pairs already parsed from visible card fields.
- When explicit customer evidence is absent, the search card fails closed to null.
- Placement/general organization fields are not promoted to customer identity.
- The stricter common-info/detail extractor remains authoritative downstream.
- Added tests/fixtures/public_44fz/search_card_customer_js_pollution.html, a deterministic fixture reproducing the historical JavaScript-contamination failure mode.
- Added positive coverage proving an explicit visible Заказчик pair still parses normally.

## Deterministic verification

Focused ARV-002 gate plus parser/precedence regressions: 87 passed.

Persistence/recovery companion gate: 32 passed, 12 skipped.

The skips are the same environment/profile-gated cases used by the historical ARV-002 revalidation; no failure was observed.

Repository check: make check — PASS.

After rebasing onto current main b4723cc9 (Commercial Workflow admission + fresh AM-4 reset), the combined focused/parser/source-graph/no-fallback/watchdog-policy set passed 90 tests; the new queue/admission state is preserved.

A full local suite also reached 3097 passed and 236 skipped, with one R9 backup/restore failure at pg_restore. The same isolated test failed identically on a clean origin/main 05a939eb worktree, so it is a pre-existing/environmental failure unrelated to the ARV-002 parser change.

## Read-only live EIS verification

The historical exact-number case 0888500000226000399 was read through the current public EIS path without authentication or external side effects.

Search result after the fix:
- status=parsed
- outcome=success_with_results
- returned_count=1
- parser_status=parsed
- eis_pages_fetched=1
- customer_name=null

This is the intended fail-closed search-card result because the card does not expose trustworthy explicit customer-role evidence.

The public common-info detail page for the same registry number returned:
- network_status=success
- customer_name=ДЕПАРТАМЕНТ ЗДРАВООХРАНЕНИЯ ЧУКОТСКОГО АВТОНОМНОГО ОКРУГА
- document_links=5
- error=null

Thus detail-page precedence remains intact while the unsafe search-card fallback is gone.

## Result

The concrete ARV-002 residual identified on 2026-09-19 is closed. ARV-002 can move from revalidated_residual_gap to confirmed_done after exact-head CI and merge of this task.
