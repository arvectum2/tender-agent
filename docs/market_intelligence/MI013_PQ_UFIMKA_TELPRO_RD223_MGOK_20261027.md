# MI-013 PQ: Ufimka original contract + equipment and MGOK dedupe — 27.10.2026 (v24)

## Original commission and signed contract: Bashkirenergo / PS Ufimka 10kV BSK

Procedure **32514476448**, 04.02.2025, ООО «Башкирские распределительные электрические сети», INN0277071467, modernization ПС 35/10кВ Уфимка, planned **2×0.9Mvar BSK 10kV** (not a verified manufacturer equipment delivery by itself).

| Metric | Verified fact | Provenance / limitations |
|---|---|---|
| Initial max | **3,176,527.55 RUB excluding VAT** | Original commission [PDF](https://zakupki.gov.ru/223/purchase/public/download/download.html?id=100970521) |
| Commission decision 06.03.2025 | Failed single-bid procedure; sole conforming bid assigned contract negotiation | Original PDF SHA256 `6aad26d79ae29136cca5214b44f2aae9fdd4fe45dd0cd3f8ab2fe0e74d524554`, 179843 bytes |
| Name of admitted / selected bidder | **ООО «Уральская электроинженерная компания ТЭЛПРО»** | Original PDF, not manufacturer by default |
| INN corroboration | **6670226212**, short name ООО «ТЭЛПРО-УРАЛ» | External official [SRO member record](https://www.sro-mri.ru/reestr/v/2841), also [company-owned copy of regulator registration](https://telpro-ural.ru/upload/iblock/c28/tnwhulyfc8qnt3i8rfbb7eupspzjrau8.pdf). INN **not directly printed in original protocol** |
| Sole conforming participant final bid | **2,922,405.35 RUB excluding VAT** | Commission PDF |
| Machine EIS proposal representation | **3,506,886.42 RUB including VAT** | [Original EIS HTML protocol](https://zakupki.gov.ru/223/purchase/public/download/download.html?id=100970523), SHA256 `973bad52e54604c62f353c391c9cd42723d663f39e76997d3eb8a9cff751014d`. This is same bid ×1.20, NOT second offer. |
| Registered signed contract | **№50277071467250001900000**, customer contract **РЭС-1.16.7/Д-01408**, signed **26.03.2025** | [First-party EIS open public contract card](https://zakupki.gov.ru/epz/contractfz223/card/contract-info.html?reestrNumber=50277071467250001900000), SHA256 `8162f01dee6578dfa1255724dfa2ed93428d937df8b8ffb70d7d108c831ba05b`, 136186 bytes |
| Official signed contract price | **2,922,405.35 RUB** | EIS public card (does **not** separately specify VAT basis). Not equipment price |
| Original registered execution status | **Исполнение завершено** | EIS same card; registered execution period 02.06–30.12.2025; does not itself document amount PAID |
| Actual 10kV BSK manufacturer and hardware value | **Unknown** | Avoid adding turnkey EPC price to standalone power-quality equipment turnover |
| Signed registry supplier legal name | **Not visible in public card** | Original protocol provides selected bidder, but independently unredacted signed counterparty is not proven |
| Guarantee / works settlement | 36 months; payment within 7 working days following agreed КС-2/КС-3 | Original commission PDF |

This corrects v19 secondary-only `source_corrections` without losing history. One verified additional **signed public original registered contract** takes corpus tally from 4 to **5** (different notice, no repeated revision). One additional **named primary protocol bidder occurrence** takes count 4→5. Final buyer/EPC statement remains separate from OEM, invoices and delivered goods.

## MGOK: verified published repetitions, no false additions

Three original existing commercial corpus cards: **4561228**, **4561243**, **4565274**; their ancestors **4538400** also mentioned in index and v7 source evidence. The buyer/project is Mikhailovsky GOK MGBZh:
- `MGOK-MGBZH-UK1-UK2`: 4538400 (earlier generic UKRM), 4561228 (13.08.2026; 2 systems `УК1, УК2`), 4565274 (17.08.2026; expressly “взамен конкурса 4538400”, same `УК1, УК2`). **One possible underlying pair**, not 3 ×2 sold.
- `MGOK-MGBZH-UK3-UK4`: 4561243 (13.08.2026; distinct labels `УК3, УК4`, 2 units). **Another pair**; no sale confirmed.

Reference procurement listings: [4561228](https://zakupki.kontur.ru/4561228_4), [4561243](https://zakupki.kontur.ru/4561243_4), [4565274](https://synapsenet.ru/zakupki/b2b/4565274--kurskaya-obl-zakupka-kondensatornoj-ustanovki-10-kv-aukrm-uk1-uk2-dlya). All **secondary** replications, original B2B protocol/winner not retrieved. Scope: 2 distinct intended pairs totaling up to **four different 10kV systems requested**, *not proof of four supplied systems or of price*.

## Existing case GP630876: secondary-only bill enrichment

[ETP GPB index via Synaps](https://synapsenet.ru/zakupki/gazprombank/%D0%B3%D0%BF630876%231344734--leningradskaya-obl-postavka-oborudovaniya-s): NOVATEK-UST-LUGA, INN4707026057, 2026 retrofit of existing 10 kV UKRM, not new full STATCOM project. Listed: 3 reactors per 450kvar step, 4 per 300kvar step, 1 per 150kvar step, 3 vacuum 400A 10.5kV contactors, 1 KEPZ-10.5-150-3U2 capacitor, fuses and wiring. Because originals `Модернизация УКРМ.7z`, `Заводская документация.7z`, `Технические требования.xlsx` are not obtained, do **not** sum these reactor nominal ratings as power of new 10kV bank; no winning contractor or price verified.

## Version and statistical invariants

`v23→v24`: 101→101 active source notices; no new procurement announced in this pass. `v24`: 101 source notices; 71 verified in PostgreSQL, 30 Git-only; primary signed registry cases 4→**5**; named original-protocol bidder occurrences 4→**5**. **No newly confirmed stand-alone PQ equipment sale or new hardware price.** Original-source checksums are in `original_bsk_contractor_contract_20261027.v24.json`.

Continue queued: signed original RD223 for Rossseti NTC component frameworks 32515218366 and 32616355390 (contract ceilings are not delivered components), Meleuz 32616296475 signed-counterparty identity, NOVATEK GP630876 original doc archive, MGOK exact contract awards, and sparse 2024 regional source days. Never replace previously verified v3-v23 evidence; run all changes append-only in canonical branch; production DB remains read-only pending independently scoped import.
