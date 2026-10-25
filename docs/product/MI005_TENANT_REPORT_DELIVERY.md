# MI-005 — authenticated Market Intelligence report delivery pilot

Date: 2026-10-24. Scope: **internal, disabled-by-default** tenant-bound read-only delivery of report bundles. NO national market census, no customer production launch, no payments or proposal submission.

## Existing foundation reused

Uses *exactly the existing SaaS Foundation* `_principal / require_tenant` in `src/modules/saas_foundation/router.py`, which checks hashed Bearer token against database, expiration, revocation, active membership and tenant lifecycle, billing entitlement/trial. Existing `legal_required` enforces accepted terms and privacy version. Existing `role_required` allows read-only owner/admin/analyst/viewer to see **only their tenant's report**.

Added a second feature toggle `Settings.market_intelligence_report_delivery_enabled=False`. The SaaS foundation itself remains `saas_foundation_enabled=False` by default; *both* must be enabled through controlled operations for this endpoint to become callable. Do not enable for public users without formal privacy/security and business acceptance.

Routes under existing FastAPI `router_registry`:

| Method | URL | Purpose |
|---|---|---|
| GET | `/api/saas/market-intelligence/reports` | List reports published under the authorized tenant |
| GET | `/api/saas/market-intelligence/reports/{report_id}/json` | Download evidence-limited machine report |
| GET | `/api/saas/market-intelligence/reports/{report_id}/html` | Download static HTML report as **attachment**, not rendered under trusted SaaS origin |
| GET | `/api/saas/market-intelligence/reports/{report_id}/csv` | Download CSV account prospects (manual qualification only) |

All routes require authenticated user and current SaaS legal acknowledgement. Returned headers: `Cache-Control: private, no-store`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`, restrictive CSP and `Content-Disposition: attachment` to prevent arbitrary HTML executing on the application origin.

## Offline operator-controlled publication

Service: `src/modules/market_intelligence/report_delivery.py`; `ReportBundleStore.publish(tenant_id, evaluation, report_id=...)` is **not an HTTP endpoint**. It may be invoked only by trusted internal operator workflow, with tenant ID from server-authenticated owner mapping — never a user-specified customer query string.

Current MI-003 bounded evaluation (schema version `mi003-power-quality-evaluation/0.1`) is the only accepted data type. It must assert:
- `verified_hardware_market_size_rub=null`
- `coverage.full_market_census=false`
- no `known_winning_epc` or `known_verified_designers` claims

The publisher generates its own sanitized HTML/CSV (using audited MI-004 serializers) and JSON, then writes a versioned tenant/report manifest with bytes, content SHA-256, source-limited state, national `market_size_rub=null`. Report IDs are random or strict-safe operator IDs, immutable once published.

Storage location: `{Settings.arvectum_data_dir}/market_intelligence_reports/{tenant_id}/{report_id}/` with private 0700 directory and 0600 file permissions. No cross-tenant symlinks, arbitrary paths, raw user files, global public links or ability to download arbitrary filesystem objects. Each downloaded file is checked against its committed size and SHA-256; a mismatch returns unavailable, never silently exposes bytes.

## Required before enabling any live service

- Review SaaS Foundation security and test live tenant identity/billing/legal gates under deployment, including logging, revocation and abuse rate limits.
- Establish real tenant-authorized Data Platform ingestion/auth, privacy policies, deletion/retention and robust web-URL/redirect/DNS-rebinding SSRF handling. The present intake adapter alone is not that acceptance.
- Validate official company visual assets in the HTML renderer, accessibility, navigation semantics and support process. Static HTML preview is a prototype; no full interactive portal/UI with customer login is offered yet.
- Review source data licensing / redistribution to paying customers and PII minimization.
- Deploy Data Platform PPTX PR #126 separately if supplier presentations should be imported.
- Complete actual EIS 44/223 plus commercial platform historical acquisition, source-month completeness and primary protocols before claiming actual national TAM, real win rates, named EPC winners, contract amounts or current live opportunity alerts.
- EIS SOAP has a separate live blocker until its Oct 24/25 maintenance. This delivery code does **not** call SOAP or retry it.

## Tests

`pytest -q tests/test_mi005_tenant_report_delivery.py` covers tenant isolation, no cookie/public URL access, existing SaaS Bearer requirement, legal 428, owner/viewer access, denied cross-tenant report even with known report ID, second feature flag off, checksum/symlink/path traversal, immutable reports and no fake TAM.

The source-limited test suite uses an in-memory/transient SQLite test client. No real report uploaded, no mail sent, no payment or tender executed.

## Operational metadata

- This is internal code on draft PR, not production installation or customer offer.
- Canonical task checkpoint: `.agent/checkpoints/MI-005-DELIVERY-20261024.yaml`.
- Owner-reviewed deployment is a separate gated task. Leave both feature toggles disabled until authorization.
