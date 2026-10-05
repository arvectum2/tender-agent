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

For the current migration phase, Data Platform performs extraction/chunking and Tender Agent stores a local projection of returned chunks only to preserve stable procurement evidence references used by existing Decision Core/reporting code. The legacy local extractor/chunker/embedding/vector stack remains compatibility-only and must not be used by the data_platform backend.


## Document recovery chunk rebuilding

The production recovery path delegates both staged text extraction and chunk rebuilding to Data Platform. Tender Agent verifies that Data Platform extraction matches the already recovered and validated extracted text before writing returned chunks into procurement storage. The local extractor and legacy local chunk indexer remain test/compatibility code only and are no longer production recovery defaults.
