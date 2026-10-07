# Troubleshooting

## 1. Backend не отвечает на 8001

Проверить:

```bash
curl http://127.0.0.1:8001/api/tender-research/health
```

Что делать:

- проверить, что backend-процесс запущен;
- при необходимости перезапустить backend;
- повторно проверить health.

Полезные команды:

```bash
lsof -nP -iTCP:8001 -sTCP:LISTEN
tail -n 40 /tmp/ai_corp_uvicorn_8001.log
set -a && source .env.prod >/dev/null 2>&1 && set +a
nohup ./.venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8001 --proxy-headers >/tmp/ai_corp_uvicorn_8001.log 2>&1 &
```

## 2. DB смотрит не туда

Симптом:

- backend внезапно работает через SQLite вместо PostgreSQL;
- health или alembic показывают не тот контур.

Что делать:

- загрузить правильный `.env.prod` или runtime env;
- убедиться, что используется `AI_CORP_DATABASE_URL` для PostgreSQL;
- повторно проверить health.

Типичный симптом:

- health показывает `database_dialect=sqlite` вместо `postgresql`.

## 3. Data Platform недоступна

Проверить:

    curl -fsS http://127.0.0.1:8094/health

Если health не отвечает, восстановить runtime Data Platform. Tender Agent
больше не имеет отдельного локального embedding/vector backend.


## 4. LLM server недоступен

Проверить:

```bash
curl -s http://127.0.0.1:8088/v1/models
```

Что делать:

- проверить `8088`;
- проверить `model id`;
- проверить путь к GGUF.

## 5. Анализ идёт долго

Что делать:

- использовать `fast` mode;
- смотреть progress по секциям;
- не перезапускать без причины;
- объяснить, что локальная LLM работает без облака.

## 6. `sources_count=0`

Что проверить:

- chunks и embeddings;
- retrieval;
- корректность `registry_number`.

Полезная проверка:

```bash
curl "http://127.0.0.1:8001/api/tender-research/analyze/history?registry_number=0323100010326000013&limit=5"
```

## 7. DOCX не скачивается

Проверить:

```bash
curl -OJ http://127.0.0.1:8001/api/tender-research/analyze/history/<run_id>/export/docx
```

И:

- export endpoint;
- права на `data/rag/exports/`.

## 8. PDF не читается / проблемы с кириллицей

Проверить:

- локальный шрифт с кириллицей;
- `reportlab` / font config;
- в качестве fallback использовать DOCX.

## 9. History run не экспортируется

Проверить:

- существует ли исходный saved report file;
- history row не orphaned.

Важно:

- orphaned history rows могут давать `404`.

## 10. Report или history открываются, а export нет

Проверить:

```bash
curl "http://127.0.0.1:8001/api/tender-research/analyze/history?registry_number=0323100010326000013&limit=5"
curl http://127.0.0.1:8001/api/tender-research/analyze/history/<run_id>/report
curl -OJ http://127.0.0.1:8001/api/tender-research/analyze/history/<run_id>/export/pdf
```

Если report открывается, а export падает:

- проверить наличие saved markdown;
- проверить права на `data/rag/exports/`;
- проверить локальный шрифт для PDF.

## 11. Приоритет источника данных

Приоритетным источником структурированных данных является электронное извещение (epNotification XML). Метаданные карточки поиска используются как fallback, а прикреплённые документы — для детального анализа. В случае конфликта данных приоритет имеет извещение ЕИС. Даты в мастере отображаются в формате ДД.ММ.ГГГГ, НМЦК — в рублях с разделителями тысяч. В отчётах источник данных маркируется как «электронное извещение ЕИС» или «карточка ЕИС».
