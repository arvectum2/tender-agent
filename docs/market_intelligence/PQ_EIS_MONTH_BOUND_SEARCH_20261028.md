# PQ market intelligence — first month-scoped official EIS searches (28 October 2026)

Task: TA-MI-AUTONOMY-20261027. This is a **bounded discovery sample**, not exhaustive EIS/ETP market coverage and not a list of signed contracts.

## Original search execution

Mac mini used the existing official EIS read-only 223-FZ/44-FZ search adapters. All requests used verified HTTPS and exact URL date bounds. The private append-only attempt journal is
`pq-agent-pilot-live/month-eis-search-attempts.json`,
SHA-256 **de7e8a2b229f98538d06fe5b706f8ec7d12136a90190bba471ca9b4cca28b25f**.

Twelve topical first-page searches: months **2024-04, 2025-05, 2026-09** × laws **223-FZ, 44-FZ** × text queries **УКРМ, фильтр гармоник**. All 12 returned a validated official search URL with exact month bounds; four pages yielded 15 *candidate metadata rows* and eight were parsed empty. Two further **exact-number** 44-FZ searches for September 2026 were run and journaled after those twelve. Both matched the original September medical-repair candidate titles, and six further topical 223/44 searches were performed for 2024-10, 2025-11 and 2026-06. The final total is **20 official date-bound requests, 7 nonempty first pages, 18 metadata candidate rows, 13 parsed empty pages**. No page required further pagination according to the adapter, but that is **not proof** of exhaustive source discovery or absence of other PQ procurements.

The official search pages do not establish that results are relevant to the search phrase: five 2025-05 44-FZ results for «фильтр гармоник» and two exact-number 2026-09 44-FZ rechecks visibly concern **medical equipment repair**, not power quality. They are *not* PQ contracts. The April 2024 223-FZ candidate 32413513847 was previously source-reviewed as **0.4 kV**, outside the 6–35 kV target. Other 44-FZ candidate metadata remains unverified, with no original technical specifications or signed contracts recovered in this slice.

## Safeguards and coverage accounting

- Source URL host/path, law flag, search string, calendar boundaries and first page are validated before an attempt is credited as date-bound. All actual attempts are journaled with UTC timestamp, status, candidate ID and publication date when parsed.
- Each result is explicitly query-scoped and first-page only. Original documents, award, signed supplier and contract price are always unverified at this stage. Exact query repeats are blocked for 12 hours; malformed or future-dated journal records fail closed.
- The v29 coverage ledger now records four bounded queries in April 2024, two in October 2024, four in May 2025, two in November 2025, two in June 2026 and six in September 2026. The remaining 28 months have no such query evidence. **All 34 months still lack exhaustive 2024–2026 source coverage.**
- The independent corpus counts remain **101 candidate lot rows; 39 rows with original primary sources; 62 without**. The gap inventory covers 101 leads (38 with locally detectable source files, 32 with review packets; different counting semantics from lot-row coverage).
- The S10 quality gate remains `partial_source_consistent_market_incomplete`, with zero verified signed supplier identities, no defensible market-volume total, and 15 SHA-bound Data Platform extractions blocked pending authorized SDK key. No credential or production change was made.

Runtime artifact SHA-256: `coverage.json` **1e02cb52fa32e9ae1f5c15b974c2405a39c3db1ece94f85875f9c550e469dbba**; `quality_report.json` **930d83abf7bbf10ef730020eda9dbc3ed6c23fa6ade29f93eb924c2fe1673205**.

## Exact continuation

Do not replay these 20 exact month/law/query combinations before the cooldown. Expand genuinely month-scoped official 44/223 and originating ETP searches across the remaining months with source and query semantics audited. For candidate notices, obtain and SHA-verify original technical specifications and protocols before classification. Prioritize signed contract/award evidence for relevant 6–35 kV lots, especially the linked Bashkirenergo UKRM equipment/installation notices 32514720691 and 32514754857. Keep committee offers, NMCK, public registry entries and executed contract amounts separate. Do not merge PRs without queue authority and exact-head CI.

## New independent 2024 official 44-FZ candidate (not added to immutable v29)

October 2024 month-scoped official 44-FZ search identified **0315100006624000089**, published 23 October 2024, titled «Прочая закупка товара (установка компенсации реактивной мощности)». This is a **potential PQ installation lead**, not proof of 6–35 kV equipment, signed supplier or executed price. It is held separately from the immutable 101-row v29 corpus pending original technical specification.

The exact official EIS notice common-info page was fetched with registry number visible, original HTML SHA-256 **0e908d4d1e2826b82c65712f4a2ab97f1444240d9b5c322729979e11341946c4**. The corresponding documents page SHA-256 is **7e2cee8c2d4adcf58ead38284b58aa22ed4d9d9c6535045767f090cd0c136683**. The adapter selected the active 23 October 2024 revision and observed five original filestore attachment links, including «описание объекта закупки.docx» and price justification. Two bounded verified-TLS Python download attempts failed with URLError (direct and default-proxy); a separate curl noproxy attempt returned **HTTP 404** for the exact technical specification link. All attempts and source-page bytes are retained in the private runtime. **No original technical document was downloaded**, and 404 is not evidence that the procurement or contract does not exist. Recheck later under cooldown/alternate official archive access, without synthesizing URLs.
