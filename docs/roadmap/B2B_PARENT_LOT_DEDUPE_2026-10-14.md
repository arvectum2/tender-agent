# B2B first-party parent/lot identity and false positives — 14 October 2026

Read-only direct Russian Mac mini/no-proxy official HTML verification at **00:26 Moscow**, receipts in [machine evidence](b2b_parent_lot_original_audit_2026-10-14.json). All three original URLs returned HTTP 200; **this does not establish bidder eligibility or access to full documents**.

- [B2B-Center lot-card #4632699](https://www.b2b-center.ru/market/otbor-dlia-uchastiia-v-konkursakh-na-razrabotku-i-redizain-brend-saitov/tender-4632699/) (59,762 bytes, SHA-256 `01edb692...`): source heading explicitly identifies **lot №1 of prequalification procedure №4632682**, from АО «Логика молока». Historical pool already includes procedure **#4632682**. Therefore page/card 4632699 is **not** a new unique procurement procedure. Parent identity is useful for dedupe; lot remains a distinct sub-record for future technical analysis. Platform displays active status, but actual eligibility/contract and detailed participation requirements are not verified.
- [B2B-Center #4616411](https://www.b2b-center.ru/market/tender-na-uslugi-razrabotki-saita-transportno-servisnoi-kompanii-v/tender-4616411/) (72,968 bytes, SHA-256 `f4713282...`): original public page identifies ООО «ТК «Мираторг», **archive status**, deadline 9 October 18:08 Moscow including final short extension. Do not revive from search results.
- [Rosatom RTS #4638345](https://www.rosatom.rts-tender.ru/market/vypolnenie-rabot-po-razrabotke-i-adaptatsii-baz-dannykh/tender-4638345/) (52,395 bytes, SHA-256 `5d1b0b43...`): original page explicitly classifies as **market price monitoring** for highly specialized industrial/nuclear SAKOR-491 software, even though displaying an active status and 22 October 23:59 time. This is not proof of an actionable development procurement.

## Engineering control

The offline source-byte parser derives a **procedure grouping key**, *only* after SHA-256 integrity check and visible original-page explicit procedure reference. Catalogue, aggregator, unknown, conflicting or tampered evidence returns `REVIEW_REQUIRED` without a grouping key. A parent-lot relationship does not confer legal or competitive suitability; independent lots can remain separate analysis records under one parent procedure.

**Counts:** 11 historical distinct source-attested corporate IT/digital procedure cards remain the currently documented research baseline; **not 11 verified live and eligible software orders**. The target **15–20 simultaneously current, qualified corporate IT procurements remains OPEN**. Zero added in this verification pass. No account login, ETP, payment, signature, contact, production or merge.

## Независимая проверка родительской карточки

[Оригинальная процедура №4632682 на B2B-Center](https://www.b2b-center.ru/market/otbor-dlia-uchastiia-v-konkursakh-na-sozdanie-i-redizain-brend-saitov/tender-4632682/) открылась напрямую с российского Mac mini: **HTTP 200**, **64 714 байт**, SHA-256 `4af001503f0725b6b99464043bee984ec8026e817330808aec866bbe9d2d1d04`, проверка **14.10.2026 00:34:39 МСК**. Страница прямо показывает родительский отбор №4632682, один лот, заказчика АО «Логика молока», статус «активно» и дату окончания **14.10.2026 16:00 МСК**. Это срез публичной страницы, а не подтверждение права подачи. Условия участия доступны зарегистрированным пользователям и полностью не проверены.

Отдельная офлайн-проверка реальных байтов родительской страницы дала `DIRECT_PROCEDURE_CONFIRMED / b2b-center:4632682`; для уже сохранённой страницы лота №4632699 ранее получено `PARENT_LOT_CONFIRMED / b2b-center:4632682`. **Обе страницы относятся к одной процедуре**, а потому не увеличивают количество уникальных тендеров. Лот может оставаться отдельным объектом анализа. `bid_ready=false` для обоих.
