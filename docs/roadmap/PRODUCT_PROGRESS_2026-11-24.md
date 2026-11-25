# Tender Agent — verified product progress, 24 November 2026

Dated progress delta to [the 23-Nov full product roadmap](PRODUCT_STATUS_2026-11-23.md), not a replacement for immutable MASTER_ROADMAP.md. Parent TA-ROADMAP-EXEC-20261012 remains in_progress.

## Completed engineering

| Scope | Proven result | Boundary |
| --- | --- | --- |
| Full roadmap | TA PR #738 merged, main 02b89e34; protected CI 9/9 | Docs only |
| Daily runner error attribution | TA PR #739 merged, main 61cf6c92; protected CI 9/9 | Code only; production runner remains pinned |
| APR03B/04/05 two-tenant synthetic API | TA PR #740 merged, main 674814ab; protected CI 9/9; local 126 PASS / 2 optional SKIP | Synthetic API only, no legal real-company acceptance or ETP |
| Read-only DTR status | TA PR #741 merged, main 37d1c896; protected CI 9/9, local DTR 60 PASS | Source-only, protected production runner stays pinned |
| New full-DTR resource admission | [TA PR #743](https://github.com/arvectum2/tender-agent/pull/743) merged protected main 45174590, exact-head CI 9/9, 38 focused PASS | Code only, live pinned launcher still unchanged; operations #744 OPEN |
| Search phase timing | [DP PR #138](https://github.com/arvectum2/data-platform/pull/138) merged, main 361f3b27; protected DP CI 12/12 and mirror success; local 50 PASS | Numeric-only code, not deployed; live search SLO still RED |

## Actual operations and blockers

- The 24-Nov DTR run DTR-20261124T050008Z-87f721ac was still RUNNING during read-only checks at 09:17–09:25 MSK. Aggregates: 4 manager-ready, 1 processing, 3 shortlisted, 21 screened-out and 4 duplicate, 33 total. No final completion or production HEALTHY claim.
- [TA PR #741](https://github.com/arvectum2/tender-agent/pull/741) merged and adds safe read-only grouped DTR status with database/role checks and fixed source-derived stage allowlist. Local 60 DTR tests PASS; protected CI 9/9 SUCCESS. No deployed source changed.
- Data Platform latest 24-Nov authenticated aggregate GET: search p95 10,086ms / 40 samples against target 1,500ms, overall RED. Ingest p95 1,213ms / 256 samples against target 10,000ms but earlier 85-sample ingest p95 was 37,083ms; these are different windows/mixes, so sustained recovery is NOT proven. Track [DP search #137](https://github.com/arvectum2/data-platform/issues/137) and [ingest #133](https://github.com/arvectum2/data-platform/issues/133) separately.
- Mac mini used over 25GiB swap; second Qwen, staging inference, iPhone simulator and service restarts remain resource-blocked.
- Official current EIS originals [#679](https://github.com/arvectum2/tender-agent/issues/679) and one SIBUR PPT original [#686](https://github.com/arvectum2/tender-agent/issues/686) require separately approved current primary-source proof; no blind fetch or fabricated authenticity.
- Seven-day physical PITR [#685](https://github.com/arvectum2/tender-agent/issues/685) remains unproven. Earliest independently receipted full base 20-Nov 08:47 UTC, first possible seven-day age 27-Nov 08:47 UTC, further WAL continuity and exact restore still required.

## Additional 24-Nov verified operations

- At 10:35 MSK, the 24-Nov DTR reached WAITING_HUMAN: 8 manager-ready, 21 screened-out, 4 duplicates, zero processing, no error on that run. Historical 19/20-Nov records still had error flags, explaining possible CLI exit 20; no blind retry or DB edit.
- [Capacity incident #744](https://github.com/arvectum2/tender-agent/issues/744) remains OPEN: swap had exceeded 90 GiB by 10:46 MSK, with no proven root cause. At 13:23 MSK swap was 17.4 GiB and the governor still reduced/3, not normal/10. No model/service restart or threshold change was performed.
- Read-only 10:40 MSK Data Platform support readiness: search p95 11,468ms/80 samples vs 1,500ms target (RED), ingest p95 1,220ms/256; new per-search phase counters were not on the live deployment. Issue [DP #137](https://github.com/arvectum2/data-platform/issues/137) remains OPEN.
- Real installed daily launchd Python script is pinned to release 023d3670/migration128. PR #743 matches that baseline, adding 52 lines and removing zero installed baseline lines. Source merge is not live launcher installation.

## Next release gates

1. Keep #741 source-only probe pinned to verified merged main; do not mistake source merge for production deployment.
2. Obtain independently measured real search/ingest phase attribution, owner-approved capacity and deployment; preserve SLO targets.
3. Verify current authoritative originals under admitted source scope; leave missing evidence UNKNOWN.
4. Prove seven-day real two-database PITR on a disconnected isolated restoration once horizon is met.
5. Complete real legal/company qualification, independent human gold and physical iPhone/APNs acceptance before commercial SaaS/ETP/signatures.

No new executor admission, watchdog, service, database, customer, source, bid, payment or external permission is granted by this record.

## Later 24-Nov engineering: read-only DP P0 localization (19:03 MSK)

- The original DP search source-only stage diagnostics PR #138 were already
  included in upstream main, but the live DP process still lacked the
  search_phases field in authenticated support readiness.
- Source-only [Data Platform PR #139](https://github.com/arvectum2/data-platform/pull/139)
  added privacy-preserving fixed search-mode and rerank/expansion feature
  cohorts to the existing stage timing, with 36 focused tests PASS.
  Protected DP CI 12/12 and GitVerse mirror 1/1 SUCCESS. Merged upstream
  main cdf922cf80f7bd11a2e1d305b9d453d8e14d296a.
- Live read-only DP readiness: ingest p95 34,275ms/256 vs 10,000ms target,
  embedding-phase p95 34,085ms, prepare63ms, lookup12ms, persist231ms.
  1–3 chunk requests p95 5,734ms (92), 4–8 8,386ms (67), 9–16 21,557ms
  (34), 17+ 55,188ms (63). Search p95 11,468ms/80 vs target1,500ms.
  Zero reported operation errors. These are observed p95 figures, not additive
  or independent proof of a specific model/queueing failure.
- Existing actual provider llama_cpp Qwen3-Embedding-4B (dimension2560),
  source batch count up to32 texts/32768 characters, bounded retry max3.
  Existing embedding_attempts counters mixed normal batches with retry
  attempts and could not separate their share.
- Source-only [DP PR #140](https://github.com/arvectum2/data-platform/pull/140)
  adds distinct numeric-only batch/retry counters to existing authenticated
  ingest phase readiness, including a failed last batch. 24 focused tests,
  Ruff and protected DP CI 12/12 plus mirror1/1 SUCCESS. Merged upstream
  main ec6cac92fa42897df8a908f4b7c3d5a3d292febe.
- **Hard boundary:** Neither upstream source merge updates the production
  model/DP service. Live ingestion/search SLO issues
  [#133](https://github.com/arvectum2/data-platform/issues/133) and
  [#137](https://github.com/arvectum2/data-platform/issues/137) remain open.
  A pinned, rollback-capable owner-approved rollout followed by real
  time-window metrics and isolated synthetic root-cause experiments is
  needed before claiming restored performance. No model POST, live ingest,
  reindexing, database update, threshold change or service restart was done.
