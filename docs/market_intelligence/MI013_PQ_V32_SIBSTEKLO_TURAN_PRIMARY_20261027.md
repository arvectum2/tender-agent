# MI-013 / Power Quality — Original 2024 failed EPC and 2026 customer-owned 6kV UKRM installation (v32)

As of 2026-10-27. Independent original EIS final DOCX and Bidzaar first-party tender original DOCX, with live PostgreSQL admission into canonical `arvectum-market-pq-6-35kv`. This report is **not** a declaration of national market population or two newly signed contracts.

## Existing commercial procedure №306-644, Bidzaar, 13 March 2026 — ООО «Сибирское стекло»

[First-party original Bidzaar lot №35](https://bidzaar.com/app/process/light/019ce668-617b-7b1a-861e-113ed78182af). [Actual buyer's technical specification DOCX](https://bidzaar.com/api/filestorage/files/download/8042258e-bd58-4efc-9f98-b00db6113f82), **43,070 bytes; SHA256 `28c970162cc7b36cff91df3b64ea4168c5717cc43554aea162440e6d10272516`**. This file was downloaded successfully from the original Bidzaar file endpoint and its 8,724 characters of native Word text extracted.

| Original technical parameter | Source-proven value |
| --- | --- |
| Buyer | **ООО «Сибирское стекло»** |
| Work site | Новосибирск, Даргомыжского 8а, РП-30 and КТП-17, СК-3 |
| Device class | **6 кВ** |
| Planned contractor mounting work | **2 × 900 квар UKRM**, 1,800 квар aggregate connected nameplates |
| **Who supplies the compensators?** | **Buyer!** Clause **2.1** states the UKRM 6kV are supplied by the customer |
| Contractor scope | Fabricate support frames, mount customer-furnished UKRM, connect to existing 6kV sections, supply and fit Tavrida Electric **КСО-272 modernization kit** in РП-30 bay 8, supply relay protection, current transformers and cables, commissioning |
| Contract timing | Begin within 5 calendar days after signature; finish within 35 working days from start |
| Bid conditions | Required on-site bidder visit, quoted detailed works estimate |
| Signed installer agreement and price | **Not identified** |
| Independent source status | Primary buyer TЗ verified by SHA, original ETP closed stage 17 April 2026, no public awarded supplier or registered contract |

**Market classification changed:** `commercial:306-644:lot35` was already one of the 101 notices. Its **new 1.8Mvar rating is an installation capacity indicator, not a sale of 1.8Mvar of new UKRM equipment**. The two installed units are *customer-furnished*, so no OEM can be inferred from the installer bid. Only contractor-supplied switching/bay materials and installation are inside contract scope.

The future discovery avenue is the customer’s *earlier purchase* of those two UKRM, which is economically distinct from this montage contract. Do not conflate the two.

## Existing EIS procurement №32413708738, 2024, PS 220kV Turan expansion — **both bidders rejected**

Source [official EIS original Protocol №4/3119384 signed 29 July 2024](https://zakupki.gov.ru/223/purchase/public/download/download.html?id=95895747), **40,701 bytes**, SHA256 **`692c0c546d581257a9855d7f5038a2f9f7147f2b9277b726c20303f0dbc1e25e`**, read directly as DOCX. A second [EIS indexed ID 95895888](https://zakupki.gov.ru/223/purchase/public/download/download.html?id=95895888) is byte-identical: **one source document, not two protocols**.

Subject: design, construction, commissioning and equipment supply for high-voltage **220kV** lines and Turan substation, with **UShR/ShR 220kV 40Mvar and BSK 220kV 110Mvar** in the complex title. This is *adjacent HV* and **not a proven 6–35kV equipment order**.

The 2024 commission reports:
- NMC **826,223,180.00 ₽ including VAT20** (688,519,316.67 ₽ excluding VAT).
- **ООО «ЛЭМ»** offered **826,222,954.64 ₽ VAT included**.
- **ООО «ЭНЕРГЕТИЧЕСКОЕ СТРОИТЕЛЬСТВО»** offered **826,223,180.00 ₽ VAT included**.
- **0 admitted, 2 rejected** because both bidders’ project-design and author-supervision timelines began *after* planned construction mobilisation, violating the tender contract.
- The commission declared the procedure **failed** and proposed re-tender if needed. **NO winner**, **NO signed contract**, no realized 6–35kV sale.

Unlike an earlier public title without original outcome, **this source conclusively excludes the 826.2m rub EPC notice from any signed tender turnover, component revenue or actual awarded compensation-unit figures**. It remains a historical *procurement intent* entry, not a positive 2024 hardware sale.

## v32 production data platform result

Canonical **101 original procurement notices**, unchanged. Two **existing** records received a primary verified source JSONB patch: `commercial:306-644:lot35` and `223fz:32413708738:lot1`. Two additional named company appearances in verified committee protocol cause progressive count **30→32** (not 32 distinct awarded companies). The 5 separately confirmed original signed RD223 contracts **unchanged**.

- v32 structured source: `data/market_intelligence/power_quality/primary_sibsteklo_turan_docs_20261027.v32.json`.
- Transactional append via `scripts/market_intelligence/apply_pq_evidence_v32.py`, no broad database re-import, unchanged stable existing resource IDs.
- Verified pre-write PostgreSQL `pg_dump -Fc` backup: `/Volumes/ArvectumSSD/Arvectum/runtime/data-platform-backups/data-platform-arvectum_data-20261027T193025Z.dump`, **37,465,965 bytes**, SHA256 `08ab9e98ffdda7fd97668d97a3df5b30dc2aec06bc9119ab2543b7b448b8b67f`; SHA+companion manifest checked before transaction.
- Atomic PostgreSQL commit passed source identity checks, original/source count guards and independent readback. **101 resources, 101 records, 98 metadata v29, 1 v31, 2 v32**. A total **15** previously collected procurement cases now embed at least one original primary document overlay in `dp_records.data.mi013_source_enrichments`.
- Other Data Platform collections unchanged (**2,192 non-PQ resources; 2,192 total `dp_documents`**).
- Follow-up direct read-only importer `--check-db` found **2 already enriched / 0 pending**; reproducible tests in `tests/test_mi013_pq_v32_originals.py` and older v29 tests.
- Receipt: `data/market_intelligence/power_quality/mi013_production_enrichment_receipt_20261027.v32.json`; operational manifest: `verified_public_leads_20261027.v32.manifest.json`.
- Future source query **`86829457` (Kogalym UKRM10.5kV450kvar)** only appears on a secondary Rostender category listing; no unique first-party procurement ID or technical/bidder original; it is **NOT** source-grade enough to add as notice 102. It remains a retrieval queue candidate.

## Prioritized following original source work

First locate actual first-party **signed** equipment buyer/price for three source-verified 6–12kV direct-device offerings: 2025 Kuzbass `32514947144` (14×450kvar capacitor units), MES South `32515029641` (12×450kvar), 2026 Bashkirenergo Nagornaya `32515582393` (6kV200kvar stepped UKRM), and Meleuz `32616296475`. Source-grade buyer-supplied equipment ownership at Sibsteklo points to a *prior purchase*, not 2026 installation sale. Also preserve the cancelled `ГП628666` ↔ possible `ГП630876` re-tender link and get original ETGPB archive and price. For 2024 Turan, identify any *new independently numbered successful procedure*, do not reclassify the failed 2024 original.

**Sourcing guard:** neither a tender’s technical design nor nominal device count is proof of final signed supply. Do not sum high-voltage EPC, low-voltage UKRM, 3-year price ceilings, denied bids and proposed buyer-furnished equipment as medium-voltage FGI addressable booked revenue.
