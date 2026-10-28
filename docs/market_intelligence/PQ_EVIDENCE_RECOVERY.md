# MI-013 — Missing procurement evidence recovery

The hourly Tender Agent Watchdog must treat a known PQ lead as an **open evidence-recovery case**, not a finished row, until each material source is verified or explicitly unavailable. The first inventory is `python -m src.modules.market_intelligence.pq_gap_recovery` against `verified_public_leads.v1.json`; the wider v29 corpus must be integrated separately, not silently assumed covered.

## Repeated source search (each productive scheduled run)

1. Inventory known procurement IDs, notice revisions, lots and project aliases. Deduplicate on procurement/lot/project/contract and source SHA.
2. For every incomplete case search exact ID on official EIS notice page and EIS contract registry (223-FZ/44-FZ as appropriate). Also search the originating commercial ETP and its archive, amendments, protocols and attached specifications. Try alternative legal customer name, project name, asset name and equipment synonyms (УКРМ, КРМ, СТАТКОМ, STATCOM, SVG, SVC, ТКРМ, фильтр гармоник, 6–35 кВ).
3. Reuse allowlisted, verified-TLS EIS attachment acquisition and XML-to-filename provenance. Do not synthesize old filestore URLs, bypass access controls, or treat a search snippet as an official award.
4. Record for **each source attempt**: procurement ID, missing field, source URL or provider, timestamp, status (found / not_found / inaccessible / retryable / permanently_unavailable), original SHA and retrieval method where available, retry count and next eligible retry time. Retry transient failures with bounded exponential backoff, cap attempts per run, and continue other cases instead of waiting indefinitely.
5. On new original files, enqueue via `pq_queue_seed`, classify in ChatGPT via ARC, validate source quotations and persist decisions. Cross-check award protocol against signed contract registry. Distinguish NMCK/planned amount/offer/contract amount, and design/supply/EPC/maintenance.
6. Prioritize: missing signed contracts/winners for relevant cases; original technical specifications for high-value ambiguous cases; protocols for no-bid or cancelled cases; then broader discovery. Never turn unknown fields into zero or market totals.
7. Keep backlog and exact resume pointer durable. Continue processing next eligible case until platform budget or actual blocker. Keep existing watchdog; do not create another schedule.

## Status of implementation

`pq_gap_recovery.py` creates a deterministic **gap inventory** from known seed leads and local originals. It is not yet a network fetch/retry scheduler, and does not claim to search EIS or ETP by itself. EIS attachment acquisition already exists as a separate component. Next step: wire a source-attempt journal, source adapters and bounded retries into the hourly runner, then extend beyond the 12-row seed to the full v29 corpus.

## Corpus-wide ETP URL queue (2026-10-28)

Use `python -m src.modules.market_intelligence.pq_etp_queue_expand --leads-file <SHA-tracked-v20-corpus> --output <runtime-queue>` to enumerate **all exact, allowlisted, case-specific URLs already present in the immutable 100-row corpus**, not just the previous manually selected ETP queue. Duplicate URL aliases are retained without repeating network requests. Generic category/customer indexes and unsafe/unsupported URLs are excluded and counted. Run `pq_etp_card_audit` with both the main and native attempt journals: its 12-hour URL-level retry guard remains authoritative. A retrieved secondary HTML page is **not** an original specification, signed award, supplier or contract price; retain gaps until verified primary evidence is recovered.
