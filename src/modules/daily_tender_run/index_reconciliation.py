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
                or m.chunk_hash != digest
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


@dataclass(frozen=True)
class IndexSnapshot:
    collection_id: str
    contract: EmbeddingContract
    rows: tuple[StoredChunk, ...]


def repair_absent_batch(
    *,
    repo,
    client,
    tender_id: str,
    collection_id: str,
    expected_contract: EmbeddingContract,
    read_snapshot,
    admitted_write,
    limit: int = 10,
) -> dict:
    """Bounded repair core for a reviewed operator runner, not a live CLI.

    The caller must implement authenticated independent snapshots and a real
    context manager for mandatory prewrite backup, identity and source locks.
    The core does not grant admission. Never treat an interrupted API response
    as success or immediately retry it; independently reconcile before resume.
    """
    from src.tender_research.rag.data_platform import build_tender_collection_id

    if type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError("invalid repair batch limit")
    if not collection_id:
        raise ValueError("existing collection required")

    def inventory():
        if build_tender_collection_id(repo, tender_id) != collection_id:
            raise ValueError("local collection revision changed")
        chunks = repo.list_chunks_by_tender(tender_id)
        if not chunks:
            raise ValueError("no local chunks")
        snapshot = read_snapshot(collection_id)
        if (
            snapshot.collection_id != collection_id
            or snapshot.contract != expected_contract
        ):
            raise ValueError("collection identity or embedding contract changed")
        reconciled = reconcile(chunks, list(snapshot.rows), expected_contract)
        if reconciled["requires_review"]:
            raise ValueError("collection evidence requires review")
        return chunks, reconciled

    with admitted_write() as admitted_limit:
        if type(admitted_limit) is not int or not 1 <= admitted_limit <= 10:
            raise RuntimeError("invalid admitted resource batch limit")
        _, first = inventory()
        targets = first["eligible_absent_uris"][: min(limit, admitted_limit)]
        verified = []
        for uri in targets:
            chunks, current = inventory()
            if uri not in current["eligible_absent_uris"]:
                # A previously interrupted or concurrent successful ingest was
                # already reconciled by the exact identity checks.
                continue
            chunk = next(ch for ch in chunks if "tender-chunk://" + str(ch.id) == uri)
            client.ingest_chunk(
                collection_id=collection_id,
                chunk_id=chunk.id,
                file_name=chunk.source_file_name or f"{chunk.document_id}.txt",
                text=chunk.text,
            )
            _, after = inventory()
            if uri in after["eligible_absent_uris"]:
                raise RuntimeError(
                    "ingest response has no independently verified resource"
                )
            verified.append(uri)
        _, final = inventory()
    return {
        "verified_added": verified,
        "remaining": len(final["eligible_absent_uris"]),
        "complete": final["complete"],
    }
