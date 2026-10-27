# MI-013: bounded ETP secondary-source recovery (2026-10-28)

Source: `https://synapsenet.ru/zakupki/lotonline/chges24621pr--stavropolskij-kraj-postavka-4-chetireh-shtuk-avtomaticheskih` (public mirror, **not** original RAD procurement documentation). Direct verified-TLS HTTP 200, 54,901 original HTML bytes, SHA-256 `d7aff5882ae2cddb613674440572a59293228326f6f09fc7e8a2c14a3c103bd2`; runtime receipt `etp-native-source-attempts.json`, original HTML `etp-native-public-pages/chges24621PR/public-source.html`.

Exact source excerpt: «Поставка 4 (четырех) штук Автоматических регулируемых конденсаторных установок типа УКРМ для комплектных трансформаторных подстанций киоскового типа КТП-630кВА и КТП 400кВА».

Assessment: a **secondary-only candidate** for four capacitor compensation installations associated with kiosk transformer substations and construction-site power. Neither the 6–35 kV installation voltage nor a signed equipment supply, supplier, award, original technical specification, initial price or executed contract amount is established by this mirror. Do not count as confirmed 6–35 kV equipment market volume. The mirror lists three PDF filenames but renders them as `pro-open-form` controls without public attachment URLs; no restricted document was downloaded. Original RAD platform source still needs independent acquisition.

Also attempted `https://zakupki.tochka.com/search/1084879614-3/` for lead `1148520`: direct TLS-verified HTTP 200, but HTML exceeded the 512 KiB source budget (`curl` exit 56); no truncated page was promoted to evidence. Four additional official/mirror probes through Python were logged separately, returning HTTP/transport errors. No winner or contract price was inferred.

`pq_etp_card_audit` now distinguishes HTTP 403, 404, retryable HTTP and transport errors, records retry count and next eligibility, while retaining 12-hour dedup and explicit `signed_contract_verified: false` / `winner_verified: false`.
