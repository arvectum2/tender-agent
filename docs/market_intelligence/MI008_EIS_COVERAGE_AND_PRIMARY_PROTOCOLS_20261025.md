# MI-008 — EIS source-day coverage and original protocol linkage

**Evidence cut-off: 25 October 2026, Moscow. Read-only, first bounded pilot; not nationwide market size.**

## Why

The EIS SOAP source API is now recovered and code merged to Tender Agent `main` as PR #503. The official source can supply native notices and protocols, but a few successful SOAP archive fetches cannot substantiate complete market coverage or identify contract awards. MI-008 introduces two **generic offline evidence functions** with no Power Quality-specific ontology, additional indexing, or tenant rights:

- `eis_coverage.py` audits each requested **calendar day × region × legal subsystem** cell against original region-isolated receipt and ZIP SHA-256 bytes. Statuses: `verified_day`, `missing`, `incomplete`, `evidence_invalid`.
- `eis_source_ledger.py` parses original source ZIPs with DTD/ZIP resource limits, extracts original 223-FZ `purchaseNotice` and `purchaseProtocol` evidence, preserves raw XML member and SHA, links on exact registry number without guessing companies/winners. A preliminary 44-FZ `epNotification*` extraction leaves unrecognised notice numbers null instead of guessing.

## Genuine verified input scope

`data/market_intelligence/power_quality/eis_coverage_20261025.v1.json` is a non-sensitive derived monthly snapshot. Request horizon: **2023-10-25 through 2026-10-25 inclusive**. Region codes: `77` (Moscow) and `78` (Saint Petersburg). Subsystems: `RI223/purchaseNotice` and `PRIZ/epNotificationEF2020`.

| Measured unit | Count |
|---|---:|
| Requested source-day slots = 1,097 dates × 2 regions × 2 law regimes | **4,388** |
| Source-day slots verified with bytes and receipts | **10** |
| Missing source-day slots, not synonymous with zero procurement | **4,378** |
| Source ZIPs independently SHA-256-verified | **49** |
| XML members in those ZIPs (including revisions, not unique tenders) | **4,440** |

**Only 0.228% of these specifically requested two-region/day/regime slots are source-verified.** This is **not** a sampling-based estimate of Russia's Power Quality procurement or of market value. An observed zero of ontology matches **in narrow indexed notice metadata** cannot prove no equipment in original technical annexes; EPC requirements may be buried in attached procurement documents.

## Original notice-to-protocol acceptance

Read-only authenticated `getDocsByReestrNumber` call for **RI223 procurement 32616447910** returned one primary ZIP. It contains:

- `purchaseNotice` XML whose exact `registrationNumber` is the procurement number.
- `purchaseProtocol` XML whose `purchaseInfo/purchaseNoticeNumber` matches the exact same procurement number; **one application** is present in the source protocol.


### Real 44-FZ envelope acceptance

On a distinct actual 44-FZ `PRIZ/epNotificationEF2020` archive for Moscow on 2026-10-08, **all 100 original XML members** had an explicit purchase number successfully extracted from `export/epNotificationEF2020/commonInfo/purchaseNumber`. The native `export` wrapper was discovered by examining the actual primary XML and is now supported. Zero winner or signed-contract claims were made. These 100 XML members may include revisions, so this is **not necessarily 100 unique tenders**.

Both XMLs were parsed by `eis_source_ledger.extract_archive`, their own SHA-256 computed, and linked by `link_original_documents`. Exactly **one notice-protocol linkage**, zero unlinked numbers, **winner_verified=false**, **signed_contract_price_verified=false**. The protocol has typed application fields such as `price`, `accepted`, `rating`, `contractSigned`, but these alone **do not establish signed contracts, actual EPC roles or contract prices**. No personal bidder details were copied into tracked Git data.

## Technical and safety decisions

- Source provenance requires a separately retained authoritative ZIP SHA from its receipt and computed member SHA-256. Cross-region ZIP collisions invalidate evidence; the quarantined **legacy** EIS root must never be used.
- XML entity/DTD declarations, unsafe ZIP names, oversized archive members and cumulative decompression are rejected. XML is never unpacked to a writable filename.
- Distinct versions of a procurement document are preserved by XML byte hash. Exact duplicate XML copies are collapsed; this is not necessarily canonical tender dedup across revisions, contracting organizations or mirrored ETP postings.
- A bid `price`, `rating=1`, or `contractSigned` raw protocol flag is deliberately **not interpreted as a validated award**. Contract award evidence still requires the original applicable procurement protocol and, where relevant, an actual signed contract or official contract register record with seller INN, price, currency, date and verified SHA/locator.
- Any public commercial or 223-FZ platform coverage not present in this EIS dataset is still `unobserved`.

## Reproduction on authorized Mac mini

```bash
python -m src.modules.market_intelligence.eis_coverage \
  --root /Volumes/ArvectumSSD/Arvectum/runtime/market-intelligence/eis-region-isolated-v2 \
  --date-from 2023-10-25 --date-to 2026-10-25 \
  --region 77 --region 78 --subsystem RI223 --subsystem PRIZ \
  --output /tmp/eis-coverage-report.json
```

Source ledger entry point (pure Python, no network): `extract_archive(zip_path, official_archive_sha256=..., subsystem="RI223", region="77", exact_date="2026-10-25")`, then `link_original_documents(records)`. Unit tests `tests/test_mi008_eis_coverage.py` and `tests/test_mi008_eis_source_ledger.py`.

## Next steps not claimed complete

1. Systematic source-day ingestion with bounded service usage over the 36-month window and all relevant regions; keep failures and missing periods explicit, not zero.
2. Original XML object normalization across notice/protocol and 44-FZ contract register; deduplicate by notice number and version, verify winning parties/INN and actual prices via original official protocol/contract.
3. Acquire and index **original technical annexes** through Data Platform generic hybrid/ontology search. EPC modernizations demand attachment-level matching, not only title/description.
4. Expand independent commercial ETP coverage with official platform notices and archived protocols, not aggregator-only leads.
