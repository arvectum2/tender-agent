# Runtime checklist для Mac mini

Проверка за 3–5 минут перед созвоном.

## 1. Git

- HEAD на актуальном `main`
- `git status` без неожиданных tracked changes

Ожидаемый ориентир:
- `origin/main = 8eec85516b690b6f58d80ea9d26fe6d3d708bb9c`

## 2. DB

Проверить health:

```bash
curl http://127.0.0.1:8001/api/tender-research/health
```

Ожидаем:

- PostgreSQL `127.0.0.1:55432`
- `pgvector_extension_available=true`
- `current_migration=092_create_tender_analysis_jobs_table`
- `migration_head=092_create_tender_analysis_jobs_table`

## 3. Backend

```bash
curl http://127.0.0.1:8001/api/tender-research/health
```

Ожидаем:

- HTTP 200
- `status=ok`
- `can_connect=true`

Если backend не отвечает:

```bash
lsof -nP -iTCP:8001 -sTCP:LISTEN
tail -n 40 /tmp/ai_corp_uvicorn_8001.log
```

## 4. Data Platform

    curl -fsS http://127.0.0.1:8094/health

Tender preparation calls Data Platform for chunking, embeddings and indexing;
Tender Agent does not maintain a separate embedding backend.


## 5. LLM

```bash
curl -s http://127.0.0.1:8088/v1/models
```

Ожидаем:

- endpoint `http://127.0.0.1:8088/v1`
- model `/Users/master/models/Qwen2.5-14B-Instruct-Q4_K_M.gguf`

## 6. UI

Открыть:

`http://127.0.0.1:8001/demo/tender-agent`

Проверить:

- страница загружается;
- вкладка `Анализ закупки` есть;
- preset `Mac mini: локальная LLM + Qwen3 embeddings` доступен.

## 7. Export

Проверить на свежем или историческом run:

- DOCX download работает;
- PDF download работает;
- PDF Cyrillic readable.

Рекомендуемый historical run для быстрой проверки:

- `7b29f717-13d6-4dc9-9764-79ba17cbf0e3`
