# SIBUR historical archive and working exact-ID diff — 22 November 2026

Task TA-SIBUR-HIST-GAP-READONLY-20261122; issue #692. This is a reproducible read-only audit, NOT a current open tender list or import authority.

## Independent original and working ID evidence

- Replayed all 4,052 of 4,052 saved first-party SIBUR archive pages in nine categories. Every original source URL, page number, original byte SHA256, source pagination, original row ID and category aggregate member SHA matched saved receipts. No new network access.
- Historical 48,536 source observations = 48,332 unique exact external IDs and 204 duplicated observations.
- Working DB is arvectum_local on separate PostgreSQL16 research cluster system_identifier 7694400479046774822 (NOT production arvectum PG17). One repeatable-read read-only SQL transaction reverified 30,632 exact source=sibur_public IDs with exact original saved snapshot hash.
- Overlap: 30,081; historical archive IDs missing from working: 18,251; working-only IDs not in the nine archive categories: 551. Exact full archive ID SHA256, missing-IDs SHA256 and working ID SHA256 matched independently saved 21-Nov proofs.

| Category | Historical IDs absent from working |
| --- | ---: |
| 107 | 2,035 |
| 108 | 4,883 |
| 109 | 1,008 |
| 112 | 3,925 |
| 132 | 3,891 |
| 999_08 | 653 |
| 999_10 | 803 |
| 999_11 | 994 |
| 999_19 | 59 |
| Total | **18,251** |

Source-only CLI: scripts/research/audit_sibur_archived_working_id_gap.py
requires explicit absolute paths to already saved private and SHA-pinned receipts. Optional with-working-db-readonly uses only fixed PG16 local research container, read-only SQL and create-once private 0600 proof. No ID lists, source content, credentials or private proof bytes are committed.

SHA256 archive receipt: 07c4ce310b28dec397aa927f9cbcbfaeb6d9374017038c03c2a59a0af25c7f0d
SHA256 older ID-gap receipt: 069a8ce4fd0b6d74b6f3866df3116b9019c5cf0b13f1c45a198c76d2efd81085
SHA256 new independently verified private proof: 4dae9e36df79dbbf678fab5264a4e60de378d71fd391e8b7d7e71280e39151a8

## Issue #692 still OPEN

The 18,251 exact missing IDs are a CONFIRMED HISTORICAL archive-vs-working discrepancy, not proof of 18,251 currently open, compliant, useful or economically attractive tenders. Root cause of the 18,251 absent IDs and 551 working-only IDs is UNKNOWN. Retention policy, historical import timing and category filters are hypotheses, not established facts. The proof does not authorize any bulk import, live source request, Data Platform indexing, ETP operation or production database write. Future ingestion must separately pass business policy, permitted source admission, MI, full PITR/rollback and isolated staging.

Issues #679 (missing current official EIS files), #685 (seven-day PITR) and #686 (one PPT/PPTX source discrepancy) remain independent. The read-only historical ID diff is complete; root-cause and decisions about additional historic data remain blocked or open.

## Independent temporal diagnosis (still no proven business root cause)

A second original-page-only archive replay grouped each unique historical
external ID by the first original source publication year and membership
in the read-only working ID set. A separate PG16 repeatable-read read-only
aggregation measured publication-year and working row creation-day counts.

| Archived original publication year | Missing from working | In working |
| --- | ---: | ---: |
| 2019 | 2 | 0 |
| 2020 | 17 | 0 |
| 2021 | 78 | 0 |
| 2022 | 4,907 | 0 |
| 2023 | 13,218 | 0 |
| 2024 | 16 | 14,066 |
| 2025 | 7 | 9,965 |
| 2026 | 6 | 6,050 |
| Total | 18,251 | 30,081 |

The historic pre-2024 set accounts for 18,222 of 18,251 missing IDs,
and the 2024–2026 archive portion for only 29. The working DB itself
contains no source publication earlier than 2024-01-03 and has publication
year totals 2024=14,067, 2025=9,968, 2026=6,597.
The read-only working row creation-day counts are:
2026-11-14=313, 2026-11-15=30,081, 2026-11-19=238.

This strongly suggests a historical time-window or import-batch boundary,
but the inclusion and retention policy and original importer filter
configuration were NOT independently established. Do not mark a root cause
confirmed, assume it was intended, or import the 29 newer historical gaps.
The 551 extra IDs are also not proof of invalid records; they are only
outside the nine saved archived category sets.
