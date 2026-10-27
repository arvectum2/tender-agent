# MI-013 · Power Quality Russia · Primary EPC/project designers pass (27 October 2026)

Canonical corpus = **v26, 101 source notices**; **71 PostgreSQL** and **30 GitHub-only**, unchanged. Total 5 original public signed RD223 contracts independently verified in earlier phases; **no additional signed original contract identified in this pass**. Source SHA and item-by-item facts: `data/market_intelligence/power_quality/primary_stk_skrm_designer_competition_20261027.v26.json`; preceding original BOQ: `original_nikitskaya_epc_protocol_boq_20261027.v25.json`.

## 1. 2025, № 32515225588: project replacement of 3 SVC/СТК at PS Slavyanskaya / Afipskaya 220 kV

Original [EIS commission protocol 3/3614155 of 30.10.2025](https://zakupki.gov.ru/223/purchase/public/download/download.html?id=106305968), **46100 bytes, SHA256 `6d81b62143fd3523fbe172d2c62feb612e5b9cd1953fe12549c793600f3e4424`**, read as DOCX.

NMC: **27,175,270.00 ₽ including 20% VAT**. Four original conforming applications, no rejections; retender negotiation/rebidding 23.10.2025. Final protocol ranked:

| Outcome | Project firm | Offer after rebid with VAT | Firm INN verification |
| --- | --- | ---: | --- |
| **Winner**, rank 1 | **ООО «ПЦ СИБИРИ»** | **20,107,269.94 ₽**, 20% VAT | **5402574460**, self-published on [pcsib.com](https://www.pcsib.com/) |
| Runner-up rank 2 | ООО «ТЭП» | 17,793,360.90 ₽, company VAT **5%** under USN | Not verified; do not infer INN from ambiguous short name |
| Rank 3 | ООО «МОДЭНС ГРУПП» | 25,758,834.00 ₽, 20% VAT | **7724417137**, [bank registry](https://www.tbank.ru/business/contractor/legal/1177746851006/) |
| Rank 4 | ООО ПЦ «ЭКРА» | 27,175,270.00 ₽, 20% VAT | **2130110311**, [own published details](https://www.pc-ekra.ru/kontaktyi-i-rekvizityi) |

**Important**: Lowest *VAT-included* price does NOT necessarily win the multi-factor tender; EIS commission explicitly ranked proposals by weighted price **and** relevant project experience. The contest winner is the *design firm* PC Sibiri, not an established OEM supplier of 3 compensators. Public RD223 signed contract not independently retrieved; no manufactured PQ equipment price.

## 2. 2026, № 32616354211: Tyazhinskaya 52 Mvar SKRM design consortium

Original [EIS RAR](https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/file.html?uid=DA341AB568084928B96A457AD02938D4) 668627 bytes, SHA256 `5ebf2889ecca1fe28dfbdf90ffe2b4a187aa75511c4b5ae8511f4a2fef1fcf2e`, embedded RTF 140552 bytes SHA256 `4169c08123d77454829d1ec304241d1d9cfd7d96e734c478e6da413279d20d20`.

Customer АО «ЭСК Сибири», 18.09.2026 protocol **№ 26-5011/32616354211/4**. Project: engineering survey and adjustment of design for 110/35/10 kV PS Tyazhinskaya, replacement of existing BSK-110 with 52 Mvar SKRM. Specific rated voltage of *new SKRM* NOT established; substation bus voltages are not device nameplate.

One legal collective bid:

| Company in primary original source | INN | Consortium role |
| --- | --- | --- |
| ООО «СВЭТ-ПРОЕКТ» | 2465200905 | **Leader** |
| ООО «СИБЭЛЕКТРОПРОЕКТ» | 2465189948 | Member |
| ООО «ВЕКТОР» | 5402052777 | Member |
| ООО «АСК «Барс» | 3812057503 | Member |

NMC **6,163,644.34 ₽ without VAT**, equivalently **7,519,646.09 ₽ including VAT 22%**. Collective bid **6,071,189.67 ₽ without VAT**; equivalently **7,406,851.40 ₽ including VAT**. Sole application, tender legally failed, commission requested conclude contract with consortium. **No original signed RD223 contract located** and zero PQ hardware purchased per this design-stage evidence.

## 3. 2025, № 32514944142: earlier related but failed Kirillovskaya + Slavyanskaya + Afipskaya STK design competition

Original [EIS protocol №2/3514049](https://zakupki.gov.ru/223/purchase/public/download/download.html?id=103756668), 23355 bytes, SHA256 `769552aa0bad2d7b96dbcd64d886b80ad7d5c796b42efecd3fb36d3cd569c1d6`. A second indexed EIS file ID 103756742 is binary-identical (same SHA), *not a new protocol*.

Budget: **18,668,690.00 ₽ with VAT**. Seven original applicant company names:
- ООО «АЭСП» — rejected, incomplete proposal documents.
- ООО «УРАЛПРОЕКТИНЖИНИРИНГ» — rejected, absent technical proposal.
- ООО «ПРОФЭНЕРГО» — rejected, exceeds approved price ceiling.
- ООО «ЭНЕРГЕТИЧЕСКОЕ СТРОИТЕЛЬСТВО» — rejected, exceeds ceiling.
- ООО «КПЭИ» — rejected, exceeds ceiling.
- ООО «ЛЭМ» — rejected, exceeds ceiling / deadline.
- АО «РОССЕТИ НАУЧНО-ТЕХНИЧЕСКИЙ ЦЕНТР» — only admitted applicant.

Commission declared procedure failed with only one admitted and advised new procurement *if necessary*. **No winner/contract confirmed** for this earlier competition.

**Data-quality note:** header says signed/published **02.07.2026**, while procedure/meeting in body says June–July **2025**. Record both, do not silently “correct” original. The later October 2025 design competition **32515225588** overlaps in Slavyanskaya/Afipskaya, but omits Kirillovskaya and still says three STK. Label as *partially overlapping investment/design program*, not three distinct sold compensators.

## 4. Nikitskaya existing EPC case № 32615966040 source-level correction

Original [EIS final RAR](https://zakupki.gov.ru/223/purchase/public/download/download.html?id=110931276), SHA `86a6d2605f575465feebfb5cb84eae1d90f7f4ed56bd178588061dc200273744`; first-party commission chose **ООО «ЭНЕРГОСЕТЬ»**, exact-address-match **ИНН 5001061220** from the company's group and [legal records](https://companies.rbc.ru/id/1075001001580-ooo-energoset/). NMC in earlier admission protocol **5,564,090.57 ₽** incl VAT 22%, revised NMC/final sole bidder **5,273,763.77 ₽** incl VAT 22%. This is a *changed initial estimate* across document editions, not a 5.2% competitive discount.

Original EIS [engineering/BOQ archive](https://zakupki.gov.ru/223/purchase/public/download/download.html?id=110412149), SHA `0d1b4730cf2ce43237c79ad7175063a528a40e611a6d8c2caa50264e346f42e3`, original inner single-page contractor supply list SHA `0d659868ec0aed8b33d6e815d548c892c7ff984dca4803f969db696d409455da`, read from actual rendered scan. Contractor-supplied equipment and materials **2,948,531.63 ₽ excluding 20% VAT** (earlier worksheet basis): of which four types of *current transformers (incl zero-sequence), withdrawable 10 kV vacuum switchgear elements, active/reactive meters* **2,888,306.62 ₽** and minor wiring etc **60,225.01 ₽**. **NO explicitly itemised UKRM/SVG/STATCOM/BSK** in this specific contractor list. Do not invent equipment count or apply original 20% VAT to final 22% 2026 contract. Separately, official source text mentions measures to compensate reactive power at switchgear 10kV, so classify as **PQ-adjacent / mixed EPC, unproven discrete PQ device**, not a definite standalone 6–35kV OEM opportunity.

## 5. NOVATEK two procedures: not independent verified PQ supplies

[ГП628666, 12.04.2026](https://energybase.ru/tender/019d85e1-073d-7222-8421-390b2fbaae67) on existing 10kV UKRM retrofit reported as **cancelled**. Later [ГП630876, 22.06.2026](https://synapsenet.ru/zakupki/gazprombank/%D0%B3%D0%BF630876%231344734--leningradskaya-obl-postavka-oborudovaniya-s) same customer and subject plus overlapping file names; probable replacement/republication. Source is public secondary commercial cards; no original ETGPB contracts. Cancelled earlier notice **not appended as separately active physical demand**, linked as excluded precursor. Supplier, delivery and price unknown.

## Version control and business relevance

- Base **v24 101** public-source procurement announcements → **v25 101** with original Nikitskaya and cancelled GП628666 predecessor → **v26 101** with three additional previously existing STK/SKRM project-designer/protocol cases.
- **21 original-protocol legal-company appearances** total in the progressive narrow set, **NOT 21 distinct company winners**: v25 already had 6, this pass named 4+4+7=15 further participant occurrences. Many are losers/rejected. Five primary confirmed registered signed contracts unchanged, equipment-only signed value remains unproven.
- Business development: `PC Sibiri`, `SVET-Proekt` consortium members and `MODENS Grupp`, `PC EKRA` are verifiable potential *design/EPC counterparties*. This is a role map, not an OEM ranking or national manufacturer shares.
- Next: original registered signed RD223 contracts for winning designs; exact 52 Mvar replacement voltage, commercial ETGPB archived GП630876 and 2024 archival PQ. Keep source-driven 6–35 kV strict subset separate from adjacent 110/220 kV procurement and unverified PQ in EPC.

Machine-readable source append: `primary_stk_skrm_designer_competition_20261027.v26.json`. All original source files archived externally or linked + SHA, not committed in binary to repo.
