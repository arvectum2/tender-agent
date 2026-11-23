# 2026-11-22 — DTR #679: preserved official HTML and unavailable originals

**Authority:** read-only, filesystem-only bounded local audit, **not a current EIS check**. No network calls, DB queries/writes, source retry, daily replay, document downloads, business GO, procurement submissions, or production deployment. This is an independent local re-check of the 2026-11-21 diagnostic (see `TA_DTR_3_ORIGINAL_GAPS_SOURCE_20261121.md`), not new official source availability evidence.

## Exact offline result on Mac mini

Existing root `/Volumes/ArvectumSSD/Arvectum/data/tenders/eis`, inspected using the repo's existing historical document-revision parser and pinned SHA-256/byte-length receipts:

| 44-FZ register number | Actual files on disk | Independently rechecked | Source-safe disposition |
| --- | ---: | --- | --- |
| `0173100007526000046` | 0 | No locally saved HTML, attachments or original DOCX | `BLOCKED: source_unavailable` — no assertion that live EIS has zero attachments |
| `0128200000126007559` | 0 | No locally saved HTML, attachments or original DOCX | `BLOCKED: source_unavailable` |
| `0128200000126007558` | 2 HTML, 0 DOCX | Two existing 20-Nov first-party HTML bytes match pinned size and full SHA-256. Offline parser selects one **historical** active revision #1 and four unique official source links; zero original DOCX bytes/hashes verified. | `BLOCKED: historical_snapshot_only_original_bytes_unavailable` |

Full raw evidence pins checked in the repository's offline audit:

- Documents HTML: `143222` bytes, `035bcca3adb2855d98e4b31f466d071c10f369aa9ac899e640a10eb8a23cfa26`.
- Common-info HTML: `216571` bytes, `b1deaa5af45932bc984689fc66460674899a7cb349dfc5ad027bed3a470ea379`.

Only the snapshot captured **20 November 2026** was verified. This does **not** prove the active EIS revision, legal stage, attachment inventory or authenticity of downloadable DOCX as of 22 November. No saved DOCX was mistaken for an original. Without active-source evidence, 0 chunks is not an empty-document conclusion, and historical HTML is not admissible as replacement documentation.

## Reproduce safely

From the repo root, with an existing local checkout and its dependencies:

```sh
python scripts/ops/audit_dtr_679_offline.py --source-root /Volumes/ArvectumSSD/Arvectum/data/tenders/eis
```

The command is fixed to **only these three** register numbers, reads existing local files, caps inspection volume, rejects symlinks and SHA/size drift, uses the existing read-only revision parser, and emits only counts/booleans/safe reason codes. It does **not** expose source URLs or raw HTML; it has no network, credentials, database or `--apply` mode. Even a successfully parsed historical revision remains `BLOCKED`. Production runtime/DB remains unchanged by this audit.

## Next admission conditions (issue #679 still BLOCKED)

1. Separately obtain and verify the **current official notice revision and complete attachment inventory**, through a source-authorized bounded single-notice channel (no blind repeats). Historical 20-Nov HTML is not sufficient.
2. Preserve original ZIP/DOCX bytes and receipt hashes/lengths, link to exact official notice and revision. Reconcile the four saved 7558 URLs with the current official inventory; two other notices have no archival source bytes.
3. Re-evaluate source network policy and provenance; confirm resource budget, exclusive source lock, matching release/MI readiness and TA/DP PITR **prewrite** conditions. A healthy point-in-time recovery on 21-Nov is **not** proof of a continuous seven-day PITR horizon; see issue #685.
4. Only after separate owner/AM-4 admission, consider a single controlled dry-run for one notice, inspect resulting DP source-bound chunks/embeddings, and keep failure statuses until real original evidence exists. No autonomous bid/go/deploy.

As of this check, **no source retry is admitted and issue #679 must not be closed**. This document updates evidence and operations only, not the execution queue or paid/production acceptance.
