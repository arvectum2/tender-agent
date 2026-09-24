# ARV-015 structured operator-profile ingestion

The existing RFQ-first markdown profile is now parsed into `analysis_context.supplier_profile` without creating a parallel supplier registry or decision engine. The parser preserves unknown/malformed values as `None`, maps working categories/regions and NMCK bounds into existing Decision Core criteria, and records VAT/financial/qualification values for downstream use.

The pilot runner injects the structured profile before analysis and re-binds it after controlled-LLM requirement updates, so the existing report-model Decision Core receives the same source profile. No external communication, procurement action, production mutation, commercial commitment, or fixed-catalog assumption is introduced.

Focused deterministic validation on the implementation branch: `41 passed` across the new ingestion tests, Decision Core v1 tests, and existing supplier-profile tests. Exact-head CI remains required.
