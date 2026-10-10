# R5 structured unknown accounting (2026-10-10)

Read-only report evidence audit: earlier literal UNKNOWN marker checks observed
zero matches in sections[].items, while actual unknown status is stored in
decision_core.unknowns and canonical_report.procurement_passport.

Existing private operator preview:
- 29 unique EIS procurements represented by 46 stored EIS runs.
- Best selected run per registry: 11 reports, 110 sections, 362 string items.
- 16 structured decision-core unknown entries across those 11 reports.
- 7 exact unknown-valued passport fields in their canonical reports.
- Zero eis-xml: citation markers in saved report section items.
- No quality or completeness acceptance implied.

Isolated local Gemma E2E on the museum-of-bread six original files:
- 10 report sections, 54 items, 3 verified-XML marker references,
  31 explicitly unverified model suggestions.
- Five decision-core unknown entries, one exact unknown-valued passport field.
- It is correct to retain unknown status when no original source evidence exists.

These metrics exclude document text and operator/customer PII. They are structural
indicators, not false claim rates and not legal-commercial source validation.
The independent R5 quality gate requires 20+ human-reviewed procurements.
