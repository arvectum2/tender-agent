# MI-013 Power Quality — verified 24 BSK capacitor components in 3 nominal-voltage classes, Rosseti (v37, 28 Oct 2026)

## Primary new evidence, without duplicate procurement

Existing EIS case **32616339168** (RTS **4006686**, buyer PАО «Россети» МЭС Юга, organizer АО «Россети Центр закупок»), published 31 August 2026. The tender title alone refers to “Поставка конденсаторов БСК (24 шт.)” and publicly reported NMC **6,807,600 ₽ including VAT22**.

Downloaded exact [FIRST-PARTY EIS original 7z tender archive](https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/file.html?uid=8FBB1BB807B64388802027D1A4F3827A), **850,428 bytes**, SHA256 `46c3237d2b632e3e7147ec2e49a44fcbdf95af8e04b6a4b2e300d594cd271710`; unpacked original buyer technical DOCX, specification DOCX, NMC comparison PDF and NMC justification DOCX, original tender notice and unsigned contract template.

Original equipment specification, verified native DOCX text **not category inference**:

| Original separate capacitor model | Nominal component voltage | Quantity | Nameplate kvar/unit | Buyer NMC baseline per unit **VAT22 included** | Buyer NMC line **VAT22 included** |
|---|---:|---:|---:|---:|---:|
| КЭПФ-12-450-2УХЛ1 | 12 kV | **12** | 450 kvar | **303,000 ₽** | **3,636,000 ₽** |
| КЭПФ-11,55-430-2УХЛ1 | 11.55 kV | **6** | 430 kvar | **275,000 ₽** | **1,650,000 ₽** |
| КЭПФ-4,2-510-2УХЛ1 | 4.2 kV | **6** | 510 kvar | **253,600 ₽** | **1,521,600 ₽** |
| **Total** | Mixed | **24** | – | – | **6,807,600 ₽** |

**Result: 18 of 24 components have rated equipment nominal voltage inside strict 6–35 kV**. Six at rated **4.2 kV are not in this range**; however a 4.2 kV individual capacitor's nameplate does **not** establish the electrical network bus voltage or necessarily mean a low-voltage 0.4kV installation.

Strict nominal-component initial-price basket = **5,286,000 ₽ inc VAT22**, separately priced below-6kV component basket = **1,521,600 ₽ inc VAT22**. Without VAT: **4,332,786.89 ₽** and **1,247,213.11 ₽** respectively; total NMC ex VAT = **5,580,000 ₽**.

The tender requires delivery to Пятигорск by **30 November 2026** and two years of warranty. It describes **individual replacement/spare BSK capacitors**, not purchasing one STATCOM or an entirely new UKRM per capacitor.

### Original source buyer quotations, price cannot be called contract revenue

Original `2. Расчет стоимости НМЦД.pdf` in source archive:
- 11.55 kV / 430 kvar, 6 units: quotation unit prices **282,006.44 / 280,408.11 / 275,000.00 ₽ VAT22**.
- 12 kV / 450 kvar, 12 units: unit prices **312,297.44 / 310,527.44 / 303,000.00 ₽ VAT22**.
- 4.2 kV / 510 kvar, 6 units: unit prices **259,587.51 / 258,116.25 / 253,600.00 ₽ VAT22**.

The buyer's original calculation derives from quotation **№26 (20 Feb 2026)**, **№006 (20 Feb 2026)** and **№74 (15 Jul 2026)**. The displayed final NMC values correspond to the third column in each respective item line, not a separately signed commercial sales price. No original signed actual purchase contract, named winning vendor, factory origin, delivery acceptance certificate, or invoice appears in this public archive; the draft agreement has blank supplier.

### Distinct national origin requirements, not interchangeable across procurement

The original `Приложение 1 к техническому заданию.docx` specifies for all **three** item lines `ОКПД 2 27.90.52.000` and marks **PP RF №1875 “преимущество”**. This differs materially from the separate 2026 Meleuz 6kV500kvar UKRM original buyer technical-table tick in **“ограничение”**. Do not treat Russian origin regime as uniformly prohibitive or identical across hardware categories: check each legal procurement, origin code and exact item.

The product drawing specs also require approval under **PАО «Россети» приказ №305 от 26.07.2023**, +45 to –60°C climate, welded type terminal insulators with press-fitted pins, and new devices. These technical requirements help assess OEM qualification for FGI and competitors; supplier/manufacturer identities remain blank.

### Files and exact provenance

All inner documents were successfully unpacked from the original official EIS 7z and verified:

| Inner original document | SHA-256 |
|---|---|
| `1. Техническое задание БСК (24 шт) +.docx`, 43,957 B | `eafb60890383a231e6f27fc496def4073dfcab705aa777a424e10101f4304ec2` |
| `Приложение 1 к техническому заданию.docx`, 29,441 B | `cd9907ac8e80f9a9abd1e5587921502f2fbfe214fdad221b40ef3df34a12473e` |
| `2. Расчет стоимости НМЦД.pdf`, 90,519 B | `255f2caf43c2dddb9479bdd24666378c88a546d9f08cb44a630f193fbf89159d` |
| `3. Обоснование расчета_ НМЦД.docx`, 32,819 B | `052f6e1321b4fda18a18b885f63320b030a0827d90ac56f67d813bc4f61024ae` |

The original PDF price table (not a scanned image) was read directly and cross-checked with whole NMC 6,807,600 VAT22; the quote per-unit prices are kept in the structured source sidecar. Original draft contract is NOT proof of signed supplier.

### Postgres / GitHub evidence sync

- One **existing** case `223fz:32616339168:lot1` received first-party original EIS evidence `data/market_intelligence/power_quality/original_rosseti_24_bsk_caps_20261028.v37.json`. New canonical notices **0**; no false 24 new equipment sales. Total corpus unchanged **103 notices**.
- Guarded one-case script `scripts/market_intelligence/apply_pq_evidence_v37.py`: before write, official PostgreSQL backup `/Volumes/ArvectumSSD/Arvectum/runtime/data-platform-backups/data-platform-arvectum_data-20261028T044120Z.dump`, **37,475,661 bytes**, SHA256 `633ad00fd5b8fc501c152c63724010dac96ca97f22e81b556eccca9f89bcb11f` verified against file/manifest/companion.
- SQL atomic commit and independent readback PASS: resources **103**, structured records **103**, stable IDs **103**; other non-PQ source resources **2,192** and all documents **2,192** unaffected.
- New target data SHA256 `c5347adc71252f5069bbab75fc7a804d7e4a174cde38c0ef748a96db1a9e2ae8`. The append-only `scripts/market_intelligence/materialize_pq_research_v37.py` regenerates **103/103** source records with **exact content hashes equal to production PostgreSQL**: zero drift.
- Primary evidence-enhanced procurement cases **16**, secondary-only enriched **1**, total enriched **17**. Recorded original registry signed contracts remains **5** and original-company bid occurrences **32**.
- 38/38 source regression tests PASS, including 5 new `tests/test_mi013_pq_v37_rosseti_24_caps.py`: 18/6 split, prices by scope, 1875 preference and no invented award.
- Versioned manifest `verified_public_leads_20261028.v37.manifest.json`, receipt `mi013_production_enrichment_receipt_20261028.v37.json` and retrieval queue `primary_evidence_retrieval_queue_20261028.v19.json`.

**Context and avoid repeated discovery:** Original first-party 2025 MЭС Юга `32515029641` named ООО «ЭСК ЮГ» as intended 12x12kV capacitor supply contractor at **3,490,560 ₽ VAT20** through original 19 Aug 2025 protocol. This information was *already* present in v27; the present v37 new contribution is the **2026 24-item mixed component original specification and separate prices**, not another 2025 company occurrence nor a signed 2025 contract. The 2025 and 2026 Rosseti projects are separate legal EIS notices but common geography and item models require investment-project deduplication when estimating sold volume.

## Next concrete evidence

Seek original **registered signed** RD223 contracts and supplier INNs for 2025 Росseti МЭС Юга `32515029641`, Кузбасский ПМЭС `32514947144`, Bashkirenergo 2026 `32515582393` and Meleuz 2026 `32616296475`. For 2026 24 capacitor procurement `32616339168`, find later signed supplier and actual invoice price, if publicly accessible. Also get original Gazprombank `ГП630876` 10kV UKRM 7z and 2023 Tender.Pro 834269 4×STATCOM technical questionnaire; no manufactured delivery implied.
