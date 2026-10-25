# MI-009 — bounded historical EIS acquisition across years

**Status: technical collection pilot, 25 October 2026.** Do not extrapolate this source-date sampling to national Power Quality demand.

## Implementation

`src/modules/market_intelligence/eis_history_plan.py` is a generic source-day acquisition planner. No equipment taxonomy is hard-coded in the scheduler. It audits the already-existing region-isolated, source SHA-verified original EIS ZIP receipts through `eis_coverage.audit_day`, then selects missing cells for a bounded SOAP collection budget.

- **Dry-run default:** no network call until the operator provides `--execute`. Maximum 12 real date/region/subsystem calls per invocation. Use `--max-calls 2` for controlled live source collection.
- **Fair historical coverage:** breadth-first bisection across all months for geographic and yearly spread, rotating priority across regions and EIS statutory subsystems instead of fetching only one source or the newest dates.
- **Resume-safe:** a successful original SHA-verified source-day is skipped. Failed, incomplete, tampered or orphaned archived source material is never silently overwritten. Suspicious material requires independent human/source integrity review.
- **No unofficial shortcuts:** existing getDocsIP SOAP client enforces verified TLS and official archive host allowlist. Original ZIPs and sensitive receipts remain in protected Mac mini SSD runtime, outside git. Network errors stop the batch; the status and failure are preserved.
- **Source record integrity:** valid historical days require `complete_with_archive_scan`, expected region and law, exact date, saved original ZIP and independently checked SHA-256, and credible XML scan count. Day counts are not unique procurement counts.
- **No financial inference:** no signed contract, winner, EPC role, price or market TAM may be derived solely from a notice, application, early-stage protocol or proposed contract.

## Authentic live acquisition + independent result

Initial input for Moscow **77** and Saint Petersburg **78**, two EIS subsystems **44-FZ PRIZ** and **223-FZ RI223**, date window **2023-10-25 to 2026-10-25**:

| Observed scope | Before MI-009 | After MI-009 |
|---|---:|---:|
| Requested source-day slots | 4,388 | 4,388 |
| SHA-verified complete source-day slots | 10 | **21** |
| Source-day slots not yet collected | 4,378 | **4,367** |
| Independently SHA-verified official ZIP archives | 49 | **85** |
| XML members inspected (including notice revisions) | 4,440 | **7,467** |

**11 newly verified daily EIS source cells**, 36 additional original ZIPs, 3,027 additional XML documents. New verified cells:

| Original date | Region | Law | ZIP | XML |
|---|---|---|---:|---:|
| 2023-10-25 | 77 | 223-FZ | 6 | 538 |
| 2023-12-15 | 78 | 223-FZ | 1 | 91 |
| 2024-01-15 | 78 | 44-FZ | 2 | 119 |
| 2024-02-15 | 77 | 223-FZ | 4 | 379 |
| 2024-05-15 | 78 | 44-FZ | 6 | 542 |
| 2024-07-15 | 77 | 44-FZ | 6 | 547 |
| 2024-12-15 | 78 | 223-FZ | 1 | 5 |
| 2025-04-15 | 78 | 223-FZ | 1 | 95 |
| 2025-09-15 | 78 | 44-FZ | 4 | 313 |
| 2026-02-15 | 77 | 223-FZ | 1 | 8 |
| 2026-07-15 | 77 | 44-FZ | 4 | 390 |

The independent `eis_coverage` SHA replay validated all 21 original source-day receipts with **zero invalid-evidence cells**. Versioned non-sensitive summary: `data/market_intelligence/power_quality/eis_coverage_20261025_extended.v2.json`. No secret token, original document content, URL bearer credential, bidder PII or unknown winner was copied into the repository.

The ratio 21/4,388 = **0.48% of deliberately selected 2-region/day/law cells**, NOT sample representativeness, actual EIS nationwide completeness or share of any equipment market. Most regions of Russia and commercial ETPs are not represented. Missing source-day cells **do not imply absence of procurement**.

## How to reproduce

```bash
python -m src.modules.market_intelligence.eis_history_plan \
  --root /Volumes/ArvectumSSD/Arvectum/runtime/market-intelligence/eis-region-isolated-v2 \
  --ontology data/market_intelligence/power_quality/ontology.v1.yaml \
  --date-from 2023-10-25 --date-to 2026-10-25 \
  --region 77 --region 78 --subsystem RI223 --subsystem PRIZ \
  --max-calls 2
```

By default this **only prints the plan**. Add `--execute` to perform actual read-only EIS SOAP calls and download original archives. Avoid running jobs against the quarantined legacy `.../eis` runtime tree.

Reproduce source status (independent SHA check) through:

```bash
python -m src.modules.market_intelligence.eis_coverage \
  --root /Volumes/ArvectumSSD/Arvectum/runtime/market-intelligence/eis-region-isolated-v2 \
  --date-from 2023-10-25 --date-to 2026-10-25 \
  --region 77 --region 78 --subsystem RI223 --subsystem PRIZ
```

## Next scope (not part of this merge)

- Full 36-month source coverage expansion nationwide with rate limits, daytime load controls, and explicit missing/failed cells. Existing limited staged rounds can continue with the same planner; no shell background batch should run unbounded.
- Collect **original technical documents** (PDF/DOCX/XLSX and native annex ZIPs) linked from EIS notice/protocol XML, verify secure attachment URL source host, independently SHA-hash and ingest into **Data Platform**. Only then will semantic ontology search find hidden Power Quality scopes inside EPC modernization.
- Extract and review original official award/protocol decisions and signed contract registers to verify winner INN, EPC/design/supplier role, NMCK and signed contract prices before monetary claims.
- Expand commercial ETP source acquisition and join/dedup by official registry number where possible, while preserving original per-platform source evidence.
