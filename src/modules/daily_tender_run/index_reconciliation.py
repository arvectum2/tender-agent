"""Pure reconciliation of an existing tender collection against local chunks.

This verifies persisted source/document hashes and the collection's embedding
contract. The caller is responsible for authenticated read-only evidence and
must not treat this inventory as permission to ingest or overwrite resources.
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingContract:
    provider: str
    model: str
    dimension: int

    def __post_init__(self):
        if (
            not self.provider
            or not self.model
            or type(self.dimension) is not int
            or self.dimension <= 0
        ):
            raise ValueError("incomplete collection embedding contract")


@dataclass(frozen=True)
class StoredChunk:
    uri: str
    resource_hash: str
    document_hash: str | None
    chunk_hash: str | None
    embedding: EmbeddingContract | None


def reconcile(chunks, rows: list[StoredChunk], contract: EmbeddingContract) -> dict:
    expected = {}
    for chunk in chunks:
        uri = "tender-chunk://" + str(chunk.id)
        if uri in expected or not chunk.text or not str(chunk.id):
            raise ValueError("invalid or duplicate local chunk")
        expected[uri] = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.uri].append(row)
    decisions = {}
    for uri, digest in expected.items():
        matches = grouped.get(uri, [])
        if not matches:
            decisions[uri] = "absent_resource"
        elif len(matches) != 1:
            decisions[uri] = "identity_conflict"
        else:
            m = matches[0]
            if (
                m.resource_hash != digest
                or m.document_hash != digest
                or not m.chunk_hash
            ):
                decisions[uri] = "identity_conflict"
            elif m.embedding is None:
                decisions[uri] = "missing_embedding"
            elif m.embedding != contract:
                decisions[uri] = "model_conflict"
            else:
                decisions[uri] = "verified_resource"
    unexpected = sorted(set(grouped) - set(expected))
    counts = dict(Counter(decisions.values()))
    # Existing resources without embeddings need the platform's supported
    # repair contract; they must not be silently treated as absent resources.
    unambiguous = not unexpected and not any(
        counts.get(k, 0)
        for k in ("identity_conflict", "model_conflict", "missing_embedding")
    )
    return {
        "expected_count": len(expected),
        "counts": counts,
        "unexpected": unexpected,
        "eligible_absent_uris": sorted(
            uri for uri, status in decisions.items() if status == "absent_resource"
        )
        if unambiguous
        else [],
        "complete": bool(expected)
        and unambiguous
        and counts.get("verified_resource", 0) == len(expected),
        "requires_review": not unambiguous,
    }
