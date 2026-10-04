# Data Platform Knowledge Assets Search

## Scope

This integration adds bounded retrieval over existing Arvectum OS `KnowledgeAssetRecord` data.

It does **not** open autonomous M-049/M-050 runtime behavior. Agent registry and prompt/schema execution remain governed by their existing boundaries.

## Ownership

Arvectum OS remains the source of truth for:

- `KnowledgeAssetSet`;
- `KnowledgeAssetRecord`;
- `KnowledgeAssetLink`;
- `deal_id` ownership and access boundaries.

Data Platform owns only the reusable search index and hybrid retrieval.

## Collection model

Each deal receives a deterministic versioned collection:

```text
arvectum-os:knowledge:<deal_id>:<revision>
```

The revision changes when indexed knowledge asset content changes.

Search always targets the current collection for exactly one `deal_id`. There is no cross-deal fallback.

## Canonical mapping

Each indexed record uses:

```text
arvectum-os-knowledge://<knowledge_asset_id>
```

Search hits are mapped back to the current Arvectum OS database record before being returned. Hits that do not belong to the requested deal are ignored.

## API

Explicit indexing:

```text
POST /knowledge-assets/index
{"deal_id":"..."}
```

Bounded retrieval:

```text
POST /knowledge-assets/search
{"deal_id":"...","query":"...","limit":10}
```

Search fails closed when the current versioned collection has not been prepared.

## Rollout status

A live synthetic acceptance against the production Data Platform service on 2026-10-04 verified:

```text
1 KnowledgeAssetRecord
-> versioned Arvectum OS collection
-> pre-chunked ingest
-> 1 chunk
-> 1 embedding
-> hybrid search
-> canonical knowledge_asset_id
-> source refs
```

The production Arvectum OS database contained no real `KnowledgeAssetRecord` rows at acceptance time, so real-data production acceptance remains pending until the first knowledge asset is built.
