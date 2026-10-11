# Tender Agent × Data Platform: current ownership and migration audit

**Audited:** 2026-10-11. **Scope:** code and contracts; **not** a production-quality, security, or human-source acceptance certificate.

| Repository | Frozen review revision | Responsibility |
| --- | --- | --- |
| [Tender Agent](https://github.com/arvectum2/tender-agent) | `7c564070e3b830ca829b7ed48b7b39a153e8b170` | Procurement-specific behavior, EIS, supplier/risk/economics decisions and human review |
| [Data Platform](https://github.com/arvectum2/data-platform) | `a8bcd59d9adf0f838a7771bc7d59f63a64512aef` | Reusable retrieval, acquisition, document extraction, provenance, indexing and generic connectors |

This report **supersedes the technical gap inventory** in Data Platform's 2026-10-04 `docs/REUSE_AUDIT.md` *for these two reviewed revisions*. It does not rewrite that historical audit and does not assert that every implemented code path is active in the Mac mini production runtime.

## Established canonical ownership

| Capability / contract | Canonical owner | Verified code seam | Boundary rule |
| --- | --- | --- | --- |
| HTTP/web acquisition, crawl, generic bounded connectors | **Data Platform** | `src/arvectum_data/acquisition/`, `crawl/`, `connectors/` | Business-side site adapters can remain in a product, but transport/URL safety is shared |
| File/URL ingest, extraction, PDF/OCR, chunking | **Data Platform** | `documents/ingest.py`, `documents/extractor.py`, `documents/pdf_pipeline.py`, `processing/chunking.py` | TA `src/shared/document_processing.py` is an HTTP/SDK adapter; it should not reimplement document extraction |
| Collections, resources, documents, chunks, source/provenance, source binary integrity | **Data Platform** | `core/`, `storage/postgres/`, `api/service_mixins/collections.py`, `processing/original_attachment_audit.py` | A DP-stored hash proves consistency with independently supplied bytes, not EIS authenticity by itself |
| Vector indexes and lexical retrieval | **Data Platform** | `indexing/vector_postgres.py`, `search/postgres.py`, `storage/postgres/repository.py` | Collection-scoped, provider/model/dimension-scoped retrieval; no direct product DB table imports |
| Hybrid search, fusion, rerank/expansion contracts | **Data Platform** | `search/hybrid.py`, `search/models.py`, `search/rerank.py`, `search/expansion.py` | Generic ranking is platform-owned; procurement relevance/business decisions are product-owned |
| Versioned search, document and connector API, consumer SDK | **Data Platform** | `api/routes/search_connectors.py`, `api/schemas.py`, `sdk/python/`, `sdk/javascript/` | Consumer wire compatibility takes priority over silently adopting latest incompatible SDK |
| EIS official notice/XML/SOAP/getDocsIP, 44-ФЗ/223-ФЗ regulations | **Tender Agent** | `src/modules/tender_operator_agent_demo/eis_notice_parser.py`, `src/tender_research/providers/public_44fz_search.py`, tender-specific connectors | DP may ingest an attachment generically; only TA validates procurement authority, edition and legal semantics |
| Procurement source graph, field precedence, business fact classification | **Tender Agent** | `src/modules/procurement_source_graph/`, `src/modules/procurement_analysis/` | Source-backed values and conflicts cannot be silently replaced by prompts or inferred supplier assertions |
| Supplier quotes/TКП, bid economics, contract risks | **Tender Agent** | `operator_quote_report.py`, `operator_goods_economics.py`, `operator_non_goods_economics.py`, `operator_risk_report.py` | Missing costs, margin, offer prices or contract facts stay UNKNOWN/needs review |
| Controlled model prompts, procurement-specific output, review gating | **Tender Agent** | `src/modules/controlled_llm_prebid/`, `src/modules/tender_operator_agent_demo/operator_llm_workflow.py` | LLM output is a review candidate; model schema validity does not prove source accuracy |
| Submission, signatures, customer report, pilot control | **Tender Agent** | `src/modules/tender_operator_agent_demo/`, `src/modules/runtime_control_traces/` | No autonomous platform submission, signatures or partner communication without explicit human action |

Paths in the DP rows are relative to `src/arvectum_data/`; TA paths are repository-root relative. This matrix is *ownership of implementation and contracts*, not a claim that the human acceptance gates have already passed.

## Corrections to the older 2026-10-04 reuse audit

The old report identified these gaps **as of its date**; they should no longer be scheduled as greenfield implementations:

- **“No PostgreSQL vector backend” is outdated at the code level.** `indexing/vector_postgres.py` now defines `PostgresVectorIndex` and calls a Postgres repository with collection/model/dimension scoping. Deployment readiness, index data quality and latency on real EIS originals remain separate acceptance tasks.
- **“No first-class hybrid retrieval / SearchHit / search contract” is outdated at the code level.** `search/hybrid.py` contains `HybridSearchEngine`, `search/models.py` contains `SearchHit`, and `api/routes/search_connectors.py` exposes a search route. `tests/search/test_hybrid.py`, `tests/api/test_v1_contract.py` and Postgres integration protect these implementations.
- **Previously suggested TA `tender_research/rag/chunker.py`, `embeddings.py`, `vector_store.py`, `retriever.py` and `indexer.py` are no longer present.** Do not “migrate” nonexistent files again. TA's remaining `tender_research/rag/data_platform.py` is an SDK-backed consumer adapter.
- **The shared document processing seam already delegates to DP.** TA `src/shared/document_processing.py` calls the `DataPlatformHttpClient.process_document` API and projects a product-compatible result. The separate `src/shared/data_platform.py` reexports `arvectum_data_client`; it is *not* a second HTTP transport engine.
- **The consumer SDK remains intentionally pinned** in TA's `pyproject.toml` to the DP release asset `consumer-sdk-v0.3.0`. That is a compatibility/reproducibility decision, not an arbitrary hardcoded internal implementation version. Change after a versioned consumer contract test, not by blind substitution.

**Important distinction:** an implemented, testable backend is **not evidence that the production runtime indexed and served the actual EIS originals**. The authenticated DP SDK contract and synthetic integration results are lower assurance than an independently sourced original document, immutable hash, valid edition, chunk offsets and human-reviewed conclusions.

## Outstanding duplication / coupling

| Area | Current evidence | Decision | Migration gate |
| --- | --- | --- | --- |
| TA generic web research fetchers | `src/tender_research/browser/requests_fetcher.py` and `playwright_fetcher.py` still implement bounded acquisition while DP owns generic acquisition | **Candidate replacement** by DP connector/acquisition adapter, *not* immediate deletion | URL allowlist/SSRF, redirects, timeouts, content-type, size, HTML readability and existing product results parity |
| TA `src/tender_research/pipeline.py` | Still instantiates TA `RequestsFetcher` by default | **Keep coordinator**, replace transport via explicit interface only | Existing research and browser parity tests; offline mock and failure-mode behavior |
| TA `src/shared/document_processing.py` | Already a typed TA projection over DP consumer HTTP SDK | **Keep compatibility facade**; no duplicated extractor to remove | SDK wire-schema, source/hash/offset parity and consumer-facing tests |
| TA `upload_service_legacy.py` | **3,975 lines** at audited revision | **Strangler extraction**, with old import/call facade retained while splitting pure product projections | Full Python regression; AST/equivalent-output checks; independent new tests; no fast big-bang rewrite |
| TA product reports/source graph vs DP provenance | TA can assemble domain-sensitive claims; DP stores generic source identities | **Do not merge domain graph into DP** | Every rendered fact resolves to authorized resource/document/chunk + original evidence; UNKNOWN must survive |
| Model runtime vs quality judgement | Local non-stub four-section TA synthetic workflow was tested separately | **Keep technical-smoke and gold-quality verdicts distinct** | Independently labeled authoritative EIS corpus and per-model source-grounded accuracy, latency and failure rate |

## Cross-repo dependency contract

1. **TA → DP only over released SDK and authenticated API.** Keep `src/shared/data_platform.py` as compatibility facade. Avoid importing `arvectum_data` server internals, DP SQLAlchemy ORM tables or local DP code directly into TA runtime.
2. **DP must remain product-neutral.** A `SearchHit`, chunk, resource or connector must not depend on 44-ФЗ, supplier names or bid economics. TA owns interpretation, provenance-ordered procurement facts and review decisions.
3. **Data boundary and failure policy:** secrets stay in env/runtime configuration; missing DP credentials should fail closed (not fallback to an apparently authoritative source); unauthorized HTTP 401 is not a successful business result.
4. **Original evidence boundary:** original binary SHA-256, canonical source URL and official notice revision are verified from an **independent, authorized source**; persisted DP values and chunk hashes alone cannot prove EIS originality. Later report cites resource/document/chunk ID and exact text locator when available.
5. **Report boundary:** only supported claims become sourced facts. Incomplete contract terms, unknown delivery dates, missing ТКП or unknown economics remain explicitly unknown. Final recommendations always require human approval.

## Proposed execution order and acceptance gates

| Phase | Bounded deliverable | Verification / done gate |
| --- | --- | --- |
| **R3 product projections** | Continue extracting report sections from `upload_service_legacy.py` while preserving old facade and explicit source precedence | AST/behavior parity, adversarial UNKNOWN tests, local full pytest, exact-head quality, Docker, migrations, Redis, PostgreSQL, security GitHub CI |
| **R2 independent source proof** | Obtain legally authorized EIS original attachments and exact notice editions; compare binary SHA, resource/document/chunk IDs, offsets and official URI | Independent source proof, read-only DP authenticated query, mismatches fail closed; no silent “verified” on missing originals |
| **R3 generic acquisition parity** | Replace TA research fetcher implementation with DP connector adapter **only if** every existing failure/safety behavior is preserved | Cross-repo contract tests, old/new output parity on a bounded corpus, no secrets or credential transmission to untrusted hosts |
| **R4 model benchmark** | Use source-locked identical real procurement inputs for qwen2.5:3b, qwen3:4b and other candidates | Numeric/source fidelity, hallucination rate, UNKNOWN retention, schema pass, cost/latency/review workload; synthetic timing alone cannot rank quality |
| **R5 independently reviewed acceptance** | Review at least 20 original EIS procurements spanning goods/services/IT cases | Qualified human signs each source/claim comparison; product owner accepts go/no-go before private/production pilot |
| **Operational rollout** | Migrate only after R2–R5 pass | Same deployed commit/hash, authenticated DP API/SDK contract, backups/rollback, read-only dry run, owner approval |

## Non-goals and explicit unknowns

No attempt is made here to claim that EIS source retrieval, 20+ independently human-reviewed procurements, full real model accuracy, production rollout, or owner approval have happened. The checkpoint `.agent/current-task.yaml` must remain `in_progress` until those independent gates are actually satisfied. The owner-disabled Tender Agent watchdog remains disabled, and this audit is docs-only, with no production/service changes.
