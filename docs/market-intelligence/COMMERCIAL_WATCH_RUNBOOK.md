# SIBUR / GEH commercial watch — source-safe operator runbook (2026-11-22)

## Business acceptance

This read-only watch answers **which procurement opportunities deserve review today**, not whether Arvectum is qualified to bid. The 0–100 score is only a deterministic *scope relevance* heuristic; it is **not** a win probability, bid recommendation, verified budget or assertion of legal stage.

- **GEH / Mosenergo / ETP GPB** — use the latest complete first-party public source snapshot from the scheduled `com.arvectum.tender-agent-geh-fresh-cycle` (currently 07:35 host-local). The digest independently verifies every raw HTML page SHA and the guarded ingest state, rejects incomplete captures, and separately labels actually new records versus already-known procedures. A price inquiry is MARKET_RESEARCH_ONLY, not a tender.
- **SIBUR** — `capture_sibur_public_snapshot.py` already exists in main, but as at 22-Nov there was **no verified daily current-public SIBUR LaunchAgent**. The indexer of historical source documents is not a substitute. To call data current, first create a fresh full public-only snapshot; the digest refuses missing pages or SHA drift. Non-atomic page captures do **not** prove closures when an ID disappears.
- **Commercial watch input** — use `sibur-current-commercial-watch-v18.json` (as-of 17-Nov) only to compare dated earlier curated records and detect explicitly observed deadline changes, never as a current eligibility or status source.

## Manual admission — no new production deployment

Read-only public capture (external GET, TLS, no redirects, no credentials; **local private files only**). This writes a new source-evidence folder, **not** a production database. Start only when no identical source capture is already running:

```sh
ROOT=/Users/master/ArvectumSafe/runtime/ta-source-discovery-20261114
SIBUR="$ROOT/sibur-sales-map-20261115"
CAPTURE="$SIBUR/current-commercial-$(date -u +%Y%m%dT%H%M%SZ)"
python -m scripts.research.capture_sibur_public_snapshot --output "$CAPTURE" --max-pages 40
```

Use the existing repository Python environment from the project root. The capture must have completed with `advertised_pages_traversed=true`, no `errors`, and actual SHA-verified page 1…N. The report additionally **fails closed** when any GEH or explicit current SIBUR source observation is older than **36 hours** (or future-dated by more than 5 minutes); an old saved folder cannot silently masquerade as today's shortlist. A transport-interrupted 22-Nov capture was **manually repaired by inspecting all original page hashes**, then fetching only pages 27–28; this special recovery is **not** a normal unattended fallback. Never substitute a partial capture.

Compile and inspect using only the saved originals (no database, HTTP, API or model calls):

```sh
python -m scripts.research.commercial_watch \
  --geh-snapshot "$ROOT/parallel-sources/<latest-verified-geh-snapshot>" \
  --sibur-watch "$SIBUR/sibur-current-commercial-watch-v18.json" \
  --sibur-current-capture "$CAPTURE" \
  --limit-per-source 14 --format markdown
```

`--as-of` may pin an UTC offset-aware timestamp for deterministic replay. Without `--sibur-current-capture`, the tool marks all SIBUR results from 17-Nov as STALE; **do not use those as the daily live list**.

## No silent promotion

The current local evidence as of 22-Nov: GEH 18/18 page hashes and 40 uniquely imported source rows, with 34 relevant unexpired list observations; SIBUR complete public 28/28 pages, 328 unique IDs, 54 relevant unexpired observations, 5 changed deadlines against the older selected watch, one publicly cancelled procedure excluded. Four public SIBUR source rows have date-only deadlines and are not assigned invented times. The supplier's eligibility, official card terms, budgets not explicitly published, original closed SIBUR SAP SRM procedures, and source coverage for contractors remain independently unverified.

**No new automatic LaunchAgent, scheduled model inference, production reindex, bid, credential usage or live database mutation is authorized by this PR.** Before installing the daily digest on Mac mini, approve a separate source-bound read-only deployment with fixed resource/runtime budget, logging/retention policy, fail-closed alerts on incomplete snapshots, and an explicit Owner gate. The low ingest P95 issue does not block *read-only source discovery*; it remains a gate for deploying Core/PRICE.
