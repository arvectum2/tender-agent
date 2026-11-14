# TA / DP reuse-first baseline — 2026-11-14

Scope: bounded repository and runtime inventory, not production acceptance. TA main e92c948ce7d7e7c325e374bee6964651abde25b4; DP main d341731664bdc4bc6bb5e8fdeef3df00706c72bd. Preserve existing APR and PQ checkpoints and the ownership contract in docs/00_architecture/TDP_Cross_Repo_Ownership_Audit_2026-10-11.md.

| Reuse area | Verified observation | Next gate |
|---|---|---|
| Existing TA private runtime | API health HTTP 200; running image 89d4bb433e285af165f58596a89dfe0cdcb8d01a; database and Redis containers healthy | Reconcile running image with main, then authenticated read-only workflow and source freshness; no live upgrade yet |
| DP | Main updated through terminology search/PPTX extraction; checkout is an independent Gemma branch | Identify active DP runtime and authenticated SDK/API parity before changing versions |
| Source adapters | EAT and Moscow parsers exist; combined parser and watchdog focused suite 45 passed | Authorized live read-only collection, pagination, stable identity and history coverage; parser presence is not a live connector |
| Industrial procurement | Existing market_intelligence, procurement_source_graph and PQ evidence machinery | Reuse generic source receipts, deduplication, project attribution; inventory SAP SRM, B2B-Center, GPB, TEK-Torg separately |
| Supplier and economics | supplier_search, quote_repository, historical_prices, cost_model, cash_gap, goods economics present | Replay verified product offers/prices and full costs, explicit unknowns, exact SKU and delivery constraints |
| Paper trading | Dedicated simulation module not found | New isolated simulated portfolio and outcome reconciliation; no real bids, payments, orders or supplier contact |

CI repair: Both quality jobs for PR 522 at 5faaa134 failed only R9 backup/restore (5376 passed, 287 skipped, 1 failed in PR quality). Disposable PG16 reproduction: client 16 succeeds; 17 and 18 fail on unsupported SET transaction_timeout. Pin PG16 client in CI with version assertions, preserving restore safety. Mac mini isolated full recovery/security tests: 10 passed.

Mirror: GitVerse HTTP 502 twice, third attempt of run 43621472378 succeeded. Independent public git ls-remote confirmed main and PR refs match GitHub at the pre-fix head. No mirror credentials or workflow changes needed for this transient outage. Recheck after this commit.

Next: exact-head CI and mirror confirmation; then existing governance review, runtime parity and source inventory. AM-4 review deadline in policy was 2026-11-08; no newer decision found in company decision list. No automatic merge without valid authority.

## Follow-up verification

- GitVerse independently matched GitHub main and PR head acdb5deba9587cc86b4929fc975648c5c60de525.
- CI runner logs confirm ubuntu-latest switched to Ubuntu 26.04 (resolute); its apt repository has no postgresql-client-16. Pin only the quality job to ubuntu-24.04; retain PG16 major assertions.
- Active TA authenticated read-only requests to DP 0.6.0 returned HTTP 200 on collections and connectors; anonymous requests returned 401. The running TA uses SDK 0.3.0, while main pins 0.4.0. This is a genuine runtime/source parity gap, not an API outage.
- Next: isolated SDK 0.4.0 contract replay with existing runtime, candidate image build and read-only validation; no runtime replacement or DB mutation before safety gates.
