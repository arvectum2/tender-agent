import pytest

from scripts.ops.audit_tender_index_linkage import reconcile, sha
from src.tender_research.rag.presets import (
    legacy_tender_collection_id,
    tender_collection_id,
)

TENDER="b7e94fed-1234-4444-aaaa-000000000001"
TEXT="Оплата  после приемки."
CHUNK="00000000-0000-4000-8000-000000000001"
DOC="00000000-0000-4000-8000-000000000002"
LOCAL=[(TENDER,"0001",CHUNK,DOC,sha(TEXT),TEXT)]
REVISION=sha(CHUNK+":"+sha(TEXT))[:16]
CID=tender_collection_id(TENDER,REVISION)
LEGACY=legacy_tender_collection_id(TENDER,REVISION)
NORMAL=" ".join(TEXT.split())
ROW=[CID,"tender-chunk://"+CHUNK,"dp-doc","dp-chunk",sha(NORMAL),NORMAL,1,1]


def test_exact_current_document_link():
    d=reconcile(LOCAL,[ROW],{CID})
    assert d["verified"]==d["complete_tenders"]==1
    assert d["missing_or_mismatch"]==0


@pytest.mark.parametrize("field,value",[(1,"tender-chunk://foreign"),(2,None),(3,None),(4,"wrong"),(5,"wrong"),(6,2),(7,0)])
def test_mismatch_not_counted(field,value):
    row=ROW.copy();row[field]=value
    assert reconcile(LOCAL,[row],{CID})["verified"]==0


def test_legacy_fallback_only_if_canonical_absent():
    row=ROW.copy();row[0]=LEGACY
    assert reconcile(LOCAL,[row],{LEGACY})["verified"]==1
    assert reconcile(LOCAL,[row],{CID,LEGACY})["verified"]==0


def test_duplicate_and_wrong_local_hash_not_counted():
    assert reconcile(LOCAL,[ROW,ROW],{CID})["verified"]==0
    invalid=[(*LOCAL[0][:4],"wrong",TEXT)]
    assert reconcile(invalid,[ROW],{CID})["verified"]==0
