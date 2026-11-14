# Parallel GEH / small-procurement source discovery — 2026-11-14

Eight bounded HTTP probes concurrent with the SIBUR capture: six HTTP 200, two TEK-Torg section redirect loops. Official Mosenergo procurement page directs readers to EIS and ETP GPB, but returned a table with header only; no claim of no demand. Official ETP GPB search at https://etpgpb.ru/procedures/ returned SSR HTML with 20 distinct cards: 13 etp, three gos, three price_request, one etp_click. All have raw price observations; 17 have customer field. Internal ETP numeric IDs and official gos UUIDs are distinct source namespaces. Thirteen cards display 15 November 2026 publication dates (later than capture date); retain raw observation for review rather than active status, canonical exact date, legal or GEH attribution. No working DB import of this sample, and no claim that these 20 generic results are GEH purchases.

TEK-Torg public market/223 pages returned HTTP 307 redirect loops, while https://kim.tektorg.ru/ loads the storefront shell. Moscow supplier portal returns an SPA shell; EAT public landing response is an intermediate loading page, not purchase sessions. Existing EAT/Moscow parsers are available; actual list/detail contracts and item-level data remain to verify. Do not treat HTTP 200 shell as data acquisition or invent API paths. Raw source receipts and normalized GPB preview are in private runtime, not Git.

Next: establish owner/customer filters using the public UI and official primary detail links, verify source dates, then source-separated ingestion of target GEH purchases. Resolve authorized public list acquisition for small-procurement platforms and distinguish goods, units, price, delivery and actual outcomes before economics.

## Target detail follow-up

Two first-party historical details returned HTTP 200 and were byte-hashed. Notice 32414196205, published 14.11.2024, 7,407,342 RUB: survey works for 275 MW units at CHPP-25/26. Notice 32414239479, published 25.11.2024, 1,267,200 RUB: functional logic diagrams for protection and automation terminals at HPP-1 boiler modernization. Both show archive status and source text supports Mosenergoproekt and GEH Zakupki. Actual award, supplier and target-filter contract remain unverified. Keep customer, organizer and project owner separate. Raw receipts retained privately.

## Verified GEH group capture and working DB seed

Primary detail pages link official GEH Zakupki and Mosenergoproekt catalogs. Official menu exposes section=geh_group. All 16 advertised accepting pages (313 unique observations), plus 32/400 completed pages (640 observations) replayed. Separate update date fixed parsing defect; 92 conflicting temporal observations quarantined. 861 rows imported as etp_gpb (223 accepting date-consistent, 638 completed date-consistent, 496 prices present); repeat inserted zero. Publication range 2026-05-27 to 2026-11-13. No complete historical coverage or winner claim. System Python trusted TLS succeeds; no verification bypass. Private originals and receipts retained.

## Historical registry expansion

192/400 history pages and 16/16 active pages verified, 4,153 observations, 4,053 source-scoped DB rows (223 accepting, 3,830 completed, 2,445 prices present), 100 quarantined observations. Publication dates 2026-05-12 to 2026-11-13. Replay inserted zero. Ten priority detail snapshots confirm source numbers; nine expose attachment labels, but no direct verified attachment links. Status on six details is accepting; four are supplier review. Do not infer awards. Continue historical pages from 193, resolve document links and review observations.

## Full advertised history and public attachments

400 historical and 16 active pages, 8313 observations, 8206 validated rows (223 active by list/date, 7983 completed), 4871 prices present, 107 review observations. Publication range 2025-11-24 to 2026-11-13; not a complete two-year archive. 1225 lexical candidates. Exact published anchors on ten primary detail pages yield 24 links to etp.gpb.ru LotDocuments/PriceOrderDocument. Four original PDF/DOCX/XLSX captured, SHA-replayed against detail/list provenance and linked to two existing procedures. Repeat import inserted zero. Archives remain unexecuted. No award claim.

## Active priority details and attachment provenance

All 19 active lexical candidates verified on primary details: 14 accepting, 5 supplier review. 45 explicit download links and two complaint labels whose destination is merely the platform root. 14 captured URLs, 13 unique tender/SHA links in TA across six procedures; 14 archive downloads disconnected, 17 links unattempted. Raw archives remain unexecuted and multipart completeness unverified. Monotonic provenance reconciliation preserves both links for identical content; replay inserted zero. Historical pilot: 17/20 primary details accepted; three parser failures remain; 14 buyer review, one expired, one order preparation, one archived. Completed list filter is not an award result. 15 focused tests and Ruff passed.

## Historical protocol pilot

All 3 earlier parser failures resolved by allowlisting the published Protocols path and deduplicating identical anchors (conflicting labels rejected). 50 historic details, 63 published links, 22 protocol links and 22 downloaded ZIP originals. Safe bounded in-memory DOCX parsing found 8 explicit best-bid decisions (5 distinct anonymous platform IDs); 14 protocols require different wording/structure review. No inferred supplier legal identity or signed contract amount. 23 historical original links inserted and replayed with zero new rows; GPB now has 36 document links. Structured decisions retained privately as protocol-decisions-v2.json with source SHA, member SHA, paragraph and exact source excerpt, not yet written as structured DB facts.

## Structured protocol decision persistence

80 historical details, 124 published links, 45 protocol source receipts and 46 historical document links. The expanded parser handles longest explicit decision clauses, marketing research and group leaders, with tax basis preserved. All 22 prior protocols parsed; 40 of 45 total yield explicit decisions (37 participant, 3 leader, 19 distinct anonymous IDs). Five remaining reviews include one invalid ZIP, one alternate decision wording and three unsupported ZIP member configurations. Structured facts are source-bound document JSON metadata, not a new award table; exact original/member hashes and paragraph excerpts retained, no legal identity or signed contract inferred. 23 additional document links, 40 decision updates, repeat zero inserts/updates. GPB total 59 links; SIBUR 713.

## Additional outcome types and direct DOCX

110 historical details, 59 captured protocols, 58 source-bound persisted outcomes: 55 best bids and 3 unsuccessful procedures. Two MOEK local ordinal participants are explicitly not platform-wide identities; 21 distinct global IDs among other decisions. Direct DOCX supported independently of ZIP containers; one scanned PDF etp:1293269 lacks text layer and requires separate OCR. 60 historical links, 73 GPB links total. Repeat wrote zero.

Completed remaining eight published protocols for 110 historical details. 67/67 captured, 65 outcomes persisted (62 best bids, 3 unsuccessful), 23 distinct global IDs; two local ordinals excluded from participant aggregation. Two reviews remain (PDF scan and alternate clause). 81 GPB links; repeat zero inserts/updates.

## Protocol batch 5

140 historical details, all 95 published protocols captured, 93 source-bound outcomes (89 best bids, 4 unsuccessful). 31 distinct platform IDs, 109 GPB DB links. Explicit total bid distinguished from unit-rate sum when both are published; prior 65 decisions replay unchanged. Two reviews remain (scanned PDF and alternate decision). Repeat writes zero.
