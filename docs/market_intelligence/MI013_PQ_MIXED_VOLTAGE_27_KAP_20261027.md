# MI-013 Power Quality — 27 units BUT only 1 medium-voltage capacitor (original ЕИС lot) — 27.10.2026

## Existing procurement №32616474682, AО «БЭСК», lot №27-000090 (published Oct 2026)

Full [original EIS ZIP archive](https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/file.html?uid=BA786DC8B0DA40A0BB27D80D1C38BC38) SHA256 `44adb9865dd71b666d5481782816907ba8968b5b7c1c4acc49426c335c3316a7` (2,886,312 bytes). 9 subfiles: 3 original questionnaire PDFs, original DOC technical specification, original signed-stage **template** Excel price form, contract templates for 2 buyers and solicitation documents. The 27 units in tender title include **mixed 0.66, 1.05 and 11.55 kV components**.

Source `Приложение №2 Ценовое предложение.xlsx`, **original worksheet rows 12–15**, directly read (price cells are blank because this is a tender bid template, not an awarded offer):

| Model from original source | Qty | Unit voltage | Nameplate each | Recipient | Delivery 2027 | Scope |
| --- | ---: | ---: | ---: | --- | --- | --- |
| КЭП2-0,66-80-2У1 | **11** (1+10) | **0.66 kV** | 80 kvar | ООО «БСК», PS Aksakovo | 1 Mar + 1 Apr | **OUT** (low voltage) |
| КЭП2-1,05-120-2У1 | **15** | **1.05 kV** | 120 kvar | ПО ОЭС / ООО «Башкирэнерго», Oktyabrsky | 30 Sep | **OUT** (low voltage) |
| КЭПФ-11,55-430 2УХЛ1 | **1** | **11.55 kV** | 430 kvar | ПО ОЭС / ООО «Башкирэнерго», Oktyabrsky | 30 Sep | **IN** 6–35 kV |

**Strict 6–35 kV: 1 unit at 11.55 kV**, not 27. Site name and procuring organisation do not imply 6–35 kV for all 27 components.

Original `Приложение №1 ТЗ для ТМЦ.doc`, SHA256 `3e24adc4a5366a1afe6afac4533b24b4ad0d35309e25486b98f6c6ec71881dd6` (59,904 bytes), confirms **NMC 2,452,650.41 RUB without VAT for the ENTIRE 27-unit procurement**, warranty ≥60 months from operation and ≥66 months after warehouse arrival; payment 45 calendar days after delivery for non-SME and 7 business days after signed acceptance for SME. Original `№27-000090 Закупочная документация` signed 15 Oct 2026; submissions 16–27 October 2026; commission result scheduled by **3 December 2026**. So neither winner, contracted price nor completed supply is knowable as of 27 Oct 2026.

**Do not assign 2.45m ₽ to one 11.55 kV capacitor**; there is no line-item price in the original template. Future 2027 delivery likewise must not be counted as 2026 revenues.

Correction recorded as `data/market_intelligence/power_quality/original_2027_condenser_mixed_voltage_bom_20261027.v28.json`. This is one **existing** ledger entry enriched, so 101→101; 71 PostgreSQL +30 Git-only unchanged; first-party signed RD223 total remains five.

## Consequences for FGI/Arvectum market methodology

- **Always read original price sheet line-by-line**, not aggregate tender quantities by guessed voltage. Example case 27 total components, only one 11.55 kV.
- A 500 kV **substation location** is not the component 500kV voltage: two other 2025 tenders carry 12 kV KЭПФ capacitors.
- Accumulate manufacturer/proposer graph separately by original committee legal name and external registry INN; two Russian `УК Конденсатор` entities must not be merged. See `supplier_legal_entity_ukkz_20261027.v27.json`.
- Equipment *bid* price != registered *signed* contract != *paid* amount; original tender price including 26 LV components is not strict medium-voltage TAM.

Original data and sources from previous phase: `primary_filter_capacitors_and_ukrm_20261027.v27.json` and `docs/market_intelligence/MI013_PQ_12KV_FILTER_CAPACITORS_6KV_UKRM_20261027.md`.
