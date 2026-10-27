# MI-013 Power Quality — original buyer 6 kV / 500 kvar equipment prices separate from work (v36, 28 October 2026)

## Executive primary-source finding

For existing EIS/ETP Region procedure **32616296475** by ООО «Водоканал», Мелеуз (ИНН 0263017332), retrieved the **original first-party buyer's cost justification XLSX**, original technical DOCX, unsigned contract form and public tender documentation from the underlying procurement ETP. All four original files downloaded directly by the authorized Mac mini, identified by SHA-256. Previously we only knew whole-lot NMC and a selected **anonymized offer**, not item-level equipment spend.

**Original Excel source row breakdown**, sheet1 from `НМЦД (41).xlsx`, original direct [download](https://zakaz.etp-region.ru/fx/gpms/etpGetFileServlet?fileUUID=dbfilefs002080000q03kmh4c7au8vf4), SHA256 `fc342d5bfb6cdffdf4fa459f77cbd3ab957c78bce400fbc3d3c0141af18be218`, file length **34,673 B**:

| Costing line (each quantity 1) | External commercial quote #1, ₽ | #2, ₽ | #3, ₽ | Buyer NMC baseline average, ₽ |
|---|---:|---:|---:|---:|
| **УКРМ высоковольтный, 500 квар** — EQUIPMENT | **3,577,711.20** | **3,493,410.00** | **3,501,200.00** | **3,524,107.07** |
| Шеф-монтаж | 250,000.00 | 300,000.00 | 207,000.00 | 252,333.33 |
| Пусконаладочные работы | 130,000.00 | 140,000.00 | 115,000.00 | 128,333.33 |
| TOTAL per external dated original quotation / NMC | **3,957,711.20** | **3,933,410.00** | **3,823,200.00** | **3,904,773.73** |

Excel row 11 identifies source quotation numbers **№01907 27 July 2026**, **№02113 30 July 2026**, **№124 31 July 2026**. Excel row 13 equipment quote prices and mean; row 14 supervisory installation; row 15 commissioning; row 27 totals. All 3 source quotations are *original BUYER NMC documentation's quotations*, **not** original 223-FZ competition bids, legally registered contracts or public 3 supplier names. They do not prove the physical origin, production cost or amount actually paid.

The equipment alone represents **about 90.25%** of the buyer's initial whole-lot NMC; shef-montage + PNR **380,666.66 ₽**. An initial equipment-only price estimate **3.524 million RUB** (3 sample quotations **3.493–3.578 million**) is a legitimate *first-party historical price benchmark* for comparable **2026 6–6.3 kV >=500 kvar controlled thyristor + reactor + harmonic filtering assemblies**. VAT status of the pricing XLSX is **not established separately**; do not pretend it is a known excl-/incl-VAT wholesale transaction.

Original selected application #79410 in earlier EIS September source at **3,865,725.99 ₽ for the WHOLE offered tender**, less than starting 3,904,773.73 ₽, **NOT a signed line-item hardware-only value**. Original published contract file remains an empty SUPPLIER + VAT + signed-price draft; the original ETP live case status is `Заключение договора`. No original signed RD223 supplier legal INN, actual hardware price, full shipment or working compensator verified.

## Specific product technical benchmark

First-party [original buyer technical DOCX](https://zakaz.etp-region.ru/fx/gpms/etpGetFileServlet?fileUUID=dbfilefs002080000q03kmh4j5tmvv6g), 28,240 B SHA256 `ca9a840c69bce647287c4571b675d57f401f89a20ae3d24f3842d8e24485b781`:

- Electricity bus **up to 6.3 kV**, actual technical connection at **6 kV**, network 50Hz; compensator nominal **at least 500 kvar**; system upper working voltage **12 kV**.
- **Thyristor-reactor** architecture with controlled shunt reactor, three-phase switching via thyristor valves, **higher-harmonic filter**, current/voltage transformers, integrated industrial-class PQ analyzer, microprocessor protection and a control archive.
- Continuous reactive power regulation 0 to +100%, specified **max step 50 kvar**; **control system response up to 5 ms**, separate load change reaction **up to 10 ms**; **cos φ ≥0.98** and regulation precision ±0.02.
- Cabinet **≥ IP54**, forced air cooling, installation indoors; initial harmonic analysis through the **50th harmonic**, original required data monitoring before supply for ≥7 days and after commissioning.
- Manufacture/delivery within **55 business days** of contract; full contract **70 business days**; **the BUYER assembles the delivered UKRM components itself**, supplier performs supervised commissioning and tests within 7 days of buyer's assembled completion. Original warranty at least **24 months after commissioning**.

### Critical national origin detail — **1875 limitation, not prohibition**

Parsed the actual original Word table cell-by-cell (not just the flattened text). Header order is `1875 (Запрет)`, `1875 (Ограничение)`, `1875 (Преимущество)`; the original row `28.99.39.190 — УКРМ высоковольтный` has **empty prohibition cell, tick ✓ in limitation cell, empty preference cell**. This proves only what the buyer **marked in its original tender**, not whether the application of decree [PP RF №1875](https://www.consultant.ru/document/cons_doc_LAW_494318/) to this exact product/contract is ultimately valid or how EAEU/Chinese manufacturer origin declarations must be legally evaluated. External secondary index [ВсемПодряд](https://vsem-podryad.ru/activepurchase/b9434c80-cd17-4dbf-b1d0-ba30ff7c2e1e/) says restrictions absent; the ORIGINAL BUYER technical table is stronger evidence of the original source text. Do **not** misclassify as absolute Chinese goods ban from checkbox alone.

## Original file provenance

| Original file | Direct primary link | SHA256 |
|---|---|---|
| `НМЦД (41).xlsx` — source of priced estimate | [Original Excel](https://zakaz.etp-region.ru/fx/gpms/etpGetFileServlet?fileUUID=dbfilefs002080000q03kmh4c7au8vf4) | `fc342d5bfb6cdffdf4fa459f77cbd3ab957c78bce400fbc3d3c0141af18be218` |
| `Техническое задание на оборудование 14.08 (2) (1).docx` | [Original Word](https://zakaz.etp-region.ru/fx/gpms/etpGetFileServlet?fileUUID=dbfilefs002080000q03kmh4j5tmvv6g) | `ca9a840c69bce647287c4571b675d57f401f89a20ae3d24f3842d8e24485b781` |
| `Проект договора (2495).docx` — **unsigned template** | [Original draft](https://zakaz.etp-region.ru/fx/gpms/etpGetFileServlet?fileUUID=dbfilefs002080000q03kmh4i38vumuc) | `0360f92c4b701319af60c53a8f1c911a3b0cb5b4e7cda79f2c857a23babaade4` |
| `АД (1 часть).docx` — auction documentation | [Original buyer document](https://zakaz.etp-region.ru/fx/gpms/etpGetFileServlet?fileUUID=dbfilefs002080000q03kmh42ma2rdlk) | `9949b25a7b693651ea89dc6ffedc0cb94899aedc8fd315af216d54d3f79e5bc7` |

Source page [ЭТП «Регион»](https://torgi.etp-region.ru/app/OfferCard/page?OfferCard.offerUUID=Scorebofs002080000q03ju2cimtcd2js), HTTP200 on authorized Mac mini. Both original September source final scanned 4-page PDFs also directly retrieved from buyer's original ETP domain, but this new phase does not claim any supplier identity from them.

## Database sync and market-statistical interpretation

No new procurement notice and no new legally registered signed contract were discovered: existing key `223fz:32616296475:lot1` enriched. Source data committed to `data/market_intelligence/power_quality/original_meles_6kv_itemized_cost_and_regime_20261028.v36.json`.

- Official independently verified prewrite custom `pg_dump`: `/Volumes/ArvectumSSD/Arvectum/runtime/data-platform-backups/data-platform-arvectum_data-20261027T214653Z.dump`, **37,472,843 B**, SHA256 `4bec2cc377ac9c804940bd140c74a72fa57e8bab92ac8bbd5d414c20987c8867`. Companion manifest/checksum verified **before** SQL mutation.
- Guarded one-case transaction in `scripts/market_intelligence/apply_pq_evidence_v36.py`, source/resource identity and original hash checks; SQL COMMIT and independent readback **PASS**. New content SHA256 `cdcc71359739f3d9f2d613f50ca8d9c220b6605e3a8a6456111ad0562e995afd`.
- **103 PostgreSQL procurement resources +103 structured records**, stable canonical IDs; **96 base metadata v29 +1 v31 +2 v32 +1 v33 +1 v34 +1 v35 +1 v36**.
- Full materializer `scripts/market_intelligence/materialize_pq_research_v36.py` regenerates **all 103** GitHub original source records, and production `content_hash` compares **103/103 equal** with PostgreSQL, **zero drift**.
- Targeted tests: **33/33 PASS** (v29 eight, v32 four, v33 six, v34 five, v35 five, v36 five). No changes to other 2,192 non-PQ Data Platform resources or 2,192 documents. Previous 16 source-evidence-enriched cases remain 16, since Meleuz was already enriched at v21.
- Signed original RD223 contract count remains **5**; original protocol company applicant occurrences remain **32**; new BUYER quotation samples **3**, distinctly stored as `price_basis=three_non_awarded_buyer_quotes`.
- Production receipt `mi013_production_enrichment_receipt_20261028.v36.json`, corpus state `verified_public_leads_20261028.v36.manifest.json`, retrieval queue `primary_evidence_retrieval_queue_20261028.v18.json`.

**Market research implication for FGI:** price benchmarking on component specifications can now compare actually separate hardware vs shef-installation vs PNR, and any sales strategy must explicitly review 1875 national restriction obligations for the selected precise product. *Neither source permits describing a manufacturer or actual Chinese company winning this procedure.*

## Resume

Next highest priority: locate primary RD223 **signed** supplier INN and contract ID for `32616296475`; identify contracts for original Kuzbass/MES South **12 kV KЭПФ** `32514947144` and `32515029641`, Bashkirenergo Nagornaya `32515582393`, original ETGPB `ГП630876` 7z/XLSX and 2023 RMC four-STATCOM `834269` original questionnaire. Distinguish one engineering prospect vs signed purchase and 6kV/10kV vs LV / HV EPC sites.
