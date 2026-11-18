import pytest

from scripts.quality import apr067_ri223_gap_review as review


def test_frozen_gap_set():
    gaps=review.baseline_gaps()
    assert len(gaps)==16
    assert ("32616444788","evaluation") in gaps
    assert ("32616445795","evaluation") not in gaps


def test_baseline_tamper_rejected(tmp_path,monkeypatch):
    p=tmp_path/"changed.json"
    p.write_bytes(review._BASELINE.read_bytes()+b" ")
    monkeypatch.setattr(review,"_BASELINE",p)
    with pytest.raises(ValueError,match="baseline changed"):
        review.baseline_gaps()


def fixture(monkeypatch,tmp_path,valid=True):
    n="32616445632"
    sha=review._DOCS[n]
    meta={"procurement_id":n,"files":[{"source":"ri223_attachment","data_platform_source":{"canonical_uri":"tender-upload://"+sha},"file_id":"FILE-02"}]}
    monkeypatch.setattr(review,"checked_search_run",lambda _:(tmp_path,meta))
    monkeypatch.setattr(review,"verified_inventory",lambda *a:{"archived_bytes_complete":True,"projection_complete":True})
    monkeypatch.setattr(review,"ri223_archive_observation",lambda *a:{"status":"PINNED_RI223_ARCHIVED_NOTICE","fields":{},"citations":[]})
    def verify(**kw):
        return {"status":"literal_quote_found_in_extracted_original_only","evidence":{"original_sha256":sha if valid else "0"*64,"quote":kw["exact_quote"]}}
    monkeypatch.setattr(review,"verify_operator_run_quote",verify)
    return meta


@pytest.mark.parametrize("valid",[True,False])
def test_quote_requires_exact_source(monkeypatch,tmp_path,valid):
    fixture(monkeypatch,tmp_path,valid=valid)
    r=review.observe("run")[0]
    assert r["status"]==("NOTICE_NOT_INVITATION_REVIEW" if valid else "UNKNOWN_SOURCE_QUOTE_UNVERIFIED")
    assert bool(r["evidence"])==valid
    assert not r["requirements_verified"] and not r["legal_applicability_attested"]


def test_incomplete_inventory_denied(monkeypatch,tmp_path):
    fixture(monkeypatch,tmp_path)
    monkeypatch.setattr(review,"verified_inventory",lambda *a:{"archived_bytes_complete":False,"projection_complete":False})
    monkeypatch.setattr(review,"verify_operator_run_quote",lambda **kw:pytest.fail("unverified source"))
    with pytest.raises(ValueError,match="complete archived"):
        review.observe("run")


def test_duplicate_and_promotion_denied():
    rows=[{"case":n,"domain":d,"requirements_verified":False,"legal_applicability_attested":False,"evidence":None} for n,d in review.baseline_gaps()]
    assert review.summarize(rows)["gaps_reviewed"]==16
    with pytest.raises(ValueError,match="duplicated"):
        review.summarize(rows[:-1]+[rows[0]])
    rows[0]["legal_applicability_attested"]=True
    with pytest.raises(ValueError,match="promotion"):
        review.summarize(rows)
