# PQ Watchdog evidence recovery — 2026-10-28 12:42:31 Europe/Moscow

Task: `TA-MI-AUTONOMY-20261027`; existing PR #519 remains DRAFT/REVIEW. This is a bounded source-attempt and inventory correction, not a market census.

## Deterministic coverage correction

Refreshed the immutable **100-row MI-013 v20** gap inventory with all three actual original roots (public223, SHA-verified EIS, primary ETP). The pre-fix inventory counted **33** local case directories, but **two** (`32615966040`, `32616400421`) contained only `public-page-receipt.json`. A retrieval receipt is not an original technical specification or contract. Updated `pq_gap_recovery.py` to exclude known receipt/manifest filenames and checksum sidecars from `source_documents_local`, with an offline regression test. Corrected case-level document-presence count: **31**; independently reviewed case count: **31**. Presence alone is not evidence of a signed contract. Pre-fix inventory SHA: `7dec0f1525d9d467f896eeeb6fb926ce82e7cd43f7e45d2bf76f67f80c40416b`.

## Real new source attempts

Six previously unattempted terms were searched through the official EIS 223-FZ provider, with a durable journal SHA `318f273efb664696adcee5f73fcd849b446becbd89692be504fbdc583883f737`. Five returned empty first pages; `управляемая конденсаторная установка` returned eight 2013–2014 procedures, outside the 2024–2026 period. An empty first page does not prove no tender/contract.

Eight prior retryable ETP card URLs became eligible after 12 hours and were **actually re-fetched** using the allowlisted verified-TLS audit (not an inventory-only pass): three secondary HTML pages HTTP 200 with exact byte SHA snapshots; two HTTP 200 responses exceeded the safe body budget and were not treated as complete; three HTTP 403 inaccessible. Retry journals SHA: `2fa9336175fecb22861cf00ea19a22ece3a6f6b0091fbf10213f12506d2e5d4e` and `6f7e007c96401ff8cf9700bbb5e53f21ac8106a7b3d04a7f4e369f4c7c6cadae`.

The SHA-verified secondary `ГП630876` page (SHA `f55a64b322592ad5f1005afe39e88cad6e919849d1b511fd10641a284a52e40e`) names modernization of a **10 kV** reactive-power compensation installation and lists technical requirements/7z filenames. It is **secondary discovery only**: original ETP attachments, winner, signed contract and final price remain unverified. Two other SHA snapshots: `32515582393` UKRM supply secondary listing (`a383223312f594a7c61f71e80fd6856d5bdb98a7c3fef5c7a53761070d875bd7`), `5747901` drilling-rig UKRM modernization secondary listing (`ae705447dce4b42d182ed44b1ae5e03ef58674c8da5d736dfd87cc01e41f01a6`). No page was promoted to an official signed award.

ARC `pq_arc_chat next`: no readable pending packet; **three** previously pending native PDFs remain unreadable, requiring visual original verification. **85** reviews already accepted; none duplicated. No Data Platform ingest (prior SDK HTTP 401), production mutation, procurement submission or external company action.

## Gates and exact resume

Previous exact-head PR #519 CI for `070b1f13` was SUCCESS. This run changed the PR head and requires fresh exact-head CI. No automatic merge: MI queue auto_merge admission not established, PR remains DRAFT/REVIEW and Company AM-4 merge authority not revalidated. Preserve the unrelated `.agent/current-task.yaml` and the single Watchdog.

Next: verify new exact-head CI; retrieve original technical specifications, commission protocols and signed-contract evidence for relevant `32514720691` / `32514754857`; check `32514842313` bank voltage; try the primary GPB ETP attachments for `ГП630876` without guessing download URLs or bypassing access. Preserve SHA, 12h ETP cooldown, exact-ID EIS dedup and source-tier separation. Never infer supplier/contract price from NMCK, secondary HTML or commission selection.

## Post-fix validation

Reran the corrected real 100-row v20 inventory on Mac mini with three original roots: **31 cases with local source files and 31 with reviewed packets**. Corrected inventory SHA-256: `824f2dc23dc7f1d88ef22c5637217ba946533e49bcefa791b0634d6707892237`. Focused regression and evidence-recovery suite: **17 PASS**, Ruff PASS, git diff check PASS; one inherited Starlette warning. The branch was fast-forwarded without overwriting unrelated work.
