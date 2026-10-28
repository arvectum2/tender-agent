# PQ source recovery — 28 October 2026, 10:32–10:39 MSK

Task `TA-MI-AUTONOMY-20261027`; existing DRAFT PR #519. Machine-readable attempt overlay: `PQ_WATCHDOG_RECOVERY_20261028_1032.json`, SHA-256 `95d6343ce13b79e9fe1b97e8f050d891ba92cc19510ff380821101825bc2ec95`.

## Actual official source attempts

Twelve distinct real network searches: eight EIS 223-FZ and four EIS 44-FZ, with timestamped official-provider statuses in four SHA-verified runtime journals. One 223-FZ search returned four **2014–2019** notices, outside the target 2024–2026 period. The other eleven searches returned empty first-page results. This does not prove absence of procurement or signed contracts. Two additional exact EIS 223-FZ notice-document attempts (`32414337924`, `32615645096`) returned `documents_page_unavailable_or_mismatch`; they are not evidence that the procurement is absent. No new originals were accepted.

Refreshed the immutable 100-row v20 gap inventory against the correct `public223-originals` root: **33** cases with local originals, **31** with reviewed packets. An initial inventory against the unrelated isolated XML root returned zero local documents and was corrected; no source-loss inference was made. Durable ARC queue: **83 reviewed, 5 pending**; four pending source packets repeat already-reviewed SHA or contain empty scanned text, and the fifth has no new native-text extraction suitable for acceptance. No duplicate or OCR-provisional packet was promoted.

Reinspected 23 previously SHA-verified 2024 originals for notice `32413297739`: amendments and commission protocol, but no independently proven rated equipment voltage. The original commission rejected both bids. Earlier 218.81m and later 235m RUB figures are differing NMCK revisions, **not two sales or executed turnover**.

## Code and checks

`pq_source_recovery.py` now accepts optional `--prior-journal` for exact-ID EIS search dedup across real journals, honors cooldown and fails closed on malformed matching timestamps or corrupted journals. `pq_recovery_cycle.py` forwards `--prior-eis-journal`. Four new regression cases cover cross-journal skip, malformed timestamps, corrupt journal, and cycle wiring. **26 focused tests PASS**, Ruff PASS, `git diff --check` PASS; one inherited Starlette warning.

No signed contract, contractual supplier or executed equipment-only price newly verified. Data Platform synthetic SDK HTTP 401 remains unresolved; no ingestion attempted. No local LLM, OpenAI API, procurement submission, signature, company outreach, payment or production mutation.

**Resume:** verify exact-head CI; preserve all four attempt journals and their SHA; continue source-bound signed-contract/winner/price and technical-specification recovery for relevant 6–35 kV cases (notably linked `32514720691` and `32514754857`). Supply prior real journals when running exact-ID search, honor ETP 12-hour cooldown, do not repeat verified SHA reviews. Keep PR #519 DRAFT/REVIEW and the single Watchdog unchanged; no auto-merge absent queue `auto_merge:true` and current Company authority.
