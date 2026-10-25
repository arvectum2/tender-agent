# MI-004 — Project lifecycle finance / sourced account exports

Scope: deterministic, read-only pilot for Arvectum Market Intelligence, 2026-10-24. **Not live national market sizing, not deployed to customers.**

## Why equipment turnover is not EPC turnover

Each procurement observation is scoped by `project_id + notice_id + lot_id + contract_id + tier + scope + price_type + line_id`. Mirrors and earlier revisions of the **same fact** collapse to its latest sourced revision. Same-date conflicts in price/status/family are quarantined instead of silently resolved. Source proof must be a reviewed signed contract or official contract registry record with URL, reviewer, excerpt, locator and SHA-256; protocol-only price is NOT treated as a signed contract.

A full EPC contract price (engineering/civil works/equipment) is an **envelope**. Only explicitly priced compensator/filter lines within that end-buyer contract can count as equipment value. A dedicated single-product supplier contract can count entirely if its equipment category and dedicated-lot status are independently reviewed. Main buyer contract, downstream EPC subcontract and equipment resupply must not be summed across the supply chain. Separate PИР/design, maintenance and the published НМЦК remain non-hardware or non-awarded categories.

When multiple end-buyer contracts in one project name the same equipment family and there is no reviewed asset/BoM-level separation, the current conservative bound keeps the **maximum observed contract equipment amount** for that family and raises a lifecycle-review flag rather than summing overlapping equipment. This may understate legitimate separate units; it is a cautionary lower measure, not an exact market valuation. Explicit invoice/payment evidence is not present, thus monetary language is **contracted**, not delivered or paid.

Money validation is RUB decimal and bounded to under 10 quadrillion RUB per fact; conflict/invalid identity/excess line values fail closed. Distinct legal contracts do not silently merge just because they have identical titles.

## Output fields

`audit_project_finance(...)` produces:

- `project_finance[].contracted_equipment_rub`: separately verified contractual value of equipment within available projects, or null.
- `project_finance[].full_epc_contract_envelope_rub`: full EPC totals **not additive** with equipment.
- `project_finance[].subcontract_chain_value_rub_not_additive`: secondary supply-chain flows **not additive** with end-buyer.
- `project_finance[].design_contract_rub` / `service_contract_rub` / `published_ceiling_rub_not_awarded`.
- `cross_contract_lifecycle_review` and `quarantined_price_facts`: unresolved conflict warnings.
- `observed_confirmed_contracted_equipment_rub`: observed proof-bounded contractual equipment amount; null if no qualifying award proofs. National `TAM/SAM/SOM` ALWAYS null until a separately audited source-complete estimation framework is developed.

These figures are not industrial market revenue or equipment consumption forecasts.

## Test economics — SYNTHETIC ONLY

Example assertions validate: 300,000,000 RUB total EPC award with 25,000,000 RUB explicit STATCOM line, separately 18,000,000 RUB EPC subcontract, 2,000,000 RUB design contract, 500,000 RUB maintenance and 350,000,000 RUB НМЦК. Expected equipment contracting amount = **25,000,000 RUB**, not the sum of these categories. These numbers are **made-up test values**, never market evidence.

Tests also cover same contract mirror, latest revision, contradictory same-revision values, excess equipment line, same project-family multiple end-buyer contracts, and independent different equipment families. No real Power Quality award money is in the October 24 12-lead research seed, so the actual pilot retains `market_size_rub=null`.

## Preview outputs

From trusted research-run evaluation JSON (see MI-003):

```bash
python -m src.modules.market_intelligence.finance_and_export \
  --evaluation data/market_intelligence/power_quality/mi003_evaluation.v1.json \
  --html-out docs/market_intelligence/POWER_QUALITY_CLIENT_PREVIEW_20261024.html \
  --csv-out data/market_intelligence/power_quality/account_leads.v1.csv
```

- `POWER_QUALITY_CLIENT_PREVIEW_20261024.html`: standalone static internal report, no JS, sanitized HTML text, outbound URLs must use HTTPS and open with noreferrer/noopener, restrictive content security policy. Reports observed buyers, relevant equipment categories, indicative qualification next steps and source links. No contact data, no live CRM dispatch or chatbot permissions.
- `account_leads.v1.csv`: UTF-8 BOM, marketing/CRM-friendly rows and spreadsheet formula-injection guard; **not** a production sales pipeline. `priority_hypothesis` is *unreviewed* and `qualification_needed_not_outreach` is explicit. Source URLs come from previously discovered public cards.

**Do not treat this static HTML file as an authenticated customer portal.** It is not tenant-isolated at HTTP/server authorization level. Before offering a customer self-service report, require tenant access-control acceptance, isolation testing, source licenses, export/download security, accessibility, effective branding through official Arvectum source assets, and human review.

## Relationship to upstream SOAP and MI005

EIS SOAP API is temporarily blocked during official Oct 24/25 maintenance. This MI-004 code contains no SOAP network dependency. Once original award protocols/contract registries and EPC attachments can be ingested, a reviewer can promote appropriately checked monetary facts into this ledger. The 12 public secondary Power Quality cards have **0 independently verified award contract amounts**, so no national size estimate, winners or current tenders may be asserted. MI005 portal/tenant live workflows require separate production-ready authorization, consent and real document quality gates.

## Acceptance tests

`pytest -q tests/test_mi004_finance_and_export.py` — 20 focused tests. Full integrated suite includes MI-001/002/003, SOAP, and source graph/ontology; test count recorded in task checkpoint.
