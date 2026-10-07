# Tender RAG via Data Platform

Tender Agent no longer owns a local generic RAG stack. Document extraction,
chunking, embeddings, vector/lexical/hybrid retrieval and generic index
lifecycle are provided by the shared Data Platform.

## Runtime contract

Tender Agent must use these settings:

    AI_CORP_RAG_RETRIEVAL_BACKEND=data_platform
    AI_CORP_RAG_DATA_PLATFORM_BASE_URL=http://127.0.0.1:8094
    AI_CORP_RAG_DATA_PLATFORM_API_KEY=
    AI_CORP_RAG_DATA_PLATFORM_TIMEOUT_SECONDS=30

The legacy backend is not supported.

The dependency direction is one-way:

    Tender Agent -> Data Platform

Procurement-specific models, evidence binding, Decision Core, Commercial Core,
GO/NO-GO logic and tender reports remain in Tender Agent.

## Health

Check Data Platform directly:

    curl -fsS http://127.0.0.1:8094/health

A healthy Tender Agent preparation additionally requires a complete Data
Platform collection for the tender.

## Prepare a tender

Preferred asynchronous API:

    POST /api/tender-research/jobs/prepare

Synchronous API:

    POST /api/tender-research/prepare

Readiness:

    GET /api/tender-research/prepare/{registry_number}/status

Preparation performs the full generic pipeline through Data Platform:
downloaded document -> extraction -> chunk projection -> Data Platform
indexing/embeddings -> readiness check.

## Search and analysis

The existing Tender Research CLI search, ask, eval, and analyze-tender commands
now retrieve through Data Platform hybrid search. They report
retrieval_provider=data_platform and retrieval_model=hybrid.

The historical commands build-chunks, build-embeddings, and
check-embedding-server are retained temporarily only as migration notices.
They do not create local chunks, embeddings, or JSON vector indexes.

## Local compatibility projection

Tender Agent still stores procurement-domain chunk projections so evidence
references and downstream procurement workflows retain stable local IDs.
Those rows are not an independent generic search index; Data Platform owns
generic processing and retrieval.

## Recovery

Document recovery also delegates generic extraction and chunk construction to
Data Platform. Recovery-specific validation, evidence identity and persistence
rules remain Tender Agent responsibilities.
