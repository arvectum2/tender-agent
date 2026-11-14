# MI-013 — Additional original EIS 223-FZ evidence, 28 October 2026

These four notices are **outside** immutable v20 (100 leads). Public EIS
notice-page attachments are source-bound but not original SOAP revision-bound
evidence or signed contracts. ChatGPT reviewed original text and rendered
scanned pages through ARC; no API/local LLM.

Four new official EIS 223 search terms: `установка компенсации реактивной
мощности` (10 hits), `фильтрокомпенсирующая установка` (3 old hits),
`динамическая компенсация реактивной мощности` (1 already known), and
`СТК 10 кВ` (empty). Journal:
`eis-pq-terms-search-attempts-20261028.json`. A separate direct query
`тиристорный компенсатор` returned four 2014–2019 hits; a noncanonical
direct EIS search URL returned HTTP404, not proof of absent tenders.

Official pages 32514754857, 32515523596, 32515481065 and 32414334005
yielded **15 SHA-verified attachments** (8+1+1+5). Two 32514754857 ZIPs
contained 14 entries; 10 supported child entries were safely staged
(7 unique SHA), four nested 7z entries left opaque. Parent-child receipt SHA:
`ff67f6e0ff99115a63e01634ea5de843c379fc906e149298216898772a9d0dcf`.

## 32514754857 — reconstruction/installation, lot 25-004035

Original EIS public page SHA
`9bbd40e4fc24a6f420b09b1cf2e28c6fd4d77772635e06cc2934b762cadb7111`.
Original final commission protocol, **22 May 2025**, PDF SHA
`eb94ebe8b7019383ffbd4cd7781bca158c97d7a72248e19ca6febc94f17ec24f`:
NMCK **7,030,423.59 RUB ex VAT**; first-ranked **ООО «ТЕХНОПРОМ»**
(97 points), declared commission winner at **6,732,104.09 RUB ex VAT
offer**. Other bidders: ООО «ПромЭлектроМонтаж+», ООО «Электрощит-Уфа».
The protocol says the customer *may* contract with the winner. No signed
contract, executed price, contractual supplier or delivery is verified.

Original OLE technical assignment SHA
`fc8812183a53049268b0fa11b9a696a8dceaf6a686f3bb62ac5a89aae5dbf3bd`.
Textutil line-indexed derived text SHA
`afbc16c2abbfc629ff8c2f82d4cfc55761fb5cb376e5f946484b7fbbd1af0a4f`
states **UKRM rated 6 kV** for PS Andreevka and PS Igrovka, one modular
set per listed site in reconstruction works. This is derived OLE text,
not a native text layer. Accepted ChatGPT/ARC SHA/quote review:
`32514754857-1c80b84dcd3911e2d2f7a08d` — **relevant / mixed EPC**.

Both substations also appear in separate **UKRM supply** lot
25-004033 / EIS **32514720691** (earlier verified 6.3 kV questionnaires).
Preserve separate procurement lots but link shared assets for
**project-level deduplication**. Neither lot's offer is an independently
verified equipment-sale revenue; do not sum them as separate sales.

## Three other original cases

- **32414334005**: original technical PDF SHA
  `f5b14ca8b4fe535746abc671d78e5e69388ea17ea93d6096c843baec406ebe89`
  explicitly requires **0.4 kV** compensation devices in a **6/0.4 kV**
  substation. **Irrelevant** to 6–35 kV target equipment; accepted review
  `32414334005-c854e37a30fdf260211bef9a`.
- **32515481065**: scanned protocol PDF SHA
  `c388c94b673fcbd051426ad0af814ec8fc0ebd8b9087707f2df209f76a7d4ab3`.
  ChatGPT visually verified page 1 (image SHA
  `2d6592360a12fb42fab11881bd32d2670d2375056e311c65e6d30f8ea435b38d`).
  Automatic reactive-power compensation **150 kvar**; **no bids**,
  procurement failed. Equipment voltage unverified: **uncertain**, no sale.
  Review `32515481065-f08cd71ceab9ef5bc4fc1b42`.
- **32515523596**: scanned protocol PDF SHA
  `bf9e6c2f67274b2b10ceaef248a8bdea286d9f138eee327a8985b301f1838382`.
  ChatGPT visually verified pages 1–2 (image SHA
  `95a6545f00764f4792cd75be509b8f8953a0a55804b9329350222ab0c4dfd3c3`,
  `72125ea3e507cf57e8ef52badedaf074d92610ef9a63114657c000b391528355`).
  Sole bid **ООО «РНБ групп»**, **326,990 RUB ex VAT /
  392,388 RUB incl VAT**, labelled winner, but the protocol also
  declares the procedure **unsuccessful due to one bid**. Voltage
  unverified: **uncertain**, not a signed sale.
  Review `32515523596-d0ff3882aedf375bcfbd41e2`.

The last two notices have the same buyer and subject; a reissue is
**possible, not independently established**. Do not count as separate
confirmed sales.

Two real verified-TLS public EIS 223 contract-registry attempts for
32514754857 and 32514720691 returned **HTTP404** (body SHA
`55f7d9e99b8e2d4e0e193b2f0275501e6d9c1ebd29cadbea6a0da48a8587e3e0`).
Journal: `eis-new-lots-contract-registry-attempts-20261028.json`.
This is an inaccessible entrypoint, **not** evidence of absent contracts.

Refreshed immutable v20 gap inventory: 100 leads, 31 with local originals,
31 with reviewed packets; inventory SHA
`13f0187673de4e996bd8e3c7a7a9d9b40d1073c4c4a3e3a3a32a20b224695093`.
ARC queue: **75 reviewed, 1 unreadable pending**. No new independently
verified signed contract, contractual supplier or executed equipment-only
price; no Data Platform ingestion (previous local SDK HTTP401).

Next: recover original contracts/ETP results for the linked 2025 lots,
resolve actual project-level overlap without collapsing distinct notices,
continue new 2024–2026 source acquisition, respect 12-hour ETP cooldown.
