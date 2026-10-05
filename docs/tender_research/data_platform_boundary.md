# Data Platform boundary

Tender Agent is a consumer of Arvectum Data Platform.

## Data Platform owns

- document text extraction and normalization;
- chunking;
- embeddings;
- lexical, vector and hybrid retrieval;
- generic indexing and reindex lifecycle;
- reusable Resource / Document / Chunk / Provenance models;
- generic ingestion, deduplication, retries and storage primitives;
- generic search, filter and ranking primitives.

## Tender Agent owns

- EIS, 44-FZ and 223-FZ integration and semantics;
- procurement-document interpretation;
- participant requirements and application composition;
- Decision Core, Commercial Core and GO/NO-GO;
- supplier/tender compatibility;
- procurement rules and evidence mapping;
- tender-specific reports.

The dependency direction is Tender Agent -> Data Platform. Data Platform must not import Tender Agent or procurement-specific logic.

Data Platform performs extraction/chunking and Tender Agent stores a local projection of returned chunks only to preserve stable procurement evidence references used by existing Decision Core/reporting code. The former local extractor/chunker/embedding/vector stack has been removed.


## Document recovery chunk rebuilding

The production recovery path delegates both staged text extraction and chunk rebuilding to Data Platform. Tender Agent verifies that Data Platform extraction matches the already recovered and validated extracted text before writing returned chunks into procurement storage. No local generic extractor or chunk indexer remains in Tender Agent.

## Runtime import boundary

The normal Data Platform preparation and analysis paths do not import a local
document extractor, embeddings implementation, vector store, chunk indexer or
retriever stack because those generic modules no longer exist in Tender Agent.
Backend-neutral retrieval results live in rag.search_types, so Data Platform
integration and Tender Agent domain/LLM code remain separated.

## Legacy generic RAG removal

The local Tender Agent chunker, embedding providers, JSON vector store, retriever,
and generic indexer have been removed. Data Platform is the only supported
retrieval backend. Historical CLI entry points for local chunk/embedding builds
remain temporarily as deprecation notices only; they do not execute local RAG.

## Document extraction boundary

Tender Agent no longer contains a format-specific document extractor. Download
and procurement-domain quality gates remain local, but raw document bytes are
sent to Data Platform through the thin shared document-processing adapter.
The ARV-001 acceptance path also consumes Data Platform-returned chunks instead
of constructing a second local chunking implementation.

## Consumer SDK boundary

Tender Agent and Arvectum OS no longer implement their own Data Platform HTTP
transport. The compatibility import src.shared.data_platform re-exports the
standalone arvectum-data-client SDK pinned to a released wheel with a hash-locked
dependency. Product-specific adapters may choose ranking weights and map search
hits into procurement or knowledge-asset domain objects, but HTTP paths,
authentication headers, multipart encoding, error behavior and generic contract
types belong to the shared SDK.
