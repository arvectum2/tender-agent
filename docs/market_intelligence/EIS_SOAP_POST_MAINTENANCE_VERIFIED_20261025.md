# EIS getDocsIP restored — source-byte integrity acceptance

**Observation date: 25 October 2026, Moscow. Scope: bounded archive sampling, not nationwide procurement statistics.**

## Real authenticated service response

- Mac mini authenticated SOAP `getDocsByReestrNumber` for historically successful RI223 notice `32616447910`: `soap_post_status=ok`, `response_kind=completed`, exactly one official archive link. Token loaded from mode-0600 protected file, never published.
- Verified production SOAP TLS context with native OS trust, certificate verification/hostname validation required, EIS HTTP routing direct (proxy disabled). A standalone previous `ssl.create_default_context` route test had a false negative on macOS because it used different trust roots; its diagnostic now uses exactly the production trust context. DNS/TCP/TLS/XSD checks all returned `ok` on replay.
- Obtained region/day archives through real `getDocsByOrgRegion` for both 44-FZ (`PRIZ/epNotificationEF2020`) and 223-FZ (`RI223/purchaseNotice`), with no bid submission, account login, payment, or public posting.

## Source-bound sample audit

- **10** specific source × region × day slices; **49** primary ZIP archives re-fetched and individually verified by full SHA-256; **4440** XML members successfully parsed; **0** explicit Power Quality ontology term occurrences in indexed *notice metadata fields*.
- Each archive is stored in a region-isolated directory: `{subsystem}/{document_type}/{date}/region-{region}/archive-NNN/documentation-archive.zip`. Region and date receipts are separate, with SHA-256, XML source locator, and candidate classification.
- The old common-region directory is explicitly quarantined with `UNTRUSTED_REGION_COLLISION.json`; both the collector and independent auditor fail closed if directed to that legacy root. Archived source bytes retained for incident analysis but excluded from coverage.
- This table counts inspected **XML documents, not unique tenders**. It is not representative of all days or all trading platforms. Candidate count zero in these metadata excerpts does not establish zero Power Quality demand or missing equipment in annexes.

| Statutory subsystem | Sample date | Region | SHA-verified ZIP | XML inspected | PQ metadata occurrences |
|---|---|---:|---:|---:|---:|
| 44-FZ | 2023-11-08 | 77 | 7 | 656 | 0 |
| 223-FZ | 2023-11-08 | 77 | 5 | 451 | 0 |
| 44-FZ | 2024-10-08 | 77 | 6 | 594 | 0 |
| 223-FZ | 2024-10-08 | 77 | 5 | 427 | 0 |
| 44-FZ | 2025-10-08 | 77 | 7 | 627 | 0 |
| 223-FZ | 2025-10-08 | 77 | 4 | 357 | 0 |
| 44-FZ | 2026-10-08 | 77 | 6 | 549 | 0 |
| 44-FZ | 2026-10-08 | 78 | 3 | 294 | 0 |
| 223-FZ | 2026-10-08 | 77 | 5 | 414 | 0 |
| 223-FZ | 2026-10-08 | 78 | 1 | 71 | 0 |

## Integrity and safety gates

- Distinct region-scoped ZIP paths prevent a Moscow receipt from being overwritten by a Saint Petersburg download for the same calendar day. A real collision was detected by independent SHA audit; the previous directory was invalidated, every sample was downloaded again and all 49 current ZIP hashes matched.
- DTD/external entity declarations are blocked, ZIP members and cumulative uncompressed bytes remain capped, as do archive downloads and per-XML parsing. The XML limit is **40 MiB** to support genuine EIS 44-FZ source files observed at 18.14 and 32.82 MiB; the previous 10/32 MiB thresholds rejected genuine archival documents.
- Full-archive receipts live on authorized Mac mini SSD outside Git; the versioned JSON audit artifact contains no SOAP token, archive download bearer URLs, or personally identifying contents.
- `src/modules/market_intelligence/eis_receipt_audit.py` independently reads saved receipts and recomputes ZIP SHA-256, failing closed on missing ZIP, mismatch, inconsistent counts, symlinks and the legacy collision marker. All 10 current sample slices validated.

## What this does not establish

- Full 2023–2026 monthly or national tender coverage, exhaustive commercial ETP discovery, original winner/protocol party roles, design/EPC structure, contract or NMC price totals, manufacturers' market shares, or final supplier TAM.
- Source dates are exactly those listed in the table, not every day/month in the historical interval. Notices may have several revisions, so 4,440 XML documents must not be treated as 4,440 unique procurement projects.
- Hidden Power Quality equipment in electrical substation modernization EPC attachments requires a separate Data Platform index of the original approved annexes and evidence review. Search metadata alone is insufficient.

## Exact reproduction (authorized Mac mini)

```bash
python -m src.modules.market_intelligence.eis_receipt_audit \
  --root /Volumes/ArvectumSSD/Arvectum/runtime/market-intelligence/eis-region-isolated-v2 \
  --attempt-date 2026-10-25 \
  --json-out data/market_intelligence/power_quality/eis_source_sample_20261025.json
```

Note that rerunning source collection performs real read-only SOAP requests and archive downloads, unlike the read-only SHA audit above.
