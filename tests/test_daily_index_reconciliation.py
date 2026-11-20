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
