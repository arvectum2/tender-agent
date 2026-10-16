# APR-05 — Owner company SaaS tenant: isolated legal/entitlement hold (15 October 2026)

**Bounded development acceptance: PASS. APR-05 production and commercial launch: NOT ACCEPTED.**

## Actual-continuity input and scope

This is a read-only-origin follow-up to APR-04 private actual-company identity staging (owner-supplied official registration documents). The registered corporate identity and staged company row were copied into **a new private SQLite database**. The APR-04 database's before/after SHA-256 remained identical. All HTTP requests targeted a local in-process test application with the actual SaaS router, middleware and real SQLAlchemy persistence — not a public server or a paid tenant.

The original registration PDFs are **not** present on the Mac mini. This staging exercise neither authenticates the company's signatory nor accepts terms for the real owner. It does **not** grant any bid GO, verify a license, move funds, or contact a supplier/customer.

## Measured product assertions

| Check | Observed |
|---|---|
| Packages endpoint | 200; `online_checkout_enabled=false`, payment provider disabled, offer unpublished |
| Operator bootstrap anonymous | 401 |
| First test tenant for existing corporate identity | 201; isolated simulated 14-day trial, payment_collected=false |
| Duplicate bootstrap for same customer | 409 |
| Test-only owner invitation issued/redeemed | 201; second redemption 410 |
| Bearer member session | 200 before logout |
| Protected profile read/change without explicit legal acceptance | **428 / 428** |
| Legal document preview | 200, **no `/legal/accept` invoked** |
| Test token logout and reuse | 200 then 401 |
| Persistence | Zero `SaasLegalAcceptance` for this tenant; zero `SaasPaymentEvidence`; no raw access token stored |
| Cross-tenant roles, uploads, quota, migration | 21 existing APR-05/migration regression tests PASS on current `main` (one preexisting Starlette and other existing test warnings) |

**No real owner legal agreement** was fabricated. The test invitation was consumed in process by a clearly labeled synthetic test identity and its bearer was revoked; credentials and invitations are not included in the receipt. No manual payment verification route was called. No production API, Mac mini live container, ETP, external billing or outbound mail was accessed.

## Evidence and remaining gates

- Reproducible developer test: `scripts/acceptance/apr05_owner_tenant_legal_hold_e2e.py`, requires the existing isolated APR04 private evidence and company profile. Deliberately refuses to run twice against an existing APR05 staging database without a fresh copy.
- Private receipt (outside GitHub): `/Volumes/ArvectumSSD/Arvectum/runtime/ta-apr05-staged-isolation-20261015/output/apr05_owner_tenant_gate_receipt.json`.
- Source previous accepted APR-05 actual local two-tenant infrastructure test: `docs/operations/APR05_MACMINI_SAAS_ACCEPTANCE_2026-10-09.md`; this run measures **current-main regression + real-company legal hold**, not a new full Docker deployment or independent production security audit.
- Owner must separately decide legal documents/actual terms and privacy policy, licensing, desired pricing and company onboarding preferences before any live tenant or commercial charge. Real Russian VPS/TLS, customer production isolation at deployment scale, payment-provider accounting, backup/restore and independent policy review remain deferred.

The next engineering track can continue with APR-06/07 citation and quality instrumentation using approved development expert review. Independent production/legal gold and external commercial acts remain separately gated.
