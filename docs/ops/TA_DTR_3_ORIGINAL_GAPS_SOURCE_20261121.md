# 2026-11-21 official-source diagnosis — three DTR missing-original cases

Read-only/official-source follow-up to [issue #679](https://github.com/arvectum2/tender-agent/issues/679). **No DTR rerun, database writes, Data Platform writes, bids, GO decisions or fabricated original bytes.** Production remains immutable backend release `9b650a2b818032389cfd6e13799acad33c72089b`, PostgreSQL revision 127. WSF-07B's separate 12-record original grant was not extended to DTR.

| 44-FZ notice | Actual Nov20 retained evidence | Nov21 result | Current safe disposition |
| --- | --- | --- | --- |
| `0173100007526000046` | 0 original-document DB records, 0 chunks, no linked raw source HTML; EIS detail read timeout; SOAP source not found in DTR | No verified first-party current revision or attachment inventory | `WAITING_HUMAN / SOURCE_UNAVAILABLE`; do not infer zero attachments in real EIS |
| `0128200000126007559` | 0 documents/0 chunks, no linked source HTML; detail read timeout; SOAP not found in DTR | Same unverified source inventory | `WAITING_HUMAN / SOURCE_UNAVAILABLE` |
| `0128200000126007558` | 4 official DOCX URLs registered, all timed out; 0 saved original DOCX bytes/hash, 0 chunks | Fresh public EIS detail GET timed out; official getDocsIP **one** successful exact SOAP response returned HTTPS archive URL on 21 Nov 12:39 UTC, but later 12s and 25s bounded attempts timed out before the archive could be downloaded. No ZIP saved | `WAITING_HUMAN / ORIGINAL_BYTES_UNAVAILABLE`, archived revision evidence only |

## 7558 independent archived primary-source verification

The production DB links two actual saved first-party `zakupki.gov.ru` HTML files, captured 2026-11-20 10:15 UTC. Read-only file size and full SHA256 equality with their database receipts were checked, not inferred from titles:

- Official common-info HTML: **216571 bytes**, SHA256 `b1deaa5af45932bc984689fc66460674899a7cb349dfc5ad027bed3a470ea379`.
- Official documents HTML: **143222 bytes**, SHA256 `035bcca3adb2855d98e4b31f466d071c10f369aa9ac899e640a10eb8a23cfa26`.

Production offline revision parser on those exact saved document HTML bytes sees **one active revision #1** as observed then, published 19 Nov 2026 15:28 MSK, and exactly four attachment URLs; the four URLs match the four registered DB source-document URLs as a set. This is a **historical Nov20 snapshot**, not a current Nov21 legal/procurement status verification, not a current active revision proof, and not actual DOCX originals.

## Recovery limits and next admission

EIS public homepage HEAD 200 while exact `ea20/common-info` HEAD 404; HEAD method/edge does not establish legal cancellation or 404 for GET. Official individual `int.zakupki.gov.ru` SOAP getDocsIP can succeed but is transient; do not run a broad/continuous retry loop. The new private `/Volumes/ArvectumSSD/Arvectum/private/tender-agent/dtr-source-originals-20261121/fetch-one-official.py` limits a future owner-scoped single-number retrieval to the authorized official HTTPS compound archive host and an 8-MB bound; it **has not obtained or saved** any ZIP. No private URLs/tokens or raw document bytes in Git.

When upstream becomes stable: one separately admitted exact-number current revision proof, unique original ZIP/XML and filestore URLs, bounded original bytes verified by SHA/length, then source admission, immutable preservation, MI lock, TA/DP PITR prewrite and independently reviewed narrowly scoped projection. Never mark `MANAGER_READY` from a failed download or from historical HTML alone.

## Backup observation

Read-only TA+DP recovery proofs and WAL receivers PASS at 2026-11-21 12:43 UTC. The visible independently restorable base directories begin **2026-11-20** (TA 3, DP 4), so continuous seven-day PITR history is **NOT PROVEN**. Current healthy recovery points are useful, but must not be presented as verified 7-day retention. The complete window will require independently retained base+contiguous WAL evidence spanning seven days, or an older independently verified backup plus all WAL segments; no archival pruning or fabricated history.
