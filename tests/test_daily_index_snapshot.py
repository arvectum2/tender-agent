import hashlib
from unittest.mock import MagicMock

import pytest

from src.modules.daily_tender_run.index_snapshot import (
    PostgresIndexReader,
    _row_evidence,
)

H = hashlib.sha256(b"fixture").hexdigest()


def evidence(**kw):
    return {
        "canonical_uri": "tender-chunk://abc",
        "resource_hash": H,
        "status": "ready",
        "document_hash": H,
        "document_text": "fixture",
        "extraction_status": "extracted",
        "chunk_hash": H,
        "chunk_text": "fixture",
        "ordinal": 0,
        "provider": "test",
        "model": "test-embedding",
        "dimension": 3,
        "vector_dimension": 3,
    } | kw


def test_actual_bytes_and_vector_contract():
    row = _row_evidence(evidence())
    assert row.resource_hash == row.document_hash == row.chunk_hash == H
    assert row.embedding.dimension == 3
    assert (
        _row_evidence(
            evidence(provider=None, model=None, dimension=None, vector_dimension=None)
        ).embedding
        is None
    )


@pytest.mark.parametrize(
    "change",
    [
        {"status": "error"},
        {"document_text": "wrong"},
        {"chunk_text": "wrong"},
        {"ordinal": 1},
        {"vector_dimension": 2},
        {"provider": None},
        {"extraction_status": "failed"},
    ],
)
def test_refuses_corrupt_persisted_evidence(change):
    with pytest.raises(ValueError):
        _row_evidence(evidence(**change))


def test_read_only_database_binding():
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    conn = engine.connect.return_value.__enter__.return_value
    conn.execute.return_value.one.return_value = ("other", "123")
    with pytest.raises(ValueError, match="database identity"):
        PostgresIndexReader(engine, "123")("collection")
    assert "READ ONLY" in str(conn.execute.call_args_list[0].args[0])
    assert conn.execute.call_count == 2
    conn.rollback.assert_called_once()


def test_no_revision_or_owner_bypass():
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    conn = engine.connect.return_value.__enter__.return_value
    headers = MagicMock()
    headers.one.return_value = ("arvectum_data", "123")
    rows = MagicMock()
    rows.mappings.return_value.one_or_none.return_value = {"owner": "other"}
    conn.execute.side_effect = [MagicMock(), headers, rows]
    with pytest.raises(ValueError, match="owned collection"):
        PostgresIndexReader(engine, "123")("collection")
    conn.rollback.assert_called_once()
