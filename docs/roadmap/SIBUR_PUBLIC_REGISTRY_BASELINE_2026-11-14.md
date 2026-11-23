# SIBUR public registry discovery baseline — 2026-11-14

Bounded first-party read-only discovery, not a production connector acceptance. Source https://www.sibur.ru/ru/procurement/buy/. The public site JS exposes a GET with X-Requested-With: XMLHttpRequest, PAGEN_1, count, catMTR and catNMK. Verified real AJAX responses for pages 1–27 (JSON content and pagination delivered as text/html). No login or private SAP SRM access; no source-side mutations.

## Evidence from a bounded public sweep

| Metric | Observed |
|---|---:|
| Advertised / validated pages | 27/27 |
| Raw rows | 314 |
| Unique exact procedure IDs (including suffix) | 313 |
| Repeated ID | 1 |
| Unique allowlisted document URLs | 516 |
| Unverified document link observations | 27 |
| First-observation status accepting proposals | 311 |
| First-observation status cancelled | 2 |
| Observed publication-date range | 2024-11-06 to 2026-11-14 |

Page count was stable; no acquisition/parse errors in completed sweep. One ID occurs twice with differing document labels, so preserve both observations with SHA, source page and row. Do not silently overwrite them. Contact columns are excluded from normalization, raw pages stored only in private local evidence. The date range is **not** proof of complete historical coverage, and acceptance snapshot does not prove present legal eligibility or award outcome.

Two source documents selected by deterministic extension and URL order were downloaded directly without redirects, byte-hashed and checked for OOXML container structure: DOCX 13,422 bytes; XLSX 20,163 bytes. Not yet a semantic document review. 516 URLs are discovered references, not 516 verified or downloaded documents.

Parser rejects malformed source shape, wrong page, oversized responses and invalid IDs. Public probe uses fixed origin, direct verified TLS, no redirects, bounded 40-page max, retry only on transient failures, pacing, partial failure receipts and separate observations for duplicate IDs. Attachment extraction allows only observed same-origin public upload path without query/fragment; other links remain unverified. Production integration must reuse Data Platform transport and canonical persistence, not this standalone probe.

Private evidence: source receipts, all 27 raw AJAX pages, normalized grouped observations with document links and sample document receipts retained outside repository. Only sanitized metrics and synthetic regression tests are committed.

## Next steps

1. Acquire and verify the referenced documents with source-bound receipts and bounded safe ingestion through Data Platform, distinguishing generic forms from procurement-specific specifications.
2. Reconcile pagination/date filters and archived/completed procedures to measure actual historical coverage; obtain authorized SAP SRM read-only access where required.
3. Reuse canonical procurement identity/monitoring and source graph, validate idempotent update with offline snapshots; preserve tenant isolation.
4. Parallel discovery of ETP GPB/TEK-Torg and EAT/Moscow list APIs remains open.
