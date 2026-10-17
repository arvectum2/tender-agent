# APR-06/07 — quality of historical 20-case DEVELOPMENT source cohort (15 Oct 2026)

**Status: source-technical observation passed, with two unsupported literal citations detected.** NOT a 20-case completed operator E2E, not commercial APR-06 accepted, not an independent legal expert/qualified-human decision, and not a live-production SLO.

## Reproduced primary evidence

Read-only re-run of the existing historical R4 original-source verifier against the existing saved **development** data (not independent blind test data). The full 20-case first-party review is reproduced **byte-for-byte** from an earlier versioned R4 audit, SHA-256 `707e5bbb3ab5c18c8b42…`. Raw documents, credentials and unpublished blind labels remain entirely in the private SSD source repository and are not copied into GitHub.

A new fail-closed APR-06/07 adapter separately reopens the actual preserved EIS ZIP for each of the 20 pinned, historical competitive 44-FZ cases; verifies the ZIP SHA and finds exactly one archived notice XML with the expected exact original SHA; checks that the *full 19-digit* registry number matches the original XML and the attachment count in that selected notice is the declared one. 20/20 source ZIP hashes and 20/20 XML hashes match the pinned public development manifest. Only the original selected historical edition is verified — no claims about current notice updates or participation eligibility.

The existing R4 source audit was also re-executed on private first-party bytes, and its output SHA matches the tracked result; it checks the 96 archived attachment files against original source receipts and returns 96/96 source digest attestations plus 96/96 *nonempty recorded text* flags. Nonempty text is not proof of every table cell, accurate OCR or legal interpretation. The new adapter does not independently redownload or reextract these 96 source documents; it binds those figures to the reproduced SHA-pinned original R4 audit, without relabeling them as 20 completed fresh E2E runs.

## Three deliberately different denominators

| What was checked | Observed | Meaning |
|---|---:|---|
| Competitive original EIS notice ZIPs / selected matching XMLs | **20/20 ZIP; 20/20 XML** | Historical source integrity, 44-FZ only |
| Source attachment references and archived binary attestation | **96/96** | R4 original-source audit rerun and matched; **not new ingestion E2E** |
| Saved model citation snippets checked against source-bound text | **47** | 26 in historical ten-run subset plus 21 in four other case source reviews; not every model claim |
| Exact original literal citations | **42/47 = 89.36%** | Exact snippets, not legal relevance |
| Source-evidenced whitespace/layout variant snippets | **3/47 = 6.38%** | Layout normalization needed; not literal-exact |
| Unsubstantiated or incorrect literal snippets | **2/47 = 4.26%** | **Actionable defects** requiring correction/abstention |
| Exact or layout-normalized source-backed snippets | **45/47 = 95.74%** | Selected saved excerpts only; full narrative accuracy unknown |
| Archived previously saved report deadline mismatches | **2/10** | Date/edition reconciliation backlog, not all 20 current cases |
| Older saved reports with unattested strong blocker decisions | **8/10** | **Needs expert calibration**, not necessarily proven legally false |
| Additional detected quote-length / batch-cap violations | **3 / 3** | In four-case claim subset only |

The old audit labels the two unsupported snippets; the new aggregator retains them as observed errors rather than pooling them with exact citations. No unverified model claim is promoted to legal truth, no automatic bid/NO_GO and no signatures.

## Reproduce safely

Code: `scripts/quality/apr067_r4_development_cohort.py`. Pinned public **development-only** input: `docs/quality/APR067_R4_20_HISTORICAL_DEVELOPMENT_SOURCE_MANIFEST_2026-10-15.json`. The manifest contains exactly 20 official registry numbers, selected archival original ZIP/XML SHA-256s and the attachment count per selected edition; no source binary bytes.

First regenerate the exact R4 private audit by running the existing pinned first-party R4 `build_review(private_source_root)` routine read-only on the development corpus. Its JSON digest must match the pinned public source audit digest, or aggregation aborts. Then run the new adapter with three inputs: pinned tracked manifest, existing private development original root, regenerated R4 audit JSON, and a new private output path. The script will not write outside the dedicated private R4 quality staging directory and will not overwrite an existing receipt.

The verifier is strictly offline and does not call SOAP/EIS, TDP, LLMs, ETP, Gmail, billing or production. All-snapshot SHA mismatch, duplicate procurement number, suspicious ZIP/XML entry, wrong category, fake independent gold/production permission, inconsistent model quote totals or an unsupported literal falsely counted as exact **must fail**. Synthetic adversarial regression tests cover these.

## Follow-up engineering priorities

1. Prevent model excerpts with unsupported literal source evidence from being rendered as verified facts; keep them `NEEDS_REVIEW` and promote to permanent regression cases.
2. Reconcile citation normalization so whitespace variants are visibly distinguished from literal quotes.
3. Guard against stale notice dates and strong bidder-blocker claims without actor/eligibility evidence. Do not infer legal impossibility from archived source fragments.
4. Continue separate prospective/incremental E2E runs. Existing APR-03B verifies one real full LLM operator workflow; this new 20-case audit verifies **source and selected historical claims**. Use separate denominators. Independent human gold, Owner commercial acceptance and production SLO remain `NOT_MEASURED`.

This work implements the Owner's instruction to accept ChatGPT **source-grounded analysis for initial DEVELOPMENT E2E**, while keeping observed unsupported source language visible and avoiding any false statement that an external qualified-human reviewer signed 20 cases.
