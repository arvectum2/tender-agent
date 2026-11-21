"""Independent read-only PostgreSQL evidence for an operator recovery plan.

Data Platform remains the only writer of its collections and embeddings.
The explicit engine must be supplied by the admitted host runtime. No
database discovery, schema creation, credential fallback or write SQL.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.modules.daily_tender_run.index_reconciliation import (
    EmbeddingContract,
    IndexSnapshot,
    StoredChunk,
)

_COLLECTION = text("""
    SELECT owner, embedding_provider, embedding_model, embedding_dimension,
           active_index_revision
    FROM dp_collections WHERE collection_id=:cid
""")
_ROWS = text("""
    SELECT r.canonical_uri, r.content_hash AS resource_hash, r.status,
           d.content_hash AS document_hash, d.text AS document_text,
           d.extraction_status, k.content_hash AS chunk_hash,
           k.text AS chunk_text, k.ordinal,
           e.provider, e.model, e.dimension, vector_dims(e.vector) AS vector_dimension
    FROM dp_resources r
    LEFT JOIN dp_documents d ON d.resource_id=r.resource_id
    LEFT JOIN dp_chunks k ON k.document_id=d.document_id
    LEFT JOIN dp_chunk_embeddings e ON e.chunk_id=k.chunk_id
    WHERE r.collection_id=:cid
    ORDER BY r.canonical_uri LIMIT 10001
""")


def _digest(value):
    return (
        hashlib.sha256(value.encode("utf-8")).hexdigest()
        if isinstance(value, str)
        else None
    )


def _row_evidence(row):
    # No content leaves the verifier, just exact identity and evidence hashes.
    if row["status"] != "ready":
        raise ValueError("resource is not ready")
    doc_hash = row["document_hash"]
    chunk_hash = row["chunk_hash"]
    if doc_hash is not None and (
        row["extraction_status"] != "extracted"
        or _digest(row["document_text"]) != doc_hash
    ):
        raise ValueError("persisted document bytes disagree with evidence")
    if chunk_hash is not None and (
        row["ordinal"] != 0 or _digest(row["chunk_text"]) != chunk_hash
    ):
        raise ValueError("persisted pre-chunked text disagrees with evidence")
    contract = None
    if row["provider"] is not None:
        contract = EmbeddingContract(row["provider"], row["model"], row["dimension"])
        if row["vector_dimension"] != contract.dimension:
            raise ValueError("embedding vector dimension mismatch")
    elif any(
        row[key] is not None for key in ("model", "dimension", "vector_dimension")
    ):
        raise ValueError("partial embedding identity")
    return StoredChunk(
        row["canonical_uri"], row["resource_hash"], doc_hash, chunk_hash, contract
    )


@dataclass(frozen=True)
class PostgresIndexReader:
    engine: Engine
    expected_system_identifier: str

    def __call__(self, collection_id: str) -> IndexSnapshot:
        if (
            self.engine.dialect.name != "postgresql"
            or not collection_id
            or len(collection_id) > 128
        ):
            raise ValueError("invalid Data Platform collection reader binding")
        with self.engine.connect() as conn:
            conn.execute(
                text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            )
            try:
                identity = conn.execute(
                    text(
                        "SELECT current_database(), system_identifier::text FROM pg_control_system()"
                    )
                ).one()
                if tuple(identity) != (
                    "arvectum_data",
                    self.expected_system_identifier,
                ):
                    raise ValueError("Data Platform database identity mismatch")
                row = (
                    conn.execute(_COLLECTION, {"cid": collection_id})
                    .mappings()
                    .one_or_none()
                )
                if row is None or row["owner"] != "tender-agent":
                    raise ValueError("existing owned collection required")
                # This repair contract covers the deployed legacy/direct
                # pre-chunked index only. Other index revisions need review.
                if row["active_index_revision"] is not None:
                    raise ValueError("versioned index requires separate reconciliation")
                contract = EmbeddingContract(
                    row["embedding_provider"],
                    row["embedding_model"],
                    row["embedding_dimension"],
                )
                values = conn.execute(_ROWS, {"cid": collection_id}).mappings().all()
                if len(values) > 10000:
                    raise ValueError("snapshot evidence limit exceeded")
                return IndexSnapshot(
                    collection_id, contract, tuple(_row_evidence(v) for v in values)
                )
            finally:
                conn.rollback()
