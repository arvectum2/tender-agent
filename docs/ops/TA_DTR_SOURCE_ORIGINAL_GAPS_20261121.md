# DTR source originals missing — bounded diagnostic, 21 November 2026

Status: isolated fail-closed development candidate, not installed, no source retry and no production mutation.

## Verified failure evidence
The 20 November Daily Tender Run `DTR-20261120T050008Z-cbdb36af` ended `WAITING_HUMAN`, with 62 discovered items: 17 `MANAGER_READY`, 22 duplicates, 20 screened out, and 3 `FAILED`. Exit 20 means non-empty `error_summary`, not a total discovery outage.

A production PostgreSQL REPEATABLE READ / READ ONLY inspection at schema `122_company_cost_norms` found:
- `0173100007526000046`: 0 registered documents, 0 chunks;
- `0128200000126007559`: 0 registered documents, 0 chunks;
- `0128200000126007558`: 4 registered URL records, 0 downloaded originals, 0 chunks.

The primary pipeline tries original public EIS card/detail/revision parsing and optional SOAP metadata before the document store and DP projection. Current unauthenticated read attempts to EIS common-info and documents tabs returned HTTP 404 for the tested paths. That is a network observation, **not** proof documents do not exist; independent commercial catalogs show documents for the first notice, but cannot replace verified original bytes or revision provenance. No third-party copies are ingested or treated as official.

## Bounded code change
- Classify `final_chunks == 0` into missing metadata, no downloaded original, missing extracted text, and missing DP projection **without changing readiness status or analysis gates**.
- Regression-test the four reasons; leave existing source/embeddings/citations/decision policy unchanged.
- Do not automatically retry the three failed deals, fabricate citations, infer the current revision, or mark them ready.
- Before a targeted original recovery, verify exact notice revision/attachment URLs from the primary source, source authorization, public fetch status, previous private receipts, and the required dual PITR prewrite. Retry only under the existing source-scoped execution/lock guard.
- Distinguish the separate 19 November 8 failures (incomplete DP indexing) from the 20 November 3 missing-original cases; do not collapse both into one root cause.

Remaining: exact branch CI, independent source-specific fixture replay, runtime admission and named owner/production review. No procurement or commercial acceptance.
