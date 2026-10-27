# MI-013 Power Quality — v34: component-level bill of materials for existing 10 kV NOVATEK retrofit (27 Oct 2026)

## Original research status and buyer

Procedure **ГП630876**, **ООО «НОВАТЭК-Усть-Луга»**, INN **4707026057**, published **22 June 2026**; applications closed **7 August 2026**. Subject: supply of components and engineering/dismantling, installation and tuning services to **modernize an EXISTING UKRM 10 kV** at distribution transformer substation, not a purchase of eight new devices.

Source: [Synapsenet equipment positions marked “С сайта площадки”](https://synapsenet.ru/zakupki/gazprombank/%D0%B3%D0%BF630876%231344734--leningradskaya-obl-postavka-oborudovaniya-s). **SECONDARY** publication of platform-sourced ETGPB information, HTML retrieved on Mac mini by HTTPS HTTP200 on 27 Oct 2026, 51,926 bytes, SHA256 `e23a11d035ed01fbbe972942c9343d2116172af08ce861fef07c73b1043d735e`. The actual **original ETGPB technical archives have NOT been obtained**, so this evidence must **not** be presented as a verified original buyer XLSX, verified winner, signed contract, or a complete BOM.

### Ten publicly visible source-reprinted line items

| Item as displayed | Number | Correct classification |
| --- | ---: | --- |
| Development of design/working documentation (РКД) | Unspecified | Design services |
| Three-phase inrush switching reactor for a 450 kvar step | **3** | Switching reactor component |
| Three-phase vacuum contactor 400 A, 10.5 kV, 220VAC control | **3** | Switching component |
| Three-phase capacitor, equivalent type **КЭПЗ-10,5-150-3У2** | **1** | 10.5kV / 150 kvar component |
| Dismantle/install equipment, tune controllers to 1490-2025-12-99.1-ЭМ | Unspecified | EPC/modernization service |
| Three-phase switching reactor for 150 kvar step | **1** | Switching reactor |
| Three-phase switching reactor for 300 kvar step | **4** | Switching reactor |
| Fuse ПКТ-VK 31.5A / 20kV | **3** | Protective fuse |
| Fuse ПКТ-VK 63A / 20kV | **12** | Protective fuse |
| Fuse ПКТ-VK 80A / 20kV | **3** | Protective fuse |

Technical reconciliation: **8 switching reactors** (3 rated for step 450 kvar +4 for 300kvar +1 for 150kvar), **3 vacuum contactors**, **1 nominal 10.5kV 150kvar condenser**, **18 fuses**. *No inference* that reactor step labels sum to 2,700 kvar installed bank rating, no eight UKRM units sold, no country of manufacture or certified OEM verified. 20kV is the protective fuse component rating, not UKRM nominal bus voltage.

The corresponding [original potential attachments listed by the aggregator](https://synapsenet.ru/zakupki/gazprombank/%D0%B3%D0%BF630876%231344734--leningradskaya-obl-postavka-oborudovaniya-s) are `4._Модернизация_УКРМ.7z`, `3._Заводская_документация_на_УКРМ.7z` and `2._Форма_4_Технические_требования_.xlsx`; direct source access requires further verification, none of these binaries have yet been read. The earlier cancellation/retender `ГП628666` is an unresolved same-project candidate, not a second confirmed installation. **Winner, signed buyer/supplier legal parties, payment and prices remain unknown.**

## Strict original source grade and data population

Original note `commercial:ГП630876:lot1` was already one of the 102 legal procurement records in v33; this phase adds **zero** notices, **zero** 6-35kV signed equipment sales, and **zero** signed-contract prices.

The incremental source is saved as `data/market_intelligence/power_quality/secondary_etgpb_novatek_bom_20261027.v34.json` with `source_grade=secondary_aggregator_public_original_etp_position_replica_not_original_etp_archive`.

The guarded SQL importer `scripts/market_intelligence/apply_pq_evidence_v34.py` only edited this **one existing** resource in `arvectum_data`, collection `arvectum-market-pq-6-35kv`, including `dp_records.data.mi013_source_enrichments.v34.verified_secondary`:

- Before SQL, official `pg_dump -Fc` file `/Volumes/ArvectumSSD/Arvectum/runtime/data-platform-backups/data-platform-arvectum_data-20261027T204416Z.dump` (37,469,593 bytes) SHA256 `29e9743d62ef540a1da960810cb64322cdd7d04b678ea5113fe027deed5ef1c7` verified against file, companion checksum and manifest.
- Transaction result **COMMIT and readback PASS**, source-content SHA256 `c37d6384d32702e6d871793e46520a330dba0e7c10efbf161f9d1fd9b865f122`.
- **102/102** production PostgreSQL resources and structured records persist, **97** metadata v29 + **1** v31 + **2** v32 + **1** v33 + **1** v34, **16** source-enriched cases total (**15 with original documents in previous passes, 1 secondary-only new case**).
- Other Data Platform scope preserved: **2,192 other source resources and 2,192 documents**. No unrelated checkout code touched.
- Read-only deterministic `scripts/market_intelligence/materialize_pq_research_v34.py` rebuilds all 102 with source rows and original source sidecars; **102/102 PostgreSQL content hashes match, zero drift**.
- New tests `tests/test_mi013_pq_v34_novatek_bom.py`: **5 passed**, existing v33 6, v32 4, v29 8 = **23 passed**, and v34 `--check-db` says already applied.
- Version manifest `verified_public_leads_20261027.v34.manifest.json`, operational receipt `mi013_production_enrichment_receipt_20261027.v34.json`, queue `primary_evidence_retrieval_queue_20261027.v16.json`.

## Related research signal, not a new corpus notice

The independently discovered 2026 B2B acquisition `4559984` referencing **1× АУКРМ 6.3kV/1,350kvar**, already existed as **`commercial:4559984:ukrm-6p3-component`** in PostgreSQL. It was **not** added again. Original project and vendor were not further verified in this pass.

Continue first-party original signed RD223 contract work on **2025 KЭПФ 12kV** `32514947144` and `32515029641`, **2026 6kV 200kvar Nagornaya** `32515582393`, Meleuz 6kV `32616296475`, original private ETGPB retrofit technical 7z and competent 2024 contractor/procurement backfill. No source supports converting secondary BOM or unsold 2026 equipment into total Russian market volume.
