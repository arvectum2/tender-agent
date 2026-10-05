# Local RAG Index For Tender Research

Mac mini is now the source of truth for Arvectum runtime data. PostgreSQL +
pgvector is the server-side database, while SQLite remains the fast default for
dev and tests. The local RAG layer sits on top of already downloaded and
extracted tender documents. Retrieval has two explicit backends:

- legacy: provider/model-specific JSON vector stores under data/rag/;
- data_platform: shared Arvectum Data Platform hybrid retrieval
  (PostgreSQL FTS + pgvector + RRF).

The Data Platform backend is the default shared production architecture. The
legacy backend remains an explicit rollback/compatibility mode.

For the validated Mac mini runtime layout and exact live server commands, see
[macmini_rag_runtime.md](/Users/master/Documents/AI-Corporation/docs/tender_research/macmini_rag_runtime.md).

Demo runbook for tender RAG analysis:
[docs/demo/tender_rag_analysis/README.md](../demo/tender_rag_analysis/README.md)

## Scope

- No cloud LLM dependency is required.
- No OCR is introduced.
- Only documents with `text_extraction_status=extracted` are chunked.
- Repeated indexing runs are idempotent for both chunks and embeddings.
- `local_hash` stays available as a smoke/test fallback.
- `llama.cpp` embeddings are the preferred local production path.

## Data Model

The local RAG layer uses:

- `procurement_document_chunks`
- `procurement_document_embeddings`
- `tender_analysis_runs`

Saved analysis reports are written under `data/rag/reports/`.
Generated runtime export artifacts are written under `data/rag/exports/`.
Both locations are runtime-only and are ignored by git.

Chunks keep the source document and tender linkage, character offsets, token
estimate, and source paths. Embeddings keep provider/model metadata and a
`vector_id` that points into a provider/model-specific local vector store file.

## Recommended Models

- First production-style local embedding model: `Qwen3-Embedding-4B`
- Benchmark comparison model: `BGE-M3`
- Heavy test / future benchmark: `Qwen3-Embedding-8B`
- Smoke/test fallback only: `local-hash-v1`

## Embedding Server Layout

Keep chat and embeddings as separate local services on Mac mini:

1. Chat / reasoning server
   `http://127.0.0.1:8088/v1`
2. Embedding server
   `http://127.0.0.1:8090/v1`

Example embedding server commands:

```bash
llama-server \
  --model /Users/master/models/embeddings/Qwen3-Embedding-4B-Q8_0.gguf \
  --embedding \
  --ctx-size 8192 \
  --port 8090
```

```bash
llama-server \
  --model /Users/master/models/embeddings/bge-m3-Q8_0.gguf \
  --embedding \
  --ctx-size 8192 \
  --port 8090
```

Pooling depends on both the model and the current `llama.cpp` build. Do not
hardcode pooling in application config. Keep the exact launch command in a
local runbook, not in `.env` and not in git-tracked secrets.

## Commands

Build chunks:

```bash
python -m src.tender_research.rag.cli build-chunks --limit 100
```

Check the embedding server:

```bash
python -m src.tender_research.rag.cli check-embedding-server \
  --provider llama_cpp \
  --model Qwen3-Embedding-4B \
  --base-url http://127.0.0.1:8090/v1
```

Build embeddings with the smoke fallback:

```bash
python -m src.tender_research.rag.cli build-embeddings \
  --provider local_hash \
  --model local-hash-v1 \
  --limit 1000
```

Build embeddings with `llama.cpp`:

```bash
python -m src.tender_research.rag.cli build-embeddings \
  --provider llama_cpp \
  --model Qwen3-Embedding-4B \
  --base-url http://127.0.0.1:8090/v1 \
  --batch-size 16 \
  --limit 5000
```

Search:

```bash
python -m src.tender_research.rag.cli search \
  --query "требования к содержанию и составу заявки" \
  --provider llama_cpp \
  --model Qwen3-Embedding-4B \
  --limit 10
```

## Report Reuse And Export

- History/report API reuses saved `report_markdown` by `analysis_run_id`.
- DOCX export endpoint:
  `/api/tender-research/analyze/history/<analysis_run_id>/export/docx`
- PDF export endpoint:
  `/api/tender-research/analyze/history/<analysis_run_id>/export/pdf`
- Export does **not** rerun retrieval or LLM analysis.

Eval:

```bash
python -m src.tender_research.rag.cli eval \
  --questions tests/fixtures/tender_research/rag_eval_questions.json \
  --provider llama_cpp \
  --model Qwen3-Embedding-4B \
  --limit 5
```

Ask one registry number without LLM:

```bash
python -m src.tender_research.rag.cli ask \
  --registry-number 0373200027426001278 \
  --question "Какие требования к составу заявки?"
```

Analyze one registry number into a markdown report:

```bash
python -m src.tender_research.rag.cli analyze-tender \
  --registry-number 0323100010326000013 \
  --provider llama_cpp \
  --model Qwen3-Embedding-4B \
  --base-url http://127.0.0.1:8090/v1 \
  --use-llm \
  --analysis-mode fast \
  --llm-base-url http://127.0.0.1:8088/v1 \
  --llm-model /Users/master/models/Qwen2.5-14B-Instruct-Q4_K_M.gguf \
  --limit 8 \
  --output data/rag/reports/analyze_tender_0323100010326000013.md
```

`analyze-tender` now supports latency presets:

- `--analysis-mode fast`
- `--analysis-mode balanced`
- `--analysis-mode detailed`

Optional overrides:

- `--max-context-chars-per-section`
- `--max-chunks-per-section`
- `--llm-timeout-seconds`

## Configuration

Supported environment variables:

```bash
AI_CORP_RAG_CHUNK_SIZE_CHARS=1500
AI_CORP_RAG_CHUNK_OVERLAP_CHARS=200
AI_CORP_RAG_MIN_CHUNK_CHARS=120
AI_CORP_RAG_EMBEDDINGS_PROVIDER=local_hash
AI_CORP_RAG_EMBEDDINGS_MODEL=local-hash-v1
AI_CORP_RAG_EMBEDDINGS_BASE_URL=http://127.0.0.1:8090/v1
AI_CORP_RAG_EMBEDDINGS_TIMEOUT_SECONDS=60
AI_CORP_RAG_EMBEDDINGS_BATCH_SIZE=16
AI_CORP_RAG_EMBEDDINGS_DIMENSION=auto
AI_CORP_RAG_VECTOR_STORE=json
AI_CORP_RAG_VECTOR_STORE_PATH=./data/rag/vector_store.json
AI_CORP_RAG_RETRIEVAL_BACKEND=data_platform
AI_CORP_RAG_DATA_PLATFORM_BASE_URL=http://127.0.0.1:8094
AI_CORP_RAG_DATA_PLATFORM_API_KEY=
AI_CORP_RAG_DATA_PLATFORM_TIMEOUT_SECONDS=30
AI_CORP_RAG_USE_LLM=false
AI_CORP_LOCAL_LLM_BASE_URL=http://127.0.0.1:8088/v1
AI_CORP_LOCAL_LLM_MODEL=qwen2.5-14b
AI_CORP_LOCAL_LLM_TIMEOUT_SECONDS=120
```

### Optional sentence-transformers mode

The code also supports:

```bash
AI_CORP_RAG_EMBEDDINGS_PROVIDER=sentence_transformers
AI_CORP_RAG_EMBEDDINGS_MODEL=intfloat/multilingual-e5-small
```

This mode requires the `sentence-transformers` package to be installed locally.
If it is not installed, the CLI will fail with a clear error and the local
`local_hash` provider remains available as the dependency-free fallback.

## Storage

With the default AI_CORP_RAG_RETRIEVAL_BACKEND=data_platform, Tender Agent keeps its
procurement-domain chunks and citation metadata in its own database, while
Data Platform owns lexical/vector indexes. Each current tender chunk is sent as
pre-chunked text with a stable tender-chunk://<chunk_id> canonical URI.

With AI_CORP_RAG_RETRIEVAL_BACKEND=legacy, vectors are stored locally in JSON
files under data/rag/. This path is retained only for explicit rollback and
compatibility testing.

A tender is indexed into a deterministic versioned collection:

    tender-agent:<tender_id>:<chunk-set-revision>

If the tender chunk set changes, the revision changes and retrieval will not
silently use an old collection. Preparation is fail-closed: analysis requires
Data Platform collection stats to match the current Tender Agent chunk count.

Eval results are written as JSONL under data/rag/eval/.

## Retrieval Mode

By default `ask` works in retrieval-only mode and prints the best matching
chunks. If `AI_CORP_RAG_USE_LLM=true` or `--use-llm` is passed, the CLI can
optionally call a local OpenAI-compatible chat endpoint and answer strictly
from the retrieved context.

`analyze-tender` builds a multi-section markdown report for a single
`registry_number`. Without `--use-llm` it stays retrieval-only and shows the
best matching local fragments per section. With `--use-llm` it calls the local
chat endpoint section by section and preserves structured citations for every
answer.

For latency visibility, both CLI and API now expose:

- `analysis_mode`
- `duration_seconds`
- `timings`
- `per_section_timings`
- `llm_calls_count`
- `total_context_chars`
- `max_section_context_chars`

## REST API

The analysis service is also exposed via REST on the backend (`port 8001`).

### Health

```
GET /api/tender-research/health
```

Returns database dialect, masked URL, connectivity, migration head, pgvector
availability, and per-table row counts. No secrets are leaked.

Example response:

```json
{
  "status": "ok",
  "database_dialect": "postgresql",
  "database_url_masked": "postgresql+psycopg://arvectum:***@127.0.0.1:55432/arvectum",
  "can_connect": true,
  "current_migration": "090_enable_pgvector_and_add_rag_tables",
  "migration_head": "088_create_tender_research_tables",
  "pgvector_extension_available": true,
  "table_counts": {
    "procurement_tenders": 7,
    "procurement_tender_documents": 35,
    "procurement_document_chunks": 280,
    "procurement_document_embeddings": 560
  }
}
```

### Analyze

```
POST /api/tender-research/analyze
Content-Type: application/json
```

Request body:

```json
{
  "registry_number": "0323100010326000013",
  "provider": "llama_cpp",
  "model": "Qwen3-Embedding-4B",
  "base_url": "http://127.0.0.1:8090/v1",
  "use_llm": true,
  "llm_base_url": "http://127.0.0.1:8088/v1",
  "llm_model": "/Users/master/models/Qwen2.5-14B-Instruct-Q4_K_M.gguf",
  "limit": 8,
  "save_report": true
}
```

Expected response fields:

| Field | Description |
|-------|-------------|
| `status` | `completed`, `completed_with_warnings`, `no_context`, or `failed` |
| `registry_number` | Input registry number |
| `sections_count` | Number of analysis sections (always 10) |
| `sources_count` | Total unique document chunks used |
| `report_markdown` | Full structured report in markdown |
| `report_path` | Path to saved report file (if `save_report=true`) |
| `used_llm` | Whether LLM was used for answer generation |
| `warnings` | Non-fatal warnings (e.g. LLM fallback) |
| `errors` | Fatal errors (e.g. tender not found) |

### Background Jobs

For long-running prepare/analyze flows the backend now also exposes
lightweight in-process background jobs:

```text
POST /api/tender-research/jobs/prepare
POST /api/tender-research/jobs/analyze
GET  /api/tender-research/jobs/{job_id}
GET  /api/tender-research/jobs
```

The start endpoints return `job_id`, `status=queued`, and a `status_url`.
The status endpoint returns:

- `status`: `queued`, `running`, `completed`, `completed_with_warnings`, `failed`, `cancelled`
- `progress_percent`
- `current_step`
- `steps`
- `result`
- `warnings`
- `errors`

This MVP runner is in-process and intentionally does not require Celery, Redis,
or any external queue for the local demo contour.

**`no_context` behavior**: If the tender is not found in the database, or no
embeddings exist for the chosen provider/model, the endpoint returns
`status=no_context` with an empty sections list and a descriptive error.

**`completed` behavior**: All 10 sections are generated. Each section contains
an answer (LLM-generated if `use_llm=true` and the LLM is reachable, otherwise
retrieval-only) and a list of source citations. The report markdown includes
section headers, answers, and source details.

**Report saving**: When `save_report=true`, the markdown is written to
`data/rag/reports/analyze_tender_{registry_number}.md`. The file is also
returned in `report_path`.

**Citations/sources**: Every section lists the document chunks used. Each
citation includes: document file name, chunk UUID, registry number, tender
title, and cosine similarity score. Sources are deduplicated for the
`sources_count` total.

### Latest Report

```
GET /api/tender-research/analyze/{registry_number}/latest
```

Returns the most recently saved report for a registry number. Example:

```bash
curl http://127.0.0.1:8001/api/tender-research/analyze/0323100010326000013/latest
```

Response:

```json
{
  "registry_number": "0323100010326000013",
  "report_markdown": "# Анализ закупки ...",
  "report_path": "data/rag/reports/analyze_tender_0323100010326000013.md",
  "created_at": null
}
```

- `registry_number` is validated as an 11-25 digit string.
- Path traversal is blocked; only files under `data/rag/reports/` are served.
- Returns 404 if no report exists for the given registry number.

### Prepare

```
POST /api/tender-research/prepare
Content-Type: application/json
```

Prepares a tender for RAG analysis: ingest → download → extract → chunk → embed.

Request body:

```json
{
  "registry_number": "0323100010326000013",
  "provider": "llama_cpp",
  "model": "Qwen3-Embedding-4B",
  "base_url": "http://127.0.0.1:8090/v1",
  "rebuild_chunks": false,
  "rebuild_embeddings": false
}
```

Response fields:

| Field | Description |
|-------|-------------|
| `status` | `completed`, `completed_with_warnings`, `no_tender`, or `failed` |
| `ready_for_analysis` | `true` if chunks and embeddings exist |
| `steps` | List of preparation steps with status/message/detail |
| `documents_total` | Total documents for the tender |
| `documents_downloaded` | Documents successfully downloaded |
| `extracted_texts_total` | Documents with extracted text |
| `chunks_total` | Total chunks in DB for this tender |
| `embeddings_total` | Total embeddings in DB for this tender |

Example response (ready):

```json
{
  "status": "completed",
  "ready_for_analysis": true,
  "steps": [
    {"name": "check_tender_exists", "status": "completed", "message": "Tender found in database"},
    {"name": "download_documents", "status": "skipped", "message": "Documents already downloaded"},
    {"name": "build_chunks", "status": "skipped", "message": "Chunks already exist (50)"},
    {"name": "build_embeddings", "status": "skipped", "message": "Embeddings already exist (50)"},
    {"name": "readiness_check", "status": "completed", "message": "Ready for analysis..."}
  ],
  "chunks_total": 50,
  "embeddings_total": 50
}
```

**Idempotent:** Existing chunks and embeddings are skipped unless
`rebuild_chunks=true` or `rebuild_embeddings=true`.

### Prepare Status

```
GET /api/tender-research/prepare/{registry_number}/status
```

Fast readiness check (no heavy operations). Returns:

```json
{
  "registry_number": "0323100010326000013",
  "tender_found": true,
  "documents_total": 35,
  "documents_downloaded": 35,
  "extracted_texts_total": 14,
  "chunks_total": 280,
  "embeddings_total": 280,
  "ready_for_analysis": true,
  "missing": []
}
```

If not ready:

```json
{
  "ready_for_analysis": false,
  "missing": ["chunks", "embeddings"]
}
```

## Known Limitations

- `local_hash` is not semantic and should only be treated as a smoke provider.
- `llama.cpp` availability is external to the test suite and must be checked via
  `check-embedding-server`.
- Pooling behavior depends on the model and the current `llama.cpp` build.
- Output dimension for some GGUF embedding models may still depend on runtime
  behavior rather than a fixed CLI flag.
- Eval currently reports retrieval outputs and simple summary stats only; it
  does not run an automatic judge.
- **Prepare endpoint is synchronous MVP** — first-time preparation (ingest +
  download + chunk + embed) may take several minutes. No background job queue.
- **OCR not implemented** — scanned PDFs and images produce no text.
- **Unsupported document formats** are silently skipped during extraction.
- **EIS SOAP availability** affects ingest of new tenders.
- **Embedding server (port 8090)** must be running for `build_embeddings` step.

## Data Platform Retrieval Backend

Tender-specific ingestion, EIS/44-FZ/223-FZ semantics, chunk provenance, analysis, citations, and human-control rules remain in Tender Agent. Reusable lexical/vector indexing and hybrid retrieval can be delegated to Arvectum Data Platform.

Activation is explicit:

```bash
AI_CORP_RAG_RETRIEVAL_BACKEND=data_platform
AI_CORP_RAG_DATA_PLATFORM_BASE_URL=http://127.0.0.1:8094
AI_CORP_RAG_DATA_PLATFORM_API_KEY=
AI_CORP_RAG_DATA_PLATFORM_TIMEOUT_SECONDS=30
```

After switching, run the normal tender preparation flow. Tender Agent keeps its canonical procurement chunks, creates a versioned Data Platform collection for that tender, and indexes each chunk with a stable `tender-chunk://<chunk_id>` canonical URI. Search uses Data Platform hybrid retrieval and maps every hit back to the original Tender Agent chunk before citations or analysis are produced. Tender RAG uses a semantic-first weighted RRF profile (lexical_weight=1, vector_weight=4); Data Platform defaults remain unchanged for other consumers.

There is intentionally **no automatic fallback** from `data_platform` to the legacy JSON vector store. If the platform is unavailable or the versioned collection is incomplete, preparation/readiness fails closed and analysis returns `no_context` until the platform index is prepared.

`legacy` remains available as an explicit rollback/compatibility backend during migration. `build-embeddings` and direct JSON-vector maintenance commands belong to that legacy path; normal `prepare` handles Data Platform indexing when `AI_CORP_RAG_RETRIEVAL_BACKEND=data_platform`.
