# APR-06/07 — Verified original-source quality observation, 15.10.2026

**Development quality result: PASS for a narrow, independently rechecked original-source subset.** This is neither APR-06 commercial acceptance nor APR-07 rolling production SLO.

## Exact sample and trust boundary

- **Denominator:** one completed, archived **44-FZ** read-only EIS `getDocsIP` operator case, notice **0372200172326000015**, saved run `toa-run-20261012200402-7249ed`. Not 20–30 independently reviewed procurement cases; no extrapolation to 223-FZ or currently active notices.
- Same six first-party saved original files, independently present in the preserved source copy and saved run. Freshly calculate original SHA-256 on **both byte streams** and verify against the captured run's manifest; source file identity, file IDs and run ID are unique. **6/6 observed SHA matches.** These are historical saved bytes, not proof of a fresh 2026-10-15 EIS revision or complete all-revisions legal audit.
- **6/6** original document entries have a successful extraction status / text-available flag; the tool does not measure OCR accuracy or whether every legal clause has been parsed.
- Re-reads the one archived **registry-matched XML** and checks that each of three selected fields has one unambiguous literal element with the same excerpt, file ID, document name and source reference. The HTML citation panel must visibly contain all three exact excerpts and source locators; its SHA-256 is checked again. Selected cited facts: (a) official procurement title, (b) application deadline, (c) NMCK. **3/3 checked subset integrity**, NOT 100% accuracy of the model's complete narrative.
- The saved run and model provenance show an actual local **Gemma4 12B**, four LLM calls, local endpoint, no reported fallback for the final replay, and **138.79 seconds for the analysis call**. This is neither discovery/download time nor human decision time; therefore no E2E percentile/SLO is claimed.
- Authenticated workspace/readback/history/registry 200, anonymous access 401, archival PDF/DOCX export 409 and no signature/ETP/payments are checked against the preserved isolated E2E trace. Archived edition requires current EIS verification for a potentially exportable report.

## What the measurements explicitly do not claim

The following are **NOT_MEASURED**, not zero and not a passing threshold: complete generated model statement accuracy, missing legal blockers, actual false GO/NO_GO against independent legal decisions, correction rate, current EIS revisions, all attachments/revisions' completeness, rolling p95 latency, full financial/bid suitability, or precision/recall against qualified-human gold.

Owner's 2026-10-15 decision treats source-grounded ChatGPT reviews as expert-equivalent **for development E2E approval**. The reviewer is `owner_delegated_chatgpt`, never impersonated as an independently signed human gold label. One successful saved run does not close the 20–30 case APR-06 commercial rollout criterion, approve payment/ETP/signature, or qualify any LLM for automatic promotion.

## Reproduction

Code: `scripts/quality/apr067_original_e2e_quality.py`, linked to current source-evidence parsers added by APR-03B PR #433. The evaluator is **read-only** and never contacts EIS, models or external systems. It fails closed on changed original SHA, invalid/unmatched XML, ambiguous source revision, missing rendered citations, fabricated LLM provenance, missing saved acquisition events, unauthenticated leaked access or wrongly permitted official historical export.

Run on the authorized Mac mini after APR-03B staging is available:

```sh
python -m scripts.quality.apr067_original_e2e_quality \
  --stage /Volumes/ArvectumSSD/Arvectum/runtime/ta-apr03b-e2e-20261015 \
  --output /Volumes/ArvectumSSD/Arvectum/runtime/ta-apr03b-e2e-20261015/output/<new-private-evidence-name>.json
```

Output is created exclusively in that private directory, with **exclusive create** so an existing measurement cannot be silently overwritten. Confirmed private artifact: `apr067_eis_quality_hardened_20261015.json`. Raw procurement files, corp documents, API tokens, legal data and input paths are **never committed to Git**.

Targeted source integrity/adversarial tests (including rewriting receipt and original SHA together and malicious citation outside the official panel) pass; the full regression and CI are recorded in the task checkpoint once complete.

## Next quality work

Keep APR-06/07 broader protocol and frozen evaluation corpus separate. Expand genuinely independent observed case runs with a denominator-by-denominator technical matrix, then perform owner's later legal/semantic corrections after workflow stability. Continue using the existing monitoring and Data Platform rather than building a second SLO or OCR engine.
