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
