# PostgreSQL + pgvector for Arvectum

Mac mini is the server contour and source of truth for Arvectum, so the durable database should live there. SQLite remains the default for tests and lightweight local development because it keeps the suite fast, removes infrastructure requirements for everyday coding, and matches the existing in-memory pytest setup.

## Why this split exists

- Mac mini runs the long-lived server pipeline, so it should use PostgreSQL.
- SQLite stays in place for unit tests and local prototyping.
- `data/tenders`, extracted texts, and local JSON vector files remain filesystem artifacts outside PostgreSQL.
- `pgvector` is enabled now, but the schema does not yet include a fixed-dimension `vector(N)` column because the production embedding model is not finalized.

## 1. Start PostgreSQL with pgvector

Use local-only secrets in `.env.local` and keep them out of git:

```env
AI_CORP_DATABASE_URL=postgresql+psycopg://arvectum:CHANGE_ME@127.0.0.1:5432/arvectum
ARVECTUM_POSTGRES_DB=arvectum
ARVECTUM_POSTGRES_USER=arvectum
ARVECTUM_POSTGRES_PASSWORD=CHANGE_ME
```

Start the container:

```bash
docker compose -f docker-compose.postgres.yml up -d
```

Check the database wiring:

```bash
python -m src.shared.db.cli check-db
python -m src.tender_research.cli check-db
```

Expected fields include:

- `database_dialect: postgresql`
- `database_url_masked: postgresql+psycopg://...`
- `can_connect: True`
- `migration_head: ...`
- `pgvector_extension_available: True`

## 2. Run migrations

Apply the schema on Mac mini after `AI_CORP_DATABASE_URL` points to PostgreSQL:

```bash
alembic upgrade head
python -m src.tender_research.cli check-db
```

Revision `090_enable_pgvector_and_add_rag_tables` enables `CREATE EXTENSION IF NOT EXISTS vector` on PostgreSQL and creates the RAG chunk/embedding metadata tables without locking the schema to a specific vector dimension.

## 3. Recommended rebuild path

The live dataset is still small, so rebuild from sources is the recommended path right now instead of writing a dedicated SQLite-to-Postgres migrator.

Run on Mac mini:

```bash
python -m src.tender_research.cli research-discovered \
  --source external_public_44fz \
  --days-back 7 \
  --limit 30 \
  --page-size 30

python -m src.tender_research.cli backfill-public-metadata \
  --limit 50 \
  --only-placeholders

python -m src.tender_research.cli document-quality-report \
  --limit 100

# Generic chunking and embeddings now belong to Data Platform.
curl -fsS http://127.0.0.1:8094/health

python -m src.tender_research.rag.cli search \
  --query "требования к содержанию и составу заявки" \
  --limit 10
```

Repeat the domain ingestion/backfill steps and Tender preparation once more to confirm idempotence. Data Platform owns chunk/index/embedding idempotence.

Healthy rebuild signals:

- `tenders_total > 0`
- `documents_total > 0`
- `extracted_texts_total > 0`
- `chunks_created > 0`
- repeated runs do not create duplicate tenders, documents, or chunks

## 4. Stats and diagnostics

Use these checks after rebuild:

```bash
python -m src.tender_research.cli stats
python -m src.tender_research.cli document-quality-report --limit 100
python -m src.tender_research.cli check-db
```

## 5. Optional PostgreSQL integration tests

Default pytest remains SQLite-first. PostgreSQL checks are opt-in:

```bash
pytest -m postgres
```

If the default suite overrides `AI_CORP_DATABASE_URL` to SQLite, provide a dedicated Postgres URL explicitly:

```bash
export AI_CORP_POSTGRES_TEST_DATABASE_URL="postgresql+psycopg://arvectum:CHANGE_ME@127.0.0.1:5432/arvectum"
pytest -m postgres
```

## 6. Backup and restore

Create a logical backup:

```bash
pg_dump \
  --dbname="postgresql://arvectum:CHANGE_ME@127.0.0.1:5432/arvectum" \
  --format=custom \
  --file=backup-arvectum.dump
```

Restore from backup:

```bash
pg_restore \
  --clean \
  --if-exists \
  --dbname="postgresql://arvectum:CHANGE_ME@127.0.0.1:5432/arvectum" \
  backup-arvectum.dump
```

For plain SQL dumps:

```bash
psql "postgresql://arvectum:CHANGE_ME@127.0.0.1:5432/arvectum" < backup-arvectum.sql
```

## 7. Future migration path

If SQLite contains data worth preserving later, treat that as a separate task:

- export the relevant SQLite entities
- import them into PostgreSQL with explicit mapping rules
- only then decide on the final `pgvector` storage shape

For now, the intended path is PostgreSQL rebuild from source data plus filesystem artifacts in `data/`.
