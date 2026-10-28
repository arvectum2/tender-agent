# PQ market intelligence — first month-scoped official EIS searches (28 October 2026)

Task: TA-MI-AUTONOMY-20261027. This is a **bounded discovery sample**, not exhaustive EIS/ETP market coverage and not a list of signed contracts.

## Original search execution

Mac mini used the existing official EIS read-only 223-FZ/44-FZ search adapters. All requests used verified HTTPS and exact URL date bounds. The private append-only attempt journal is
`pq-agent-pilot-live/month-eis-search-attempts.json`,
SHA-256 **27949492f0bc2727bb11cdc034b46709ed8f1905563e688c134ced00e4d357b5**.

Twelve topical first-page searches: months **2024-04, 2025-05, 2026-09** × laws **223-FZ, 44-FZ** × text queries **УКРМ, фильтр гармоник**. All 12 returned a validated official search URL with exact month bounds; four pages yielded 15 *candidate metadata rows* and eight were parsed empty. Two further **exact-number** 44-FZ searches for September 2026 were run and journaled after those twelve. Both matched the original September medical-repair candidate titles, so the final total is **14 official date-bound requests, 6 nonempty first pages, 17 metadata candidate rows, 8 empty pages**. No page required further pagination according to the adapter, but that is **not proof** of exhaustive source discovery or absence of other PQ procurements.

The official search pages do not establish that results are relevant to the search phrase: five 2025-05 44-FZ results for «фильтр гармоник» and two exact-number 2026-09 44-FZ rechecks visibly concern **medical equipment repair**, not power quality. They are *not* PQ contracts. The April 2024 223-FZ candidate 32413513847 was previously source-reviewed as **0.4 kV**, outside the 6–35 kV target. Other 44-FZ candidate metadata remains unverified, with no original technical specifications or signed contracts recovered in this slice.

## Safeguards and coverage accounting

- Source URL host/path, law flag, search string, calendar boundaries and first page are validated before an attempt is credited as date-bound. All actual attempts are journaled with UTC timestamp, status, candidate ID and publication date when parsed.
- Each result is explicitly query-scoped and first-page only. Original documents, award, signed supplier and contract price are always unverified at this stage. Exact query repeats are blocked for 12 hours; malformed or future-dated journal records fail closed.
- The v29 coverage ledger now records four bounded queries in April 2024, four in May 2025 and six in September 2026. The remaining 31 months have no such query evidence. **All 34 months still lack exhaustive 2024–2026 source coverage.**
- The independent corpus counts remain **101 candidate lot rows; 39 rows with original primary sources; 62 without**. The gap inventory covers 101 leads (38 with locally detectable source files, 32 with review packets; different counting semantics from lot-row coverage).
- The S10 quality gate remains `partial_source_consistent_market_incomplete`, with zero verified signed supplier identities, no defensible market-volume total, and 15 SHA-bound Data Platform extractions blocked pending authorized SDK key. No credential or production change was made.

Runtime artifact SHA-256: `coverage.json` **2238cdb939462d2ee09832df09c33ad56882fff699b622497128b1420332b016**; `quality_report.json` **930d83abf7bbf10ef730020eda9dbc3ed6c23fa6ade29f93eb924c2fe1673205**.

## Exact continuation

Do not replay these 14 exact month/law/query combinations before the cooldown. Expand genuinely month-scoped official 44/223 and originating ETP searches across the remaining months with source and query semantics audited. For candidate notices, obtain and SHA-verify original technical specifications and protocols before classification. Prioritize signed contract/award evidence for relevant 6–35 kV lots, especially the linked Bashkirenergo UKRM equipment/installation notices 32514720691 and 32514754857. Keep committee offers, NMCK, public registry entries and executed contract amounts separate. Do not merge PRs without queue authority and exact-head CI.
