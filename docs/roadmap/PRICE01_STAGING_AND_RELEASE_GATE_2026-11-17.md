# PRICE-01 — staging acceptance and release gate

## Reproducible isolated staging

Run from the reviewed repository with Python environment containing the application dependencies, a local Node Playwright distribution, local Chromium executable and Xcode.
Set PRICE01_NODE, PRICE01_PLAYWRIGHT_MODULE, PRICE01_CHROME; execute
python -m scripts.acceptance.run_price01_staging.

The runner creates a private temporary directory, fresh SQLite ORM schema, separate random operator credential, temporary root CA and server certificate, and loopback-only HTTPS FastAPI on an ephemeral port. It constructs an allowlisted environment instead of inheriting application secrets or repository .env. No live EIS/B2B requests, no configuration of production services. Browser intercepts and aborts non-local page requests; it allows only the ephemeral certificate's SPKI for the dedicated local profile. Native test-only URLSession uses the ephemeral CA as its only trust anchor and refuses redirects. Normal native origin and TLS policies are unchanged. Temporary artifacts, server and synthetic database are torn down. The PostgreSQL migration and concurrency test is separately covered by run_price01_postgres_tests.

Two synthetic tenants are created via real API; legal acceptance, itemized plan v1, reported actual, and manager approval seed via the actual backend. Real browser token sign-in and card selection exercise archived EIS data and empty reviewed registry, apply the approved norm, explicitly preview and save v2, then switch tenant and verify cleared data. Real native CompanyAPIClient reads v2 and original v1, actual history, row evidence binding and explicit sample preview, norm catalog, historical pairwise comparison and registry; attempts for the foreign tenant return 404. No API response substitution. The Swift command-line harness runs on macOS; optional simulator XCTest uses the same test code compiled into the test target only.

For optional iOS runtime acceptance, prebuild the test target with Xcode build-for-testing and set PRICE01_XCTESTRUN to its xctestrun and PRICE01_SIMULATOR_ID to a dedicated shut-down simulator with name prefixed TA-PRICE01-Acceptance-. The runner passes ephemeral synthetic configuration via a private temporary xctestrun, removes it and shuts down the simulator. Without that configuration the new XCTest skips, not a false pass. This is running native client code on iOS, not manual or XCUITest interaction with every SwiftUI screen.

## Deployment boundaries / GO criteria

- Preserve all default-off feature flags and the tenant/operator authentication boundary. Real source acquisition remains separate. No real reviewed signed-contract group has been published in revision 0.
- Review all stacked PRs and their CI; reconcile against the maintained deployment base before deployment. Draft PR publication does not merge or release the code.
- Verify backups, tested rollback and migration 122 on the actual approved staging deployment before production. Do not drop populated immutable histories during rollback; turn feature gates off instead.
- Verify deployment packages contain the reviewed release JSON and exact pinned old archive sources. Server and both clients must agree with release and public projection pins; the new automated consistency test checks these in the repository.
- Require a separate approved release decision and deployment authorization. Test with safe synthetic tenants on the chosen staging environment, including normal certificate trust, physical device/SwiftUI interaction, and user-role boundaries. Rehearse flag disable and rollback, check storage and monitoring. Do not advertise live contract-price recommendations without approved genuine source evidence.
- Actual contract publication: retain original signed-contract evidence, verify scope, unit, quantities, price and tax terms and source authenticity with a reviewer, pin manifest and release; update both clients atomically, then rerun acceptance. Do not infer signed prices from winning offers or contracted quantities from deadlines. Registry groups stay non-recommendations; empty state is valid.
- B2B authorization/legacy acquisition is a separate blocker; do not retry a live pilot as part of PRICE-01 staging.
