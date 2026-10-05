# Mac mini RAG Runtime

Mac mini is the server-side source of truth for the Arvectum tender research
runtime.

Demo runbook for tender RAG analysis:
[docs/demo/tender_rag_analysis/README.md](../demo/tender_rag_analysis/README.md)

## Server Checkout

- Main working checkout for the live smoke run:
  `/Users/master/Documents/AI-Corporation-live`
- The primary repository checkout on Mac mini may be dirty. Use the clean
  runtime checkout above for repeatable smoke runs.

## Database Runtime

- Docker PostgreSQL for Arvectum runs on host port `55432`
- Homebrew PostgreSQL already occupies `5432`, so Arvectum must point to `55432`
- Required runtime env var:

```bash
AI_CORP_DATABASE_URL=postgresql+psycopg://arvectum:<PASSWORD>@127.0.0.1:55432/arvectum
```

Do not commit real passwords or `.env*` files.

## Llama.cpp Services

- Chat LLM endpoint: `http://127.0.0.1:8088/v1`
- Embedding endpoint: `http://127.0.0.1:8090/v1`

Embedding model used in the validated smoke run:

- repo: `Qwen/Qwen3-Embedding-4B-GGUF`
- file:
  `/Users/master/models/embeddings/Qwen3-Embedding-4B-GGUF/Qwen3-Embedding-4B-Q8_0.gguf`

Validated embedding server command:

```bash
/opt/homebrew/bin/llama-server \
  --model /Users/master/models/embeddings/Qwen3-Embedding-4B-GGUF/Qwen3-Embedding-4B-Q8_0.gguf \
  --alias Qwen3-Embedding-4B \
  --embedding \
  --pooling last \
  --ctx-size 8192 \
  --parallel 1 \
  --batch-size 2048 \
  --ubatch-size 2048 \
  --threads 8 \
  --threads-batch 8 \
  --no-cont-batching \
  --port 8090
```

Why `batch-size/ubatch-size=2048`:

- one real production chunk tokenized to `1044` tokens;
- the earlier `1024` physical batch caused live failures;
- `2048` cleared the smoke run and kept the embedding server stable.

## Successful API Smoke

All smoke checks passed with `registry_number=0323100010326000013` using
the canonical runtime configuration.

### Canonical Database

- **Docker Postgres**: `pgvector/pgvector:pg17` on `127.0.0.1:55432`
- **Backend and CLI** must use the same `AI_CORP_DATABASE_URL`:

```bash
AI_CORP_DATABASE_URL=postgresql+psycopg://arvectum:<PASSWORD>@127.0.0.1:55432/arvectum
```

- **Health endpoint** (`GET /api/tender-research/health`) returns masked URL,
  migration head, pgvector status, and table counts. Use it to verify DB/runtime
  alignment after restart.

### Embedding and LLM Servers

- Embedding server: `http://127.0.0.1:8090/v1`, model `Qwen3-Embedding-4B`
- Chat LLM server: `http://127.0.0.1:8088/v1`
- Mac mini LLM model id: `/Users/master/models/Qwen2.5-14B-Instruct-Q4_K_M.gguf`

### CLI Result

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
  --save-report
```

Output:

| Field | Value |
|-------|-------|
| status | completed |
| sections_count | 10 |
| sources_count | 30 |
| used_llm | true |
| llm_model | /Users/master/models/Qwen2.5-14B-Instruct-Q4_K_M.gguf |
| retrieval_provider | llama_cpp |
| retrieval_model | Qwen3-Embedding-4B |
| report_path | data/rag/reports/analyze_tender_0323100010326000013.md |

For the latency-tuning sprint, also verify:

- `analysis_mode`
- `duration_seconds`
- `timings.slowest_sections`

## Report Export Runtime

- Saved markdown reports live under `data/rag/reports/`
- Generated DOCX/PDF exports live under `data/rag/exports/`
- Export endpoints:
  - `/api/tender-research/analyze/history/<analysis_run_id>/export/docx`
  - `/api/tender-research/analyze/history/<analysis_run_id>/export/pdf`
- Export reuses saved `report_markdown` and must not rerun analysis
- PDF generation on Mac mini relies on a local runtime font with Cyrillic support
- `per_section_timings`
- `llm_calls_count`
- `total_context_chars`

### API POST Result

```bash
curl -X POST http://127.0.0.1:8001/api/tender-research/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "registry_number": "0323100010326000013",
    "provider": "llama_cpp",
    "model": "Qwen3-Embedding-4B",
    "base_url": "http://127.0.0.1:8090/v1",
    "use_llm": true,
    "llm_base_url": "http://127.0.0.1:8088/v1",
    "llm_model": "/Users/master/models/Qwen2.5-14B-Instruct-Q4_K_M.gguf",
    "limit": 8,
    "save_report": true
  }'
```

- HTTP 200
- status: completed
- sections_count: 10
- sources_count: 30
- report_markdown: not empty

### Latest Report Endpoint

```
GET /api/tender-research/analyze/0323100010326000013/latest
```

- report_markdown: returned (27091 chars)
- registry_number: correct
- Path traversal: blocked

### Health Endpoint

```
GET /api/tender-research/health
```

- database_url_masked: `postgresql+psycopg://arvectum:***@127.0.0.1:55432/arvectum`
- No secrets leaked
- Table counts returned for all procurement tables

### Demo UI Smoke

**No code changes were required.** The tab was already fully wired.

| Check | Result |
|-------|--------|
| Demo URL | `http://127.0.0.1:8001/demo/tender-agent` |
| Tab "Анализ закупки" present | PASS (data-tab & section both present) |
| Form with registry_number input | PASS |
| Checkboxes (use_llm, save_report) | PASS |
| JS handler `handleAnalysisForm` defined | PASS |
| Background jobs endpoints in fetch JSON calls | PASS (`/api/tender-research/jobs/prepare`, `/api/tender-research/jobs/analyze`) |
| Job status polling endpoint | PASS (`/api/tender-research/jobs/{job_id}`) |
| Report link `GET /latest` or `/history/{run_id}/report` | PASS |
| UI HTML all 9/9 checks | PASS |

The demo UI lives on the same FastAPI backend (port 8001), uses relative URLs,
and needs no CORS setup. The updated form exposes `fast / balanced / detailed`
analysis modes, shows `current_section_title`, and surfaces post-run timing
summary. The full flow — tab display → background job start → polling by
section → result display → history/report link — works without any integration
fixes.

### Background Jobs MVP

Long-running prepare/analyze operations are now available through:

```text
POST /api/tender-research/jobs/prepare
POST /api/tender-research/jobs/analyze
GET  /api/tender-research/jobs/{job_id}
GET  /api/tender-research/jobs
```

Status values:

- `queued`
- `running`
- `completed`
- `completed_with_warnings`
- `failed`
- `cancelled`

Known limitation:

- the runner is in-process;
- active `running` jobs do not survive backend restart as executing tasks;
- job metadata remains queryable from the database.

## Verification Commands

Check PostgreSQL and pgvector:

```bash
./.venv/bin/python -m src.tender_research.cli check-db
```

Check the shared Data Platform instead of a Tender Agent embedding backend:

    curl -fsS http://127.0.0.1:8094/health

Chunking and embeddings are built as part of Tender preparation through Data
Platform. Do not run a local Tender Agent embedding build.
```

Search:

```bash
./.venv/bin/python -m src.tender_research.rag.cli search \
  --query "требования к содержанию и составу заявки" \
  --provider llama_cpp \
  --model Qwen3-Embedding-4B \
  --base-url http://127.0.0.1:8090/v1 \
  --limit 5
```

Eval:

```bash
./.venv/bin/python -m src.tender_research.rag.cli eval \
  --questions tests/fixtures/tender_research/rag_eval_questions.json \
  --provider llama_cpp \
  --model Qwen3-Embedding-4B \
  --base-url http://127.0.0.1:8090/v1 \
  --limit 5
```

Ask with local chat LLM:

```bash
./.venv/bin/python -m src.tender_research.rag.cli ask \
  --registry-number 0323100010326000013 \
  --question "Какие требования к составу заявки?" \
  --provider llama_cpp \
  --model Qwen3-Embedding-4B \
  --base-url http://127.0.0.1:8090/v1 \
  --use-llm \
  --llm-base-url http://127.0.0.1:8088/v1 \
  --llm-model qwen2.5-14b \
  --limit 8
```

Analyze one tender into a markdown report:

```bash
./.venv/bin/python -m src.tender_research.rag.cli analyze-tender \
  --registry-number 0323100010326000013 \
  --provider llama_cpp \
  --model Qwen3-Embedding-4B \
  --base-url http://127.0.0.1:8090/v1 \
  --use-llm \
  --llm-base-url http://127.0.0.1:8088/v1 \
  --llm-model /Users/master/models/Qwen2.5-14B-Instruct-Q4_K_M.gguf \
  --limit 8 \
  --output data/rag/reports/analyze_tender_0323100010326000013.md
```

## Prepare API

Added `POST /api/tender-research/prepare` and
`GET /api/tender-research/prepare/{registry_number}/status`
for the demo preparation flow (MVP, synchronous).

### POST /api/tender-research/prepare

Request:

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

Response (tender already prepared):

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

Response (no tender found):

```json
{
  "status": "no_tender",
  "ready_for_analysis": false,
  "errors": ["Tender 0000000000000000 not found in database and could not be ingested from EIS"]
}
```

**Idempotency:** Repeated calls with `rebuild_chunks=false, rebuild_embeddings=false`
skip existing data. No duplicates created.

### GET /api/tender-research/prepare/{registry_number}/status

Fast readiness check without triggering heavy operations.

Response (ready):

```json
{
  "ready_for_analysis": true,
  "chunks_total": 50,
  "embeddings_total": 50,
  "missing": []
}
```

Response (not ready):

```json
{
  "ready_for_analysis": false,
  "missing": ["chunks", "embeddings"]
}
```

### Demo UI flow

The "Анализ закупки" tab now supports a three-step flow:

1. **Проверить готовность** — calls `GET /prepare/{rn}/status`, shows metrics
2. **Подготовить закупку к анализу** — calls `POST /prepare`, shows per-step status
3. **Проанализировать закупку** — calls `POST /analyze` (unchanged)

Buttons are wired in `src/modules/tender_operator_agent_demo/ui.py`.

### Known limitations

- **MVP synchronous endpoint:** Prepare runs synchronously on the request thread.
  First-time preparation (ingest + download + chunk + embed) may take several minutes.
- **No OCR:** Unsupported document formats (scanned PDFs, images) are skipped.
- **EIS availability:** Ingest depends on external EIS SOAP service availability.
- **No background job queue:** Celery/RQ/Redis are out of scope.
- **Build embeddings requires llama.cpp embedding server** on port 8090.
- **Build chunks requires extracted text** — documents that fail text extraction produce no chunks.
