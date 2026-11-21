# APR-04 — ООО «Арвектум»: isolated owner-identity onboarding E2E

**Technical DEVELOPMENT acceptance: PASS, 15 October 2026.** This is not owner commercial/legal signoff, licensing proof, a current official notice, multi-tenant production approval or permission to bid. The live customer registry and production data were never touched.

## Actual inputs and source boundary

- Actual legal identity (corporate legal name, INN and KPP) was manually verified from two owner-provided registration PDFs (tax-registration extract and EGRUL creation record). **Only corporate identity fields** were placed in the Mac mini private test fixture. Bank details, individual founder identifiers, residential address and other unnecessary data were not imported.
- Hashes identifying the two original owner-provided PDFs are kept **off GitHub** in the private runtime; **the original official PDFs were not transferred or uploaded to the Mac mini**. Consequently the platform marks original registration documentary verification as pending.
- The previously accepted preserved original EIS 44-FZ museum-website procurement `0372200172326000015` was copied read-only into an isolated run directory. Its saved, actual LLM Decision Core supplies a **source-cited 1,000,000 RUB NMCK**. This is an **archival** EIS edition, not an assertion about a currently open auction.
- The initial owner/company commercial configuration sets category/keyword as a **development-only draft** and deliberately leaves NMCK limits, margin, VAT, qualification, experience and risk preference unset/unknown. No unapproved business preference was inferred from registration documents.

## Measured HTTP and persistence assertions

All HTTP calls run inside an isolated FastAPI operator application using the same product onboarding router, Basic Auth middleware and global AppError handler as the product. Database: isolated Mac mini SQLite file; copied EIS originals: read-only. No external-facing service, signatures, supplier contact, production database writes or funds.

| Check | Observed |
|---|---|
| UI authenticated and anonymous | HTTP 200 / HTTP 401 |
| Company creation, duplicate guard, saved profile readback | HTTP 201 / 409 / 200 |
| EIS saved model result personalized to actual legal identity | HTTP 200; source-cited NMCK |
| **No owner-supplied NMCK bounds** | **UNKNOWN** (bug fixed; previously mislabeled WITHIN_BOUNDS) |
| License/SRO and profitability | UNKNOWN / UNKNOWN, no bid authority |
| Versioning of temporary synthetic bounds + restoration | Three versions, final profile has no price bounds |
| Document upload and readback | Synthetic PDF bytes only, SHA round-trip; UPLOADED_UNVERIFIED |
| Cross-customer isolation | HTTP 404 for document key belonging to other customer |
| Session reopen | Persisted profile version 3, original UNKNOWN limits preserved |
| EIS source integrity | Copied saved report SHA-256 unchanged |

**Warning:** the synthetic PDF is intentionally labeled as a storage test, **not** as the owner registration certificate. It demonstrates the API/file-system pipeline and isolation, not documentary compliance.

## Reproducibility and ownership of evidence

- Source: `scripts/acceptance/apr04_owner_company_isolated_e2e.py`. Requires a private Mac mini fixture outside the repo: `/Volumes/ArvectumSSD/Arvectum/runtime/ta-apr04-owner-onboarding-20261015/company-identity-private.json`, copied already-verified saved run and isolated data directory.
- Receipt (private, not committed): `/Volumes/ArvectumSSD/Arvectum/runtime/ta-apr04-owner-onboarding-20261015/output/apr04_owner_onboarding_e2e_receipt.json`.
- Test suite: APR04 onboarding, company-profile store and APR05 SaaS-foundation checks — **34 passed**, one preexisting Starlette deprecation and existing SQLAlchemy SQLite foreign-key test warnings. Targeted Ruff PASS.
- Product fix: `compare_profile_price` returns UNKNOWN when neither owner-selected minimum nor maximum NMCK exists, even if the procurement's NMCK is source-cited. A source citation proves a procurement price, *not* that the customer authorized any threshold.

## Remaining gates

**APR-04 bounded development E2E can proceed to APR-05 staging.** Full owner business acceptance remains open for transferring and verifying actual registration PDFs in the intended secured operator workspace, selecting real categories/regions/NMCK/margin/risk tolerances, reviewing actual license/SRO status and active notice editions. Do not treat the registration record as a license, supplier qualification or procurement GO.

APR-05 must independently measure role and tenant isolation in staging; paid pilot, VPS, invoicing and production remain separately authorized.

## 17 November 2026 — repeatable private replay on current code

`python -m scripts.acceptance.apr04_owner_company_isolated_e2e` now validates the historical private receipt against the saved report and recorded document hashes, inventories the bounded original run tree, and copies only the required inputs into a new private temporary directory. The old SQLite database and document store are never copied or used. The child process runs the existing authenticated HTTP workflow against a fresh SQLite database; output is sanitized and the temporary directory removed. Original and copied evidence hashes are checked again. Both independent executions passed with identical sanitized results. No actual registration PDFs were transferred or reverified; synthetic upload remains unverified; the operator's qualification and limits remain UNKNOWN; no GO. 72 targeted tests passed, 2 skipped; Ruff and diff check passed. Final exact CI is independently pending.
