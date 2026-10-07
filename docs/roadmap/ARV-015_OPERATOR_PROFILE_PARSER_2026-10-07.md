# ARV-015 structured operator-profile ingestion — 2026-10-07

Task: `ARV-015-OPERATOR-PROFILE-PARSER-001`

## Scope

This bounded slice reuses the existing RFQ-first `operator_profile.md` contract and the existing Decision Core `supplier_profile` boundary. It does not create a second supplier registry, decision engine, product catalog or external-action path.

## Implemented

The parser validates the markdown into the existing `SupplierProfile` family and carries only explicit profile facts:

- working and excluded categories;
- tender regions;
- NMCK minimum/maximum;
- VAT mode;
- target margin;
- acceptable payment delay;
- acceptable contract security;
- prepayment and cash-gap limits;
- licenses;
- SRO approvals;
- required experience;
- risky and forbidden categories.

Missing, malformed, contradictory and ambiguous values remain empty/`None`. The parser does not infer product SKUs, fixed catalogs, known supplier prices, legal qualification or commercial facts that are not explicitly present.

The pilot runner injects the structured object into `requirements.analysis_context.supplier_profile` before analysis and re-binds the same profile after controlled-LLM requirement updates. Existing Decision Core price-range/profile behavior is reused unchanged. Stub economics now consumes the parsed target margin instead of emitting the historical `needs_extraction` placeholder.

## Safety and product boundaries

Decision Core external-action safety remains unchanged: no bid submission, RFQ/invitation, winner selection, signing or external commercial effect is enabled.

The existing PP1R fixture remains RFQ-first and no-fixed-catalog. Broader historical ARV-015 residuals such as brands, 1C nomenclature and reusable corporate-document persistence remain outside this bounded parser slice.

## Verification plan

Deterministic regression coverage includes:

- the existing PP1R synthetic `operator_profile.md` fixture;
- the full canonical template contract;
- malformed/contradictory numeric and VAT values;
- analysis-context preservation and Decision Core price-range consumption;
- unchanged external-action safety;
- structured target-margin reuse in economics.

Exact-head CI is the merge authority for the recovery PR.

## First exact-head CI diagnostic

CI run `37653121154` on head `7bd071b145efc382a84e8b6513797605ab0550f8` completed with eight jobs green. The quality job executed the full suite: `3103 passed, 236 skipped`; its sole failure was the Commercial Workflow admission test asserting that every admitted queue item must remain `ready`. That assertion conflicts with the executor policy's legitimate lifecycle transitions once ARV-015 is claimed. The test was narrowed to admission invariants while allowing the defined runtime states `ready | in_progress | blocked | done`. No product-code failure was observed in that run.


## Exact-head closure gate

The corrected implementation head `6b0f29ce9d662f7a11bc2cfee0b8c13dc83afc95` passed CI run `37654505822`: all 9 jobs succeeded. The quality job passed `make check`, then completed the full suite with `3104 passed, 236 skipped, 246 warnings`; the procurement-domain regression steps also passed. No product-code failure or external-effect widening remains.

Final queue/checkpoint bookkeeping is committed after this implementation proof. The resulting bookkeeping head must re-earn exact-head CI before PR #199 may merge under renewed AM-4.
