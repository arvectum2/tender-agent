import pytest

from scripts.research.link_sibur_document_receipts import reconcile_meta


def meta(receipts, indexed=None):
    return {"source": "sibur_public", "capture_status": "verified_private_original",
            "capture_receipts": [{"url": u} for u in receipts], "dp_index": indexed}


def test_monotonic_capture_and_index():
    previous = meta(["a"])
    assert not reconcile_meta(previous, previous)
    assert reconcile_meta(previous, meta(["a", "b"], {"document_id": "1"}))
    assert reconcile_meta(meta(["a"], {"document_id": "1"}),
                          meta(["b", "a"], {"document_id": "1"}))


def test_refuse_overwrite():
    with pytest.raises(ValueError, match="removed or replaced"):
        reconcile_meta(meta(["a"]), meta(["b"]))
    with pytest.raises(ValueError, match="removed or replaced"):
        reconcile_meta(meta(["a"], {"document_id": "1"}), meta(["a"]))
    with pytest.raises(ValueError, match="removed or replaced"):
        reconcile_meta(meta(["a"], {"document_id": "1"}), meta(["a"], {"document_id": "2"}))
