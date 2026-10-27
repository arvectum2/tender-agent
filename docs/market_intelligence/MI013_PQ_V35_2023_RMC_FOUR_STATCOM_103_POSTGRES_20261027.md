# MI-013 PQ original-source research v35 — Russian Copper Company 4×STATCOM indexed solicitation, 2023, full PostgreSQL sync

Date: 27 October 2026. This is the continuing append-only 2023–2026 procurement research, **not** a restart or a 20-record alternative shortlist.

## New genuine procurement signal: Tender.Pro original indexed public page 834269

**[Original Tender.Pro indexed public card](https://www.tender.pro/api/tender/834269/view_public)**. Independent first-party webpage search index cached its original page contents; the primary Tender.Pro site returns **HTTP503** on five direct request variants from the Mac mini, so original rendered HTML bytes and attached TT document are **not currently retrieved**. Grade this as `first_party_original_indexed_by_search_engine_not_directly_retrieved`, **not a downloaded original protocol**.

| Field | What indexed original Tender.Pro card supports |
| --- | --- |
| Legal organizer | АО «Русская медная компания» |
| Tender number / published | **834269 / 6 December 2023** |
| Original project | Complex producing grinding steel balls, `ГПП 110/35/10 кВ «Сфера»`, Alapayevsk, 20 Moskovskaya St |
| **Lot 1** | **4 sets** of electrical power quality improvement units, described as `Статком`, to original `УУКЭ` engineering questionnaire |
| **Lot 2** | **1** work position for installation and commissioning of sets |
| Bid closing | **25 December 2023 08:00 MSK** |
| Supply requested by | **30 April 2024** |
| Tender currency | RUB |
| Original enquiry prices / NMC / tender participant list | **Not visible in indexed source** |
| Original equipment manufacturer, supplier, signed contract, actual installation | **Not verified** |
| Device-specific nominal voltage or kvar/Mvar | **Not verified**; site's 110/35/10 kV substation description does **not** prove STATCOM 10kV, 35kV, 110kV, or its nominal kvar |
| Evidence of 4 STATCOM *delivered* in 2024 | **NONE**. The original commercial procurement **requested** 4 kits, not independently verified actual sales. |

The note about inclusion of delivery to the site and provision of Russian technical certifications is a **buyer requirement**, not a confirmed manufacturer localization/certification result. No winning supplier or proposed price has been inferred.

This gives Arvectum/FGI a *named historical prospect* for 4 power quality units in the copper/mineral industry. Before using it in strict market 6–35kV or FGI statcom price benchmarks, original device `опросный лист на УУКЭ`, signed agreement and manufacturer are required. Also check overlap with later 2024 RMC procurement projects by the exact facility and end-buyer; the title GPP Sphere itself isn't grounds to merge/split orders.

## Canonical append-only source and Data Platform write

- New independently unique canonical procurement notice key: `commercial:834269:lot1`; related service Lot 2 is an associated line in the **same** procurement, not counted as an extra independent procurement.
- Source sidecar `data/market_intelligence/power_quality/original_indexed_tenderpro_rmc_statcom_20261027.v35.json`, explicitly stores grade and HTTP503. `quantity=4` with `nominal_voltage_kv=null`, `nameplate_kvar=null`, `commission_winner=null`, `nmck_rub=null`, `signed_contract_price=null`. Not counted as sold hardware.
- **102→103** distinct procurement signals/records; zero new original registered signed contracts. Total remains 5 signed original RD223 cases; original named protocol participant occurrences remain 32.
- Safe importer `scripts/market_intelligence/import_pq_tenderpro_statcom_v35.py` specifically checks the indexed-only provenance, no rated device voltage, no signed award, stable canonical identity and owner collection. Executed only in isolated detached research worktree, with original dirty local Tender Agent checkout unchanged.
- Official verified **prewrite PostgreSQL backup**: `/Volumes/ArvectumSSD/Arvectum/runtime/data-platform-backups/data-platform-arvectum_data-20261027T205522Z.dump`, **37,471,012 bytes**, SHA-256 **`739df1bd82b09d5964a16772d0cfa023644989cf4004a2e803969380449f9e74`**, verified against backup `.manifest.json` and checksum companion before transaction.
- Production `arvectum_data`, `arvectum-market-pq-6-35kv`: guarded atomic INSERT of one `dp_resources` + one `dp_records` row completed. Read-back **103 resources / 103 structured records / 103 unique canonical keys**. Other non-PQ resources **2,192 unchanged** and documents **2,192 unchanged**. New source sha256 **`69118a20481e938a0c68762e8ed20477609585050cbebaa3287d720734cd90d0`**.
- PostgreSQL source metadata versions: **97 v29 + 1 v31 + 2 v32 + 1 v33 + 1 v34 + 1 v35**. The 16 source evidence-enriched earlier notices remain in place (15 first-party and 1 secondary), and this brand-new v35 notice has its own indexed-original provenance.
- `scripts/market_intelligence/materialize_pq_research_v35.py`: complete and deterministic regeneration of 103 notices from original v20+v23, primary v21–v28, v31/v32 patch and original v33/v35 plus v34 secondary BOM. **Independent GitHub-to-production `content_hash` check: 103/103 exact matches; zero drift.**
- Targeted tests: prior v29 8 + v32 4 + v33 6 + v34 5 + v35 5 = **28/28 passed**. The v35 importer read-only `--check-db` reports already-imported/idempotent.
- Receipt: `data/market_intelligence/power_quality/mi013_production_import_receipt_20261027.v35_103.json`; operational manifest: `verified_public_leads_20261027.v35.manifest.json`; backlog of original questionnaire and manufacturing/supplier identification: `primary_evidence_retrieval_queue_20261027.v17.json`.

## What remains unresolved

1. Highest value first-party originals are **signed RD223 contract documents** for 2025 `32514947144` 14×12kV filter capacitors, `32515029641` 12×12kV filter capacitors, 2026 `32515582393` 6kV/200kvar UKRM Nagornaya and `32616296475` 6.3kV/≥500kvar Meleuz.
2. **ETGPB ГП630876** original 10kV retrofit XLSX, 7z (design drawings and factory documents), selected OEM/contract; 10 visible position lines in v34 are **only secondary reproductions**, not first-party.
3. **Tender.Pro 834269** original UUKE questionnaire to establish 6–35kV device voltage, reactive capacity, technology (IGBT active SVG/STATCOM vs other units), actual manufacturer, actual legal signed sale and equipment installed.
4. 2024 original commercial source gap and strictly line-item 6–35kV equipment delivery rather than high-voltage EPC project total (Turan 2024 failed, Hani EPC bidder original offer only), LV mixed lots and tender framework ceilings.

**Never treat 103 research case entries as 103 awarded contracts, or count 4 proposal STATCOM sets as four deliveries, or present their unknown voltage as proven 6–35kV sales.**
