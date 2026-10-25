# MI-006 — Data Platform-native terminology-aware technical search

**2026-10-25 | Internal architecture milestone, draft PRs only.**
Canonical checkpoint: `.agent/current-task.yaml` and `.agent/checkpoints/MI-006-DP-TERMINOLOGY-20261025.yaml`.

## Ownership and boundaries

| Layer | Owns | Does not own |
|---|---|---|
| **Data Platform** (`arvectum2/data-platform`) | Generic tenant-approved hybrid lexical+vector retrieval, ontology group schema, bounded deterministic synonym expansion, ambiguous acronym context and exclusions, source-chunk term annotations, ranking/federation and dedup, consumers/ACL/quotas | Any specific industry or product taxonomy; legal award/contract claims |
| **Market Intelligence** (module of `arvectum2/tender-agent`) | Power Quality vocabulary and human hypotheses, source qualification and SHA review, EPC/buyer/designer/supplier role assertions, contract financial separation, reports and commercial recommendations | Generic query-synonym expansion or ranking implementation |
| **Tender Agent** | Procurement-specific research runs, orchestration and human evidence review, source-bound procurement protocols | A second search index or new hybrid search engine |

The Power Quality ontology remains a **versioned domain plug-in**, supplied to the generic Data Platform search API **as request-scoped data**. It does not need a Power Quality code branch inside Data Platform. Another product could send a medical, logistics or construction ontology using the same API and ranking implementation.

## Wire contract

Data Platform: `POST /v1/search` with `terminology_groups`, `terminology_expansion_limit`, and `terminology_version` (e.g. `power-quality-ontology/0.1`). The new DP service advertises `terminology_search_v1` in authenticated `GET /v1/contract`. The new SDK v0.4.0 supports those parameters. The server preserves original `document_id`, `chunk_id`, `canonical_uri`, and `evidence`; `hits[].metadata.terminology_matches` is a list of generic candidate tags. Search remains bounded, ACL-checked and ranked by Data Platform.

MI `search_demand` now:

1. Validates consumer-selected `families` against local Power Quality ontology and source collection allowlist populated from trusted tenant policy.
2. Checks Data Platform's authenticated capability contract **before** any term-based search. An older server which silently discards new JSON fields causes a fail-closed error.
3. Sends the selected domain family as a terminology group (aliases, context, exclusions, ambiguous aliases), the ontology version, and the **original** technical query, with `expand_query=False`; **no handwritten `query_variants`** or fallback shadow search.
4. Reads `terminology_matches` from Data Platform hit metadata. If Data Platform identifies explicit technical equipment, MI classifies it as an explicit **candidate**; otherwise only a `semantic_candidate_requires_manual_review`. This never proves a signed contract, equipment supply, EPC role, winner or market value.
5. Applies existing source URL/chunk and optional independently reviewed SHA-256 checks to determine source grade. Data Platform's own indexed SHA is still not an independent original-document audit.

Legacy `technical_matching.py` is currently retained for **offline** SOAP archive lexical discovery and supplier-portfolio hypothesis summarization, not for querying the search index, expanding retrieval synonyms, ranking, or corpus dedup. Deleting the offline lexical fallback requires a separately reviewed Data Platform batch-classification/offline SDK strategy; it is not safe to make SOAP corpus scanning depend on a network API during an outage.

## Upgrade order (not yet executed in production)

1. Review/merge/deploy **Data Platform generic terminology PR #127**, including authenticated capability `terminology_search_v1`; separately review PPTX-format PR #126.
2. Install Data Platform Python SDK **v0.4.0** into trusted Tender Agent/MI runtime. Existing installed SDK v0.3 does not accept `terminology_groups`; the new adapter raises explicit `PortfolioInputError` instead of silently using old search.
3. Accept the Data Platform collection/consumer/tenant policies, source preservation and live indexing in a restricted test environment; repeat owner and cross-tenant tests, then run independently labelled real EPC technical annexes.
4. Review MI-006 dependent branch PR; then enable the user-visible search workflow. No live customer research claim before the collected sources and actual protocols are verified.

The *code and tests* are ready for review. The actual production Data Platform service has **not** been upgraded.

## Verified results / limitations

- Generic Data Platform terminology tests include medicine (`МРТ/MRI`), Power Quality (`STATCOM/СТАТКОМ/SVG`), non-electric SVG graphics, exclusions, context/ambiguous terms, phrase constraints preserved, tenant quota and execution modes, old search compatibility and SDK HTTP contract.
- 12/12 **previously curated PQ procurement descriptions** matched their expected family when the new Data Platform matcher read the existing source descriptions. This only proves vocabulary compatibility on the small, pre-selected sample. It is not real 36-month historical completeness or top-K recall on hidden technical annexes.
- MI-006 test adapter uses the new actual SDK via isolated SDK source path and `httpx.MockTransport`; other MI offline tests still use the already-installed SDK v0.3, where the new SDK-only contract test is explicitly skipped. It will run again once v0.4 is installed.
- No EIS token or SOAP transport changes, no live site crawl, no customer PII ingestion, no contact outreach. SOAP recovery remains in independent PR #503; it does not block this architectural work.
- Data Platform currently accepts **request-scoped versioned ontologies**. A server-persistent catalogue/ontology CRUD/editor is **not implemented**. Keeping domain vocabularies versioned in client repos is deliberate until a multi-tenant registry and authorization policy is designed.

## SDK release integration (25 October 2026)

The DP main integration PR #128 is **merged** as `d341731664bdc4bc6bb5e8fdeef3df00706c72bd`. Versioned Python wheel `arvectum_data_client-0.4.0-py3-none-any.whl` is published at `https://github.com/arvectum2/data-platform/releases/tag/consumer-sdk-v0.4.0`, verified SHA-256 `51906ad978023c9acdefd48eb68c658012d17c28dc31acb476c9cd1b2f835b67`.

Tender Agent now pins the exact official wheel URL in `pyproject.toml` and locks its SHA in `requirements.lock`; the source branch and wheel-based independent acceptance have passed. **Merge to main != production service deployment:** DP live tenant/auth/RAG server still must advertise `terminology_search_v1` for MI search to execute, or MI will fail closed; do not disable this gate.

SDK code is backward compatible with older consumers. Historical EIS source retrieval and real contractor/winner verification are not resolved by this release.
