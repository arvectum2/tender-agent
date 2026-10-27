# MI-013: bounded ETP secondary-source recovery (2026-10-28)

Source: `https://synapsenet.ru/zakupki/lotonline/chges24621pr--stavropolskij-kraj-postavka-4-chetireh-shtuk-avtomaticheskih` (public mirror, **not** original RAD procurement documentation). Direct verified-TLS HTTP 200, 54,901 original HTML bytes, SHA-256 `d7aff5882ae2cddb613674440572a59293228326f6f09fc7e8a2c14a3c103bd2`; runtime receipt `etp-native-source-attempts.json`, original HTML `etp-native-public-pages/chges24621PR/public-source.html`.

Exact source excerpt: «Поставка 4 (четырех) штук Автоматических регулируемых конденсаторных установок типа УКРМ для комплектных трансформаторных подстанций киоскового типа КТП-630кВА и КТП 400кВА».

Assessment: a **secondary-only candidate** for four capacitor compensation installations associated with kiosk transformer substations and construction-site power. Neither the 6–35 kV installation voltage nor a signed equipment supply, supplier, award, original technical specification, initial price or executed contract amount is established by this mirror. Do not count as confirmed 6–35 kV equipment market volume. The mirror lists three PDF filenames but renders them as `pro-open-form` controls without public attachment URLs; no restricted document was downloaded. Original RAD platform source still needs independent acquisition.

Also attempted `https://zakupki.tochka.com/search/1084879614-3/` for lead `1148520`: direct TLS-verified HTTP 200, but HTML exceeded the 512 KiB source budget (`curl` exit 56); no truncated page was promoted to evidence. Four additional official/mirror probes through Python were logged separately, returning HTTP/transport errors. No winner or contract price was inferred.

`pq_etp_card_audit` now distinguishes HTTP 403, 404, retryable HTTP and transport errors, records retry count and next eligibility, while retaining 12-hour dedup and explicit `signed_contract_verified: false` / `winner_verified: false`.

## Three additional B2B-Center 10 kV candidates (secondary source only)

The following source pages were retrieved with exact original HTML bytes using direct TLS-verified GET (HTTP 200) and no login, and the quoted source fragments were checked against the SHA-bound files. These are **not** native B2B-Center technical documents or signed awards:

| Secondary procedure | SHA-256 of public HTML | Exact equipment quote | Provisional source quantity |
| --- | --- | --- | --- |
| `4561228` | `e57d2f6b0d8b02f31662815ae3d2984f1cd85a0efd29cb889ad73c58fbc2d220` | «Конденсаторная установка 10 кВ АУКРМ (УК1, УК2)» | 2 шт. |
| `4561243` | `654fecab5dd900cb5c0dddd055c08c5678d681439fc1e375ccb613ff84db0322` | «Конденсаторная установка 10 кВ АУКРМ (УК3, УК4)» | 2 шт. |
| `4565274` | `85380726233389d57a6fceb798ee57db01534420374f129d66720e0ffc9d4332` | «Конденсаторная установка 10 кВ АУКРМ (УК1, УК2)» | 2 шт. |

All three pages name the Mikhailovsky GOK / Metalloinvest purchasing context. Procedure `4565274` explicitly says «взамен конкурса № 4538400», **not** `4561228`. Because `4561228` and `4565274` describe the same УК1/УК2 equipment family, their project/lot relationship remains unresolved; **do not count their quantities as separate realized purchases**. The УК3/УК4 label is a separate candidate scope, not a verified separate contract. Secondary pages do not disclose original signed suppliers, executed contract prices, reliable NMCK or source-native technical attachments. Exact source URLs and SHA are stored in `data/market_intelligence/power_quality/etp_secondary_candidate_receipts_20261028.json`; the downloaded HTML remains in the private MI runtime and must be source-reverified before downstream promotion.

## Additional source schemas recovered and two more candidate pages

`pq_gap_recovery` previously read only the `evidence` list. The immutable 100-row v20 corpus also uses `sources`, `source_url`, `source`, and `supporting_source`. As a result, **32 of 100 leads had no URL in the generated gap inventory despite URLs in the source deltas**. The bounded fix retains exact source URLs in deterministic order, deduplicates them, and rejects non-HTTP(S) and credential-bearing URLs; this does not authorize their retrieval or change source provenance. On re-inventory: **100/100 leads have at least one discovery URL** (not 100 original notices), 48 have local source files, 30 have reviewed packets. Exact-source ETP probe queue increased from 28 to 38 candidates. This is a discovery coverage correction, **not** market coverage or signed-contract evidence.

Two more SHA-verified secondary pages were downloaded and exact quoted text checked:

* `4559984`, HTML SHA-256 `ada4603533dc44ef864c7defd498b790b8b16e0e3914878ed5557fe8b2e3e07d`: «Автоматическая установка компенсации реактивной мощности АУКРМ - 6,3 - 1350 - 450 - 12 УХЛ4». Source indicates one candidate 6.3 kV compensation component inside a **mixed materials price-sounding request** for PS 35/6 kV. This is not a standalone contract or executed sale; no supplier or signed price verified. Do not infer Mvar solely from model string.
* `231994-2`, HTML SHA-256 `19645ca3cff5ddf1e517201b9898ba1e47bd4d5e33b44b1e5db332d0c42cd899`: «№ 231994-2 ДОПОЛНЕНИЕ. РД. ПС-352 Система динамической компенсации реактивной мощности». Source is a **working-design/documentation candidate**, not a verified SVC/STATCOM supply. The substation label ПС-352 does not establish 35 kV voltage. Native original technical ZIP and award remain unrecovered.

First-party UDS corporate archive could not be acquired: TLS verification failed (`curl` exit 60, verify result 18), and a second verified-TLS path failed likewise; **no `-k`/insecure fallback**. A separate corporate PDF on recko.ru returned HTTP 403, so no original was promoted. All attempts and failure types remain in `etp-native-source-attempts.json`.

## Three further SHA-bound secondary-source classifications

* `4302914` — SHA-256 `8aa28af24df79f7a5425256eea51b04c84a336ee693d523f1d1030f6e02878e6`; exact quote «Техническое обслуживание оборудования конденсаторной установки «СТАТКОМ RU-DRIVE SVG 6,3/5-3 МВар»». A potentially useful **installed-base/maintenance** signal for 6.3 kV STATCOM equipment at Lebedinsky GOK, **not** a new STATCOM sale or equipment procurement outcome.
* `COM20082600016` — SHA-256 `a6d4a6e1942e00c3db8ba007e39f210e1038a2466a71380e81e70cf6378efa77`; exact quote «Поставка установки компенсации реактивной мощности (УКРМ)». Lukoil-West Siberia commercial **request for price information**, source shows a technical questionnaire name `ОЛ.3 УКРМ` but the original is not retrieved. Voltage, award and contract amount UNKNOWN.
* `1351/ОАЭ-ЦДКС/26` — SHA-256 `0550b97178f64f662334a4c5143e22fd36f01e253fe304b6ea42f9c90f924305`; exact quote «выполнения строительно-монтажных работ по устройству вторых питаний устройств компенсации реактивной мощности». This is **second power-feed construction for existing compensation devices**, not an equipment-only supply. The secondary page reports a starting budget, but without original notice it is not promoted as verified NMCK or contract price.

All three public HTML bytes were acquired over verified TLS and remain in the runtime source receipt journal. No original attachments or signed supplier/contract outcome was acquired. Do not aggregate these as equipment sales.

## Original scanned EIS commission protocol — 32616280467 (visual review, OCR provisional)

The SHA-verified original EIS PDF `02-76.pdf` (5 pages, **SHA-256 `5c161c4cffcef27e525e47896b55e1adeacee4d26fcf903fec36c95db21b20b1`**) was rendered page-by-page and **visually read by ChatGPT**. Original native text extraction contained only form feeds; bounded Russian OCR was used strictly as a derived transcription aid. A new **separate** OCR-provisional packet `32616280467-2c28b41f95ccecad34e79229` was accepted via ARC with the original PDF SHA, OCR transcript SHA, source quotes and `ocr_requires_visual_verification: true`. The unreadable native-text packet remains unchanged.

* Page 1: original commission protocol for `ПИР. Переустройство ВЛ-10 кВ Артскважина в части установки системы динамической компенсации реактивной мощности (1 шт.)` — project/design works involving compensation, **not evidence of equipment-only supply**.
* Page 2: initial maximum contract price **3,683,790.00 RUB including VAT 22%**; two submitted proposals. This is the protocol's stated initial price, **not** signed contract price.
* Pages 3–4: the commission ranks **ООО «Электриксервис»** first and **ООО «Энергосвязьсервис»** second. First-ranked offer **3,680,106.21 RUB including VAT 22%**. Exact OCR excerpts bound to the original PDF SHA include «первое место, а именно: ООО «Электриксервис»» and «3 680 106,21»; OCR renders the initial price as «3683 790,00 руб. с учетом», while the visual page has a space after the initial `3`.
* Page 4–5: the protocol calls for a contract to be concluded after publication. **No signed contract, final supplier identity, executed price or delivery was verified.** The signatures visible are on the commission protocol, not a contract.

Structured, explicitly **non-promoted** visual/OCR candidate: `data/market_intelligence/power_quality/ocr_provisional_commission_32616280467.json`. The original public-source receipt is preserved under `pq-official-reestr/32616280467/download_receipt.json`. Do not add the 3.68 million RUB project/design proposal to equipment-only market totals or count it as a signed contract. Existing canonical commission-facts list was **not** mutated; further source/acceptance review is required before promotion.

## Gap-inventory correction and last native document reviewed

A second inventory defect was found and regression-tested: leads with **no `procedure_id`** previously evaluated `source_root / ""`, accidentally counting unrelated root-level `canonical-manifest.json` and `source-manifest.json` as that lead's original documents. This inflated local-document coverage **48/100**. The fixed inventory now correctly reports **31/100 with case-specific local source files**, **31/100 with at least one reviewed source packet**, **100/100 with a discovery URL**, and **zero locally sourced cases without a review**. These are known-lead coverage figures, **not** a complete market census or signed contract counts.

The remaining case `32616435269` had a 15 KiB source file named `.doc` but identified by `file` as Microsoft Word 2007+ OOXML. A read-only `.docx` extension alias retained the exact original SHA-256 `5ee0e7926be6beeb372f659a39baf97521f89cbcef539f8f77bc4a1a0116c948`. ChatGPT reviewed the source-bound packet `32616435269-79fb73cc7c5df67568e811b3` as **uncertain**: the only text is «После утверждения и согласования будут внесены изменения в конкурсную документацию.» It does not establish PQ equipment, contract outcomes or signed prices. Original file remains untouched.

At checkpoint: **52 reviewed source-bound packets**, one unreadable native PDF packet preserved (with its separate reviewed OCR-provisional packet), four non-state JSON files in the queue folder, and no held cooperative lease. The verified public source HTML journal contains 12 bounded direct attempts, nine SHA-verified public HTML pages, one HTTP 403, one TLS trust failure and one oversized page; none is a signed contract.
