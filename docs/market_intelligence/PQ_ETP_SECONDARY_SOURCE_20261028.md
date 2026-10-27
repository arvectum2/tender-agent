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
