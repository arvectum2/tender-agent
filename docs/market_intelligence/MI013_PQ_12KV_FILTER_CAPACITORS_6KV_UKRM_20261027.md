# MI-013 Power Quality — 12 kV filter capacitors and 6 kV complete UKRM, primary source pass (2026-10-27)

**Canonical**: v26 101 source notice records → v27 **101**; 3 *already existing* records enriched; production PostgreSQL 71, Git-only 30, verified first-party RD223 signed contracts **5** unchanged. These are original commission **offers and selected participants**, NOT verified signed sales or delivery amounts. Source-grade structured evidence: `data/market_intelligence/power_quality/primary_filter_capacitors_and_ukrm_20261027.v27.json`.

## №32514947144 / Rossseti Kuzbass PMES — 14 units 12kV 450kvar harmonic filter capacitors

[Original technical task DOCX](https://zakupki.gov.ru/223/purchase/public/download/download.html?id=103365127) (SHA256 `5aee81a7a8dc65d4314ba718ab7621293ca3d708448958fd22c1cd5bdeb2f94c`). Emergency spare stock, delivery PS 500kV Novo-Anzherskaya. Component *nominal voltage* **12kV**, **14×450kvar**, model `КЭПФ-12-450-2 УХЛ1`, each capacitance 9.95µF, or technically compatible equivalent. The fact substation is 500kV does **NOT** mean these are 500kV capacitor units. Nameplate component sum **6.3Mvar** does not measure installed filter bank size.

[Original final commission protocol of 04.07.2025](https://zakupki.gov.ru/223/purchase/public/download/download.html?id=103806743) SHA256 `1f3cde0fa95d5187b707e978108553894dea2c1377ca0123b5a3d7b08a113fd8`: three conforming companies, original NMC **3,186,960 RUB including 20% VAT**. Winner **ООО «ТД «Усть-Каменогорский конденсатор»**, offered **3,158,400 RUB inc VAT** (≈225,600 RUB/unit proposal); ООО «Алмаз Инжиниринг» **3,179,988 RUB**, second place; ООО «ТД «Сибэнерго»**3,186,960 RUB**, third place. Committee ordered the buyer to sign after statutory waiting period, but actual original RD223 registered signature, amount, manufacturer and delivered units **not independently verified**.

## №32515029641 / Rosseti MES South — 12 units same model 12kV 450kvar

[Original July 18 protocol](https://zakupki.gov.ru/223/purchase/public/download/download.html?id=104750727), SHA256 `e4e5a46396842c35f7cbf2b26844c2614ab5c3213f91ed27e1e978f44c10437a`, first-stage committee found only one compliant bidder. **Source discrepancy:** early heading says 7 bids, actual list contains 3; later official [19 August final protocol](https://zakupki.gov.ru/223/purchase/public/download/download.html?id=104750729) (SHA256 `b3571212f38a646f3686d30974ce3a4fd6df904e2a5b22a1cd51c3b9363ed0c6`) unequivocally identifies **3**, 1 admitted, 2 rejected. Do not add four invented participants.

Original technical chapter in [EIS RAR archive](https://zakupki.gov.ru/223/purchase/public/download/download.html?id=103949308), SHA256 `821667469efbadd92ad3196c3ecadce12578df23087ee907d84383e2972e40e9`, technical inner DOCX SHA256 `e8a7ff6662469ca0685c1bfc656158ac70424376fefc89ecbc59b876542623c6`: **12×450kvar**, nominal **12kV**, `КЭПФ-12-450-2УХЛ1`, **5.4 Mvar** nominal sum, 9.95µF, **−60…+45°C**, specific weld/pressed terminal and original enclosure height **950mm** plus terminals **1190mm**, prior use qualification from Rosseti under Order №305 from 26.07.2023. Deliver to Pyatigorsk.

Initial NMC **3,621,456 RUB incl VAT20**. Original named bidders: **ООО «ЭСК ЮГ»** admitted, bid **3,490,560 RUB incl VAT**, two rejected: ООО «РегионИнжиниринг» (900mm vs required 950mm body, 1160mm vs 1190mm full height, other technical conflicts); ООО «ГК Армада» (missing structured technical characteristics form). The *July* commission had not yet approved certain signing, whereas **19 August** commission ordered to conclude with ЭСК ЮГ at **3,490,560 RUB** (≈290,880 RUB/unit as offer, includes VAT). No original signed contract, delivery, or OEM name verified.

**Commercial insight:** 14+12 = **26 different units requested by two buyers**, same 12kV/450kvar part family; total component nameplate 11.7 Mvar, **NOT verified installed filter capacity**. Two bid-price unit benchmarks must not be generalized to whole Russian market or STATCOM/Mvar pricing. Original technical rejection exemplifies exact dimension/compliance barriers.

## №32515582393 / Bashkirenergo NЭС Nagornaya PS35kV — complete stepped UKRM

[Original tender document ZIP](https://zakupki.gov.ru/223/purchase/public/download/download.html?id=107793261) SHA256 `97e9a248467ffe91efb33cecfc069b29afb14feabbd3562a13b28253ce58d1f0`; contains scanned original 25pp `Опросной лист 4257 на УКРМ ПС Нагорная.pdf` SHA256 `48ceaa3f94c353f638dbab29951d3ec6dd5b32e79114fa0641800831715333a9`. **First page visually checked**, states: `УКРМ56-6,3-200-(1×50+2×75) М4.5S`, **rated nominal 6kV**, **200kvar**, three stages **50+75+75kvar**, **50Hz**, RS-485, `Сириус-БСК`, Novar regulator. Substation is PS35kV Nagornaya but the equipment is **6kV**.

[Original two committee protocols in EIS ZIP](https://zakupki.gov.ru/223/purchase/public/download/download.html?id=108626473), archive SHA256 `842cfe42c4ad5f797cf6d4d104015406ea43d246ecc8c1cf60364861ea69ffae`:
- 12.02.2026 original selection protocol `2026.ЗК-000577/02`, selected **ООО «УК КОНДЕНСАТОР»** as sole qualifying bidder, **4,900,000 RUB EX VAT**; commission initiated sole source process.
- 16.02.2026 negotiation protocol `2026.ЗК-000577/03`, supplier gave lower offer **4,850,000 RUB EX VAT**. 7 business days payment after delivery/inward control; warranty ≥60 months from commissioning and ≥66 months from warehouse receiving.
- Original RD223 signed supplier and price **not proven**. Negotiated proposal is *not* a paid sale. 200kvar stepped system price is **not** a valid unit-price benchmark for active medium-voltage FGI STATCOM absent functionality/scope matching.

## UKKZ manufacturer channel and legal-name collision (2026)

Legal-source adjacency verified from [Kazakh state supplier register](https://procurement.gov.kz/ru/registry/show_supplier/80179), factory [own product catalog](https://ukkz.com/ru/) and Russian independently listed legal records. Legal identities must NOT be merged:

| Role | Legal entity | Identifier |
| --- | --- | --- |
| Manufacturer based in Kazakhstan | ТОО «Усть-Каменогорский конденсаторный завод» | BIN **921240000477** |
| Active Russian trading house; original 2025 Kuzbass protocol named this full trade-house name | ООО «ТД «УК конденсатор» / «Торговый дом «Усть-Каменогорский конденсатор» | INN **7719766728**, OGRN 5107746012809 |
| Other active Russian firm, same address, 2026 Bashkirenergo source uses generic ООО «УК КОНДЕНСАТОР» (INN not on protocol) | ООО «Усть-Каменогорский конденсатор» | INN **7719863288**, OGRN 5137746153694; **probable match, not first-party identity** |
| Old name collision, legal entity ceased | ООО «УК КОНДЕНСАТОР» historic | INN **5029064895** (liquidated) |

2025 Kuzbass company INN externally corroborated by [RBC company registry](https://companies.rbc.ru/id/5107746012809-ooo-obschestvo-s-ogranichennoj-otvetstvennostyu-torgovyij-dom-ust-kamenogorskij-kondensator/). Alternate 2013 legal entity verified by [b2b.house](https://b2b.house/company/OOO-UK-KONDENSATOR_226bfc07-d2c6-4f35-b88c-2c5368d5d684/), **do NOT automatically assign its INN to UKRM 32515582393** from name only. Both active entities share a Moscow street and CEO at some points; this does not imply one common bid. The Kazakhstan factory own website lists a Russian `ТД УК Конденсатор` channel, but manufacturer's offered-product brochures do not prove the exact OEM identity of the 2025 shipment.

[Factory's STATCOM catalogue](https://ukkz.com/ru/catalog/novinka-staticheskij-generator-reaktivnoj-mosh-nosti-statcom.html) describes 6.6/10/11kV implementations and [SVC line](https://ukkz.com/ru/catalog/staticheskie-tiristornye-kompensatory-reaktivnoj-moshchnosti.html) generally 10–35kV; [active harmonic filters](https://ukkz.com/ru/catalog/aktivnye-filtry-garmonik.html) appear in catalog too. Thus UKKZ is an **FGI-functional portfolio competitor** and should be included in competitor technical comparison (with a caveat that own marketing specs alone do not verify certifications, Russian field experience or particular tender awards). **Do not assume equipment is 100% Kazakh manufactured merely from sales material**.

Entity-source sidecar: `data/market_intelligence/power_quality/supplier_legal_entity_ukkz_20261027.v27.json`.

## Version and next work

Previous v26 101 procurement signals → **v27 101**, +3 existing primary-sourced procedure dossiers, **0 added source notices**; 71 PostgreSQL, 30 GitHub-only; 5 first-party registered signed contracts unchanged. Named participant-source *appearances* 21→28 (3+3+1), NOT unique suppliers or number of winning contracts.

Priority: original signed RD223 for the 3 new direct equipment procurement records, plus Meleuz original signed supplier, Rosseti NTC two related signed frame agreements, NOVATEK GП630876 source attachments and 2024 coverage. Never add all NMC or prices of failed tenders to total market estimate.
