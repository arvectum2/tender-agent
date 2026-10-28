# MI-013 — Additional official EIS 223-FZ evidence, 2026-10-28

These four notice IDs are **separate from immutable v20 (100 records)**.
Public notice-page files are weaker than original SOAP-XML revision-bound
attachments. None proves a signed contract or completed supply.

Six real official EIS 223-FZ searches at 06:38–06:39 MSK: compound
`ЧиркейГЭСстрой УКРМ`, `Суходол СТАТКОМ`, `УКРМ 6 кВ`
returned empty; single-term `СТАТКОМ`, `УКРМ`, `фильтр гармоник`
returned candidates. The `СТАТКОМ` results included irrelevant
`остатк` substrings, so lexical search alone is not qualification.
Journal: `eis-alias-search-attempts-20261028.json`;
SHA-256 `ca2d9abc4a4e1210f0a8b905f33b09e142c8e35d81f395d2aaa9964b73a1f887`.

Four public EIS notice pages were fetched with actual GUIDs and
SHA-256 receipts, and 16 attachment files were downloaded:

| Notice | Page SHA-256 | Files | Evidence |
|---|---|---:|---|
| 32615773152 | bed8b3e775579cf6675814e75cc47530243b6d539909eb7221eb8772e3cc5161 | 2 | Generic sole-supplier procurement rules, not technical proof |
| 32615696503 | abcd20a7fe03004c27e9278517573f68c9706e9a9c1869d68701e4bfc0a8826d | 2 | Identical DOC bytes to preceding notice |
| 32514720691 | 8a8668c0d24bf96e70977a0d1ec1a6a8d192d1553986648c2f0bca1c2382a2e9 | 8 of 17 | Original UKRM notice, commission and precontract protocols |
| 32413513847 | b3c2323e2803369b4dbfd787daf765d5309176f968e503ca655ed5e3994c54eb | 4 of 4 | Original active filter 300 A, 400 V |

The repeated generic DOC SHA is
`e1a4324ac459491d318f6eac265c4154431188c960ffd724b8550172de6f70d8`.
Some `.doc` files are actually HTML. Never infer original native
format from the extension. Seven source ZIPs were expanded with the
existing bounded SHA-verifying extractor: 38 unique members indexed,
35 staged, zero extraction errors.

## Exact source findings, reviewed via ChatGPT and ARC

**32514720691 / lot 25-004033, 2025.** Notice DOCX SHA
`3d0d49334115e57084bae654dbfa83cf92c79720a08a4e6fb6c12b23e174a099`:
“Поставка установок конденсаторных УКРМ для ПО НЭС ООО
«Башкирэнерго»”; two sets; NMCK **27,318,000 RUB excluding VAT**.
Commission protocol of 5 June 2025, PDF SHA
`225a5149205a542ff2f56751f55b8a7f411ac5a54f18620345434e22fb9ba926`:
“Итоговая цена коммерческого предложения составляет: 14 790 000
руб. без НДС”. The commission recommended sole compliant bidder
ООО «ТД «УК Конденсатор» for negotiations after the tender failed.
Precontract protocol of 9 June 2025, PDF SHA
`3bd1ec6f103ce779b2ea93c1db35ee3116b8d7b8fc10b02cc557e32396405126`:
the offer remained unchanged. **Neither a signed contract nor a
verified supplier under that contract is established.** Scanned
questionnaires for PS Andreevka and PS Igrovka have no native text;
6–35 kV remains unverified. ChatGPT review: **uncertain**.
Keep offer, NMCK and actual contract price distinct.

**32413513847, 2024.** Official DOCX SHA
`030f06ed799a02f20db9b1980fab1f35eb0616c605d2bcbfd6d229ffe563bd49`:
“фильтра активного гармоник 300А, 400В для УТС Н-И ТЭЦ”.
**400 V / 0.4 kV is outside 6–35 kV.** ChatGPT review:
**irrelevant**; exclude from target market.

Accepted ARC queue IDs:
`32514720691-b443cec594311db0ae525720`,
`32413513847-74b886d2aeba15fe685a61ba`.
Review queue: 69 reviewed, one old unreadable pending.
100-row v20 inventory unchanged: 31 local-original and 31 reviewed cases.
No new signed contracts, independently verified suppliers or executed
contract prices; no production Data Platform write.

All original bytes, page/ZIP/member SHA receipts, journal and accepted
reviews are retained under
`/Volumes/ArvectumSSD/Arvectum/runtime/market-intelligence/pq-agent-pilot-live`.
Next: find signed contract for 2025 lot, verify voltage visually from
scanned questionnaires, retrieve remaining nine 2025 links within
a separate bounded slice, preserve ETP 12h cooldown and avoid replaying
33 prior exact EIS searches. PR #519 remains DRAFT/REVIEW.
