import hashlib
from types import SimpleNamespace

import pytest

from src.modules.daily_tender_run.index_reconciliation import (
    EmbeddingContract,
    StoredChunk,
    reconcile,
)

CONTRACT = EmbeddingContract("test", "fixture", 32)
CHUNK = SimpleNamespace(id="chunk1", text="fixture")
HASH = hashlib.sha256(CHUNK.text.encode()).hexdigest()
URI = "tender-chunk://chunk1"


def row(**kw):
    return StoredChunk(
        **(
            {
                "uri": URI,
                "resource_hash": HASH,
                "document_hash": HASH,
                "chunk_hash": HASH,
                "embedding": CONTRACT,
            }
            | kw
        )
    )


def test_missing_only_and_complete():
    assert reconcile([CHUNK], [], CONTRACT)["eligible_absent_uris"] == [URI]
    result = reconcile([CHUNK], [row()], CONTRACT)
    assert result["complete"] and not result["eligible_absent_uris"]
    assert not reconcile([], [], CONTRACT)["complete"]


@pytest.mark.parametrize(
    "bad",
    [
        [row(document_hash="bad")],
        [row(chunk_hash=None)],
        [row(chunk_hash="different")],
        [row(embedding=None)],
        [row(embedding=EmbeddingContract("test", "other", 32))],
        [row(), row()],
        [row(uri="tender-chunk://unknown")],
    ],
)
def test_conflicts_prevent_insertion(bad):
    absent = SimpleNamespace(id="chunk2", text="other")
    result = reconcile([CHUNK, absent], bad, CONTRACT)
    assert result["requires_review"] and not result["eligible_absent_uris"]


def test_duplicate_local_identity_rejected():
    with pytest.raises(ValueError):
        reconcile([CHUNK, CHUNK], [], CONTRACT)


def test_bounded_repair_and_resume(monkeypatch):
    from contextlib import contextmanager
    from unittest.mock import Mock

    from src.modules.daily_tender_run.index_reconciliation import (
        IndexSnapshot,
        repair_absent_batch,
    )

    chunks = [
        SimpleNamespace(
            id=f"c{i}",
            text=f"source{i}",
            document_id="doc",
            source_file_name="test.txt",
        )
        for i in range(3)
    ]
    repo = Mock()
    repo.list_chunks_by_tender.return_value = chunks
    monkeypatch.setattr(
        "src.tender_research.rag.data_platform.build_tender_collection_id",
        lambda *_: "collection",
    )
    seen = []
    admitted = []

    @contextmanager
    def gate():
        admitted.append(True)
        try:
            yield
        finally:
            admitted.pop()

    def snapshot(cid):
        return IndexSnapshot(cid, CONTRACT, tuple(seen))

    def ingest(**kw):
        assert admitted
        digest = hashlib.sha256(kw["text"].encode()).hexdigest()
        seen.append(
            StoredChunk(
                "tender-chunk://" + kw["chunk_id"], digest, digest, digest, CONTRACT
            )
        )

    client = Mock()
    client.ingest_chunk.side_effect = ingest
    kwargs = {
        "repo": repo,
        "client": client,
        "tender_id": "t",
        "collection_id": "collection",
        "expected_contract": CONTRACT,
        "read_snapshot": snapshot,
        "admitted_write": gate,
        "limit": 2,
    }
    first = repair_absent_batch(**kwargs)
    assert first["remaining"] == 1 and client.ingest_chunk.call_count == 2
    second = repair_absent_batch(**kwargs)
    assert second["complete"] and client.ingest_chunk.call_count == 3
    assert (
        repair_absent_batch(**kwargs)["complete"]
        and client.ingest_chunk.call_count == 3
    )


def test_response_without_persisted_resource_fails_closed(monkeypatch):
    from contextlib import nullcontext
    from unittest.mock import Mock

    from src.modules.daily_tender_run.index_reconciliation import (
        IndexSnapshot,
        repair_absent_batch,
    )

    repo = Mock()
    repo.list_chunks_by_tender.return_value = [
        SimpleNamespace(
            id="c1", text="text", source_file_name="file.txt", document_id="doc"
        )
    ]
    monkeypatch.setattr(
        "src.tender_research.rag.data_platform.build_tender_collection_id",
        lambda *_: "collection",
    )
    client = Mock()
    kwargs = {
        "repo": repo,
        "client": client,
        "tender_id": "t",
        "collection_id": "collection",
        "expected_contract": CONTRACT,
        "read_snapshot": lambda cid: IndexSnapshot(cid, CONTRACT, ()),
        "admitted_write": nullcontext,
        "limit": 1,
    }
    with pytest.raises(RuntimeError, match="independently verified"):
        repair_absent_batch(**kwargs)
    assert client.ingest_chunk.call_count == 1
    client.ingest_chunk.side_effect = TimeoutError("ambiguous completion")
    with pytest.raises(TimeoutError):
        repair_absent_batch(**kwargs)
    assert client.ingest_chunk.call_count == 2
