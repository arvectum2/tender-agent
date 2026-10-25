# MI-003: Supplier portfolio → Power Quality technical demand candidates

Snapshot date: 2026-10-24; terminology-search integration updated 2026-10-25 (MI-006). Development status: **offline/SDK-contract validated, not deployed**.
Depends on Tender Agent MI-001 (#501), source-audited Power Quality MI-002 (#502). The EIS SOAP path is developed independently in PR #503 and remains blocked by upstream maintenance. Data Platform format enhancement: #126 (PPTX, not merged).

## Commercial job and boundary

A vendor uploads a description, one or more public HTTPS website URLs, and/or a catalogue/deck/price file. A **trusted tenant-aware caller** maps their account identity to a tenant ID and an authorized set of market source collection IDs. This service ingests the vendor's materials into a dedicated Data Platform collection. It proposes technical product families from the published, *not independently verified*, vendor assertions, creates ontology-expanded hybrid queries and returns procurement **text fragment candidates** for analyst review.

A retrieved fragment, vector similarity or secondary procurement card alone does **not** establish an active procurement, contract award, name of EPC, identity of ultimate equipment supplier, installed equipment, a signed amount, or a fully sized market.

## Existing functionality reused

- Data Platform Python SDK `arvectum_data_client.DataPlatformClient`: `ensure_collection`, `ingest_document`, `ingest_document_bytes`, `ingest_url` and (MI-006) `search(mode="hybrid", terminology_groups=[...], terminology_version=...)`. The generic terminology implementation is in Data Platform PR #127 and SDK v0.4.0. Current installed SDK v0.3 is insufficient until reviewed/upgraded; it fails closed instead of falling back to MI-side query expansion.
- Data Platform owns acquisition, extraction and chunked searchable corpus. Tender Agent does **not** maintain a competing search index.
- Power Quality ontology families: `statcom`, `ukrm`, `thyristor`, `harmonic_filter`, `power_quality_system`. They supply versioned aliases, contexts, exclusions and ambiguous terms as a plug-in **to the generic Data Platform matcher**. MI does not own query expansion or indexed chunk matching; legacy local lexical checks remain only for offline SOAP corpus scanning and supplier-hypothesis classification.
- Source-bound, stable `chunk_id`/`document_id`/`canonical_uri` are retained from Data Platform search. An index-supplied hash by itself is `unverified_index_metadata`. `reviewed_source_manifest` requires a separately supplied approved canonical_uri→SHA-256 map and matching metadata hash. No automatic promotion into MI-001 revenue.
- Project role assertions require an authorized project ID, legal entity INN, approved human reviewer, document SHA256, HTTP(S) HTTPS source, locator, original excerpt and source type `official_protocol`, `signed_contract` or `primary_project_document`. EPC/winning bidder additionally require original protocol or signed contract; all invalid entries quarantined. Secondary cards remain reported buyers, not EPC winners.
- 7-source × 37-calendar-month coverage matrix (Oct 2023 and Oct 2026 are **partial boundary months**) with `not_checked`/ `failed` and unknown denominators. `verified_complete` requires external proof + measured expected/observed counts.

## Input caps and privacy

- Max 120k characters of vendor description, 8 public HTTPS URL records, 16 documents of up to 20 MiB each, fixed supported list TXT/MD/CSV/HTML/DOC/DOCX/RTF/PDF/XLS/XLSX/PPTX.
- Deny username/password in URL, local hostnames and literal private/loopback IP, nondefault HTTPS ports, symlinks, unsupported file types and oversized source. Data Platform additionally checks public DNS targets; **redirect pinning/DNS rebinding and browser-rendered pages need a separate end-to-end security acceptance gate before exposing arbitrary URL ingestion to customers**.
- Source collections passed to hybrid search must be a subset of the trusted caller's `authorized_collection_ids`. These must be generated from authentication/ACL, not copied from a user-provided query.
- Creating a hashed collection ID does not alone enforce tenant isolation. Data Platform consumer authorization, data access policy and authenticated tenant binding must be validated before production.
- Data Platform PPTX reader was added to independent PR #126; PPTX must not be offered to live customers until the change is released and the actual server's `extraction_status` is confirmed.
- Materials must be supplied by the user under appropriate rights. Ingestion is a data write to the user's isolated collection; the current test used mocks and no real customer materials.
- Missing extraction and invalid input fail closed. Do not leak private files to third-party LLM.

## Implementation and commands

Files: `src/modules/market_intelligence/portfolio_pipeline.py` (ingestion, product proposals, **Data Platform terminology search client adapter**, verified role graph and coverage); `src/modules/market_intelligence/technical_matching.py` (legacy **offline** candidate matcher for SOAP corpus and supplier descriptions, **not search query expansion**); `src/modules/market_intelligence/mi003_pq_evaluation.py` (source-limited evaluation). New MI-006 integration runbook: `docs/product/MI006_DATA_PLATFORM_NATIVE_SEARCH.md`.

From Tender Agent checkout with project Python environment:

```bash
python -m src.modules.market_intelligence.mi003_pq_evaluation \
  --seed data/market_intelligence/power_quality/verified_public_leads.v1.json \
  --ontology data/market_intelligence/power_quality/ontology.v1.yaml \
  --json-out data/market_intelligence/power_quality/mi003_evaluation.v1.json \
  --md-out docs/market_intelligence/MI003_POWER_QUALITY_READINESS_20261024.md
```

Read-only API example (requires pre-authorized Data Platform instance/collections and authenticated tenant):

```python
from arvectum_data_client import DataPlatformClient
from src.modules.market_intelligence.portfolio_pipeline import (
    ingest_supplier, propose_families, search_demand
)
# Genuine service credentials must come from secret management, NOT code.
client = DataPlatformClient(base_url="https://<internal-data-platform-host>", api_key="<secret>")
intake = ingest_supplier(
    client, tenant_id="<authenticated-tenant-id>", run_id="run_20261024",
    company_name="Поставщик", text="Производим СТАТКОМ и УКРМ",
)
# Get ontology from versioned approved file; treat family proposals as hypotheses.
# Search authorized official-source collections, not the supplier's portfolio collection.
```

**Do not run the example against production or paste real credentials in chat.** It illustrates contract, not a configured deployment.

## What the bounded October 2026 source test actually proves

- 12 previously discovered Power Quality procurement descriptions, manually assigned `family` by the earlier MI-002 review: **12/12 labels found** by current ontology matcher (description-level sample recall = 1.0).
- Eight explicitly **synthetic** negative controls: 0 false-positive examples. This is not a statistically valid precision estimate.
- Among the existing 12 leads: 11 have only third-party card evidence; 1 has a publicly accessible primary platform page. 10 reported distinct buyers; verified EPC/winners/designers from original protocols: 0.
- 259 source×calendar-month slots in October 2023–October 2026 window (7 sources × 37 months), confirmed-complete slots: 0; October 2026 EIS-44 and EIS-223 marked failed. This is **unknown coverage**, not zero demand.
- Power Quality supplier TAM, contract amount total, manufacturer shares and historical win rates remain **unknown**. No open 2026 tender is claimed from stale cards.
- A small synthetic EPC technical paragraph containing explicit STATCOM and harmonic filter terms was recognized in testing; **recall on real embedded procurement attachments has not yet been measured**. It is the critical remaining MI-003 search quality gate.

## Readiness toward MI-004 and MI-005

| Gate | Status |
|---|---|
| Intake interface for supplier text/files/URL via SDK | Code tested, live backend/ACL acceptance pending |
| PPTX native text/slide/table extraction | Separate Data Platform PR #126; no service release |
| PQ ontology and technical query expansion | Ontology owned by MI; generic expansion/matching in Data Platform PR #127, SDK v0.4 upgrade required before live execution |
| Hybrid search against actual national attachment corpus | Not measured: source-month EIS/ETP ingestion missing |
| Source hash/fragment binding | Implemented conditional reviewed SHA mapping; real manifest reconciliation pending |
| Named customer/account action hypotheses | 10 accounts, source links, no verified EPC claims |
| Role graph provenance | Quarantine/review contract implemented; 0 verified winners/designers in pilot |
| Full market value, share and win-rate | Blocked by historical coverage and primary award/contract retrieval |
| Customer-facing web portal and delivery | Restricted report download API exists in MI-005 (disabled by default); full customer web UI not delivered |
| Supplier uploads on production/real customer documents | Not tested; tenant/privacy/SSRF/end-to-end approval missing |

Next step independent of EIS: document-format and semantic retrieval evaluation using legally accessible real EPC technical attachments from commercial portals, indexed through tenant-safe Data Platform corpus; test top-K recall/precision against independently labelled passages. Meanwhile advance official SOAP source backfill after maintenance, **not now**.
