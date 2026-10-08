# APR-05 — paid pilot / SaaS foundation on Mac mini (2026-10-09)

## Scope / gates

APR-05 is a **bounded internal operator-controlled SaaS foundation**. No
real-money charging, public offer, production payment-provider integration,
automatic bidding, electronic signing or external VPS provisioning is
authorized or claimed. APR-03 real Russian VPS remains explicitly paused
until development is complete. Operator Basic credentials must **never** be
given to a customer; customer auth is separate bearer-based API at
`/api/saas/*` with a static self-service entry at `/saas`.

The default source setting `saas_foundation_enabled=false` fails closed.
Only the Mac mini developer Compose override explicitly enables it.
Public HTTP ingress is unavailable: API binds `127.0.0.1:18082`; connect
through authorized SSH or existing private tunneling.

## Operator bootstrap

1. Operator signs into existing `/pilot/onboarding` with internal Basic Auth
   to create a customer/company profile.
2. Operator provisions `POST /api/operator/saas/tenants` with
   `{"customer_id":"CUS-...","plan_code":"pilot"}`, using the same internal
   Basic credential. Existing customers are not silently rebound to a second
   tenant.
3. One bootstrap owner invite is returned **once** in this response. Give it
   to the intended owner through an approved private channel, **never** the
   Basic password or a raw service API key.
4. Customer opens `/saas`, redeems invite and receives bearer token once.
   The browser keeps tokens **in memory only**, without localStorage/cookies
   or persistent JS SDK storage. The initial owner may invite admin/analyst/
   viewer within seat entitlement. All access tokens are SHA256 digests
   in the database; expiry, rotation, logout and revocation are enforced.
5. Each member must acknowledge the exact current draft terms/privacy
   versions. This is a logged acknowledgement, not a qualified digital
   signature, public offer or replacement for legal/personal-data compliance.
6. Owner/admin edits durable versioned company profile; owner/admin/analyst
   uploads PDF evidence, screens exact 44-FZ notices and creates tender runs
   by local documents or read-only getDocsIP. Viewer may inspect own tenant
   report but cannot alter profile or run analysis. No automatic GO.

## Packages & measurement (not approved public prices)

Developer package `pilot`: 3 seats, 14-day trial, monthly 30 screens,
12 company document/upload actions, 8 new runs and 8 analyses.
Developer package `team`: 15 seats, monthly 150 screens, 60 uploads,
40 runs and 40 analyses. `price_rub` remains `null` in API responses,
`online_checkout_enabled=false`. No card processing or customer billing
is performed by these endpoints.

All usage counters and audit events are tenant-scoped in PostgreSQL;
quota reservation happens under a row lock (PostgreSQL) and failed requests
release the reservation. Repeating a terminal analysis is blocked instead of
re-consuming LLM resources. Metrics are scoped to the tenant (adopted seats,
invites redeemed, owned runs, used/remaining limits).

Manual paid state requires an explicit operator attestation with an external
reference and explanation, is idempotency-protected by reference uniqueness,
and is **not** proof of an actual payment-provider callback or funds receipt.
The financial receipt and valid contractual basis have to be checked outside
this local pilot before any real tenant is marked verified.

## Isolation / secrets

- Each tenant is bound one-to-one to canonical CustomerProfile.
- Tenant-auth endpoints derive customer ID from authenticated token membership,
  never from client JSON/path. No public path permits arbitrary customer_id.
- User-owned tender runs are explicitly bound in `saas_runs` before run
  analysis, reports, supplementary files and personalization are accessible.
- Legacy global operator routes remain protected by internal Basic auth;
  Bearer tokens must not authorize them.
- Tenant token digests are stored, plaintext returned only at issuance.
  Operator Basic and Data Platform keys stay outside Git and response logs.
- All legal/human checks are server-side. Source-grounded screen comparisons
  can still only return HUMAN_REVIEW_REQUIRED; no bid submission.
- No request can be authenticated by a client-supplied tenant_id header;
  tenant identity comes from the keyed database lookup.
- Real document extraction reuses the existing Mac mini Data Platform, not
  a second document ingestion engine.

## Validation

Evidence for tests, Alembic migration, live local HTTP smoke, real read-only
EIS SOAP, restart and CI is appended when those stages complete.
