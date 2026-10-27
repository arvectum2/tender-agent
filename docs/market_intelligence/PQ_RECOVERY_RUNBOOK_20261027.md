# PQ recovery runbook

Run from the isolated MI worktree, not the dirty primary checkout. Canonical task checkpoint: `.agent/checkpoints/TA-MI-AUTONOMY-20261027.yaml`.

1. Refresh `pq_gap_recovery` inventory using the latest complete MI-013 leads file, not the 12-lead seed; include every official-original directory.
2. Run bounded `pq_source_recovery` for live EIS matches. Journal real network attempts and respect retry windows.
3. Rebuild `pq_archive_index` when official SHA-verified ZIP inventory changes. The previous 156 archives indexed 9,074 notice numbers but had zero exact overlap with the 58-lead test slice; do not confuse XML counts with relevant tenders.
4. Run `pq_indexed_recovery` for exact number matches, preserving verified XML/ZIP provenance. Never guess EIS filestore links.
5. Run `pq_dp_ingest` on newly downloaded originals. Its native PDF fallback is verified on the 32615969197 PDF (2,685 chars).
6. Run `pq_queue_seed` on all verified original roots; review new packets with ChatGPT via ARC and persist quoted source evidence.
7. Seek original protocols, amendments, contract registry records and ETP documents; distinguish signed contract price from NMCK and bid price.
8. Preserve incomplete cases with retry status and never assert comprehensive market coverage.

Current gaps: no unified cycle executor yet, no verified live commercial ETP connector, and no complete signed-contract outcome reconciliation. Next engineering step is a tested idempotent cycle runner with per-stage receipts and resume; then run against full MI-013 corpus.

## Bounded cycle implementation (2026-10-27)

`python -m src.modules.market_intelligence.pq_recovery_cycle --leads-file <materialized-records.json> --source-root <verified-originals-root> --ontology data/market_intelligence/power_quality/ontology.v1.yaml --queue-dir <private-review-queue> --output-dir <private-runtime> --max-cases 8 --live-search --archive-index <sha-verified-index.json> --archive-target <private-recovered-originals>`

The cycle acquires a 300-second cooperative lease (never steals an expired lease), refreshes gap inventory, performs bounded official EIS **notice** searches with existing retry journal, attempts exact SHA-indexed original attachment acquisition, seeds/reuses source-bound review packets and exposes the next packet for the current ChatGPT conversation. It persists `last_cycle.json` and releases its own lease. Signed-contract/winner/price/ETP/tenant-ingestion stages remain explicitly unattempted until separate verified adapters and authorization exist. It never invokes a local model or OpenAI API.

**Important corpus gate:** `verified_public_leads_20261027.v29.manifest.json` describes 101 active rows but contains **no `records`**. The current 58-record `v7.json` subset is not full v29 coverage. The runner rejects a manifest-only input rather than silently claiming 101 processed. Materialize and source-verify the complete v29 row set before reporting full-corpus recovery.

**Actual isolated Mac mini check:** 16 focused tests passed at `b4c03ac6`; five fresh exact official EIS notice searches succeeded, bringing the known eligible numeric subset to 13 logged searches. The existing archive index has zero exact overlap with these 58 leads; no new signed contract, award or original attachment was established. Existing two source-bound reviews were reused, not duplicated. No production ingestion.
