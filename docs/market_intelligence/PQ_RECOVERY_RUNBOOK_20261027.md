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
