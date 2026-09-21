# ARV-015 revalidation — 2026-09-21

Task: `ARV-015-REVALIDATION-001`

## Canonical scope

The immutable ARV-015 snapshot requires a reusable supplier/business profile for personalized procurement analysis. Its stated next result covers categories, brands, regions, certificates, experience, economics, 1C nomenclature, corporate documents, stop factors and a reusable business profile.

This revalidation does not rewrite that historical scope and does not invent a replacement profile architecture.

## Current reusable supplier registry

The persisted M-006 supplier registry already provides reusable counterparty identity and basic operating metadata:

- `supplier_id`, legal/display name, INN, country, status and notes;
- external references;
- contacts;
- tags;
- event trace on profile create/update.

This is a real reusable supplier registry, but its current schema does not directly model the ARV-015 participant/business constraints such as working/excluded categories, regions, NMCK limits, VAT mode, financial constraints, licenses/SRO, experience, corporate documents, 1C nomenclature or explicit stop factors.

## Existing tender-operator profile contract

`docs/product/templates/Tender_Operator_Profile_Template.md` already defines a profile contract aligned with the RFQ-first business model:

- company/operator type and sectors;
- tender regions;
- working and excluded categories;
- NMCK min/max;
- VAT mode;
- target margin, payment delay, contract security and cash-gap constraints;
- risky/forbidden categories;
- delivery/installation preferences;
- licenses, SRO and experience;
- supplier-search preferences.

The synthetic PP1R fixture and tests protect the no-fixed-catalog assumption and verify that margin, categories, VAT, regions and SRO information are present.

## Proven runtime gap

The current `scripts/run_tender_operator_pilot.py::_read_operator_profile` does not parse that contract into reusable structured values. It only returns:

- `found`;
- line count;
- booleans saying whether VAT/margin/categories text is present;
- a short preview.

Therefore the current operator profile is documentary input, not a structured reusable business-profile object.

The existing Decision Core already accepts a structured `supplier_profile` and consumes `criteria.price_min` / `criteria.price_max` when they are supplied. The missing link is not a new decision engine; it is structured ingestion of the already-defined operator profile into the existing analysis context.

## Residual versus the historical next result

Evidence-backed current state:

- reusable supplier/counterparty identity: implemented;
- working/excluded categories, regions, NMCK/VAT/financial/risk/license/SRO fields: defined in the existing operator-profile template, but not structurally parsed/persisted;
- Decision Core supplier-profile binding: implemented, currently narrow;
- brands: not established as a first-class ARV-015 business-profile field by the inspected current contract;
- certificates/experience: partially represented by template/license/SRO/experience text, not structured reusable data;
- economics: target margin and financial constraints are defined in the template, but not parsed into the reusable Decision Core profile;
- 1C nomenclature and corporate documents: not implemented by the inspected ARV-015 profile path;
- stop factors: conceptually represented by excluded/forbidden categories and risk constraints, but not normalized as reusable structured blockers.

ARV-015 is therefore not `confirmed_done`.

## Bounded successor candidate

Candidate only; **not admitted for implementation by this revalidation**:

`ARV-015-OPERATOR-PROFILE-PARSER-001 — Structured RFQ-first operator profile ingestion`

Bounded scope:

1. parse the existing `Tender_Operator_Profile_Template.md` contract deterministically into a typed/validated `analysis_context.supplier_profile`;
2. include working/excluded categories, regions, NMCK min/max, VAT, margin/payment/security/cash constraints, licenses/SRO/experience and risk preferences already defined by the template;
3. feed the existing Decision Core price-range/profile binding without creating a second decision engine or parallel supplier registry;
4. fail closed on missing or malformed values instead of inferring business facts;
5. preserve RFQ-first semantics: no fixed SKU/catalog or known-price assumption;
6. cover the synthetic PP1R fixture with deterministic tests;
7. no external supplier communication, production mutation, procurement submission, commercial commitment or authority change.

Persistence expansion, brands, 1C nomenclature and corporate-document storage are deliberately outside this first bounded parser slice and require their own traceable admission.
