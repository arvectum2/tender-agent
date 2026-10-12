# Independent R5 source verification — 2026-10-12

Task: TDP-R5-INDEPENDENT-20261012. This is an independent machine evidence
audit by the assistant. **NOT independent human-owner acceptance**, legal
assessment or assertion of current auction status.

## Source hierarchy (read-only)

1. Fresh authenticated official EIS getDocsByReestrNumber SOAP for 20 exact
   procurement IDs, 2026-10-12 05:14:35–05:14:53 UTC, official ZIP SHA256
   separately recomputed. 17 succeeded, 3 returned no_data; all 17 official
   ZIP SHA256 matched the independently downloaded previous archive snapshot.
2. Parsed original official ZIP XML (not prior summaries) by matching
   epNotification... element and exact purchaseNumber, with direct-child
   versionNumber only. Never confuse a nested versionNumber with the notice
   revision. 17/17 original notice receipt SHA256 matched official ZIP bytes.
   96/96 historical XML original byte hashes were found in fresh official
   ZIP members.
3. Independently read the original 168 stored files **as bytes** in authorized
   non-production tender-agent Docker volume; recomputed SHA256 and byte
   length against 2026-10-09 immutable receipts. 168/168 match; zero
   missing and zero mismatched. 20 metadata records and nine report files
   existed. 8 saved recommendations say manual_review_required; one case
   `0162300005826000156` carries historical participate_conditionally
   without independent publication version attestation. The main software
   PR #361 blocks unsafe reuse; it does not retroactively rewrite originals.
4. For the 72 non-XML attachments, the original UID from metadata
   independently occurs in official notice XML: 72/72. Attempted
   HTTPS/certificate-verified re-download of 72 official filestore URLs;
   no new binary SHA256 match established. The probe reported {'official_http_404': 24, 'download_unavailable': 48};
   a sampled request also returned HTTP 429 (rate limiting), so further
   repeated requests were intentionally avoided. These 72 cached original
   binaries are integrity-verified but **NOT freshly source-byte reverified
   from the official filestore**.

## New independently discovered stale original notice receipts

| Public registry ID | Historic XML → highest archived revision | Highest archive endDT | Max price (RUB) |
|---|---|---|---|
| `0158300034526000388` | v1 → v5 | 2026-10-12T08:00:00+03:00 | 152033.33 |
| `0348100024426000039` | v1 → v3 | 2026-10-19T10:00:00+03:00 | 1245000.00 |
| `0360600005326000018` | v1 → v2 | 2026-04-06T10:00:00+04:00 | 2700000 |

The machine review previously flagged only the first two. The source-receipt
SHA256 check found **three**. Their latest archived version is not proof of
the current live published version or award/cancellation/availability.

## Explicit unresolved cases

- SOAP no_data: 0348100024426000052, 0148300050426000047, 0318200087026000163.
  This does NOT prove the procurement does not exist.
- All 20 cases need dated independent human owner signoff for GO/NO_GO/DEFER.
  Current signed count: **0/20**.
- Further commercial fitness, all required attachments, signing terms,
  bidder criteria, participation eligibility and final law compliance have
  not been independently accepted. Do not manufacture GO.
- Production Data Platform's persisted original identity parity remains
  unverified (separate R2 gate). No production API/database mutation occurred.
- No bids, digital signatures, submissions, deployments or migrations performed.

## Reproduce and source evidence

- Script: scripts/acceptance/audit_r5_official_sources.py
- Tests: tests/test_r5_independent_official_sources.py
- Export: docs/acceptance/TDP_R5_INDEPENDENT_20_CASES_2026-10-12.csv
- All 168 files: docs/acceptance/TDP_R5_INDEPENDENT_168_FILES_2026-10-12.csv
- Private raw proof Mac mini: /Volumes/ArvectumSSD/Arvectum/evidence/tdp-r5/independent-20261012/
  (fresh official ZIPs, read-only transport log, original cached byte SHA
  review, 72 UID/curl probe and reconciled JSON). These private originals
  are not committed or uploaded to a public Git repository.
