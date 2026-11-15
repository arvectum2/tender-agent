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


def test_capture_only_replay_preserves_exact_verified_index():
    from scripts.research.link_sibur_document_receipts import preserve_index_for_capture_replay, COLLECTION
    sha='a'*64
    dp={'collection_id':COLLECTION,'canonical_uri':'content-sha256://'+sha,
        'extraction_status':'extracted','embeddings':4,'document_id':'d'}
    old=meta(['a'],dp); proposed=meta(['a','b'])
    assert preserve_index_for_capture_replay(old,proposed,sha,{},True)==meta(['a','b'],dp)
    assert preserve_index_for_capture_replay(old,proposed,sha,{},False)==proposed
    incoming=meta(['a','b'],{'document_id':'different'})
    assert preserve_index_for_capture_replay(old,incoming,sha,{sha:incoming['dp_index']},True)==incoming
    with pytest.raises(ValueError,match='removed or replaced'):
        reconcile_meta(old,incoming)
    with pytest.raises(ValueError,match='invalid existing'):
        preserve_index_for_capture_replay(meta(['a'],{**dp,'canonical_uri':'bad'}),proposed,sha,{},True)
    with pytest.raises(ValueError,match='removed or replaced'):
        reconcile_meta(old,preserve_index_for_capture_replay(old,meta(['b']),sha,{},True))
