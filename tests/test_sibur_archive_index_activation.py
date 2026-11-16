import pytest
from scripts.research.link_sibur_archive_index import attach,COLLECTION

def test_attach_preserves_capture_and_refuses_replacement():
    sha='a'*64;c={'url':'https://www.sibur.ru/1'};actual={'capture_receipts':[c,{'url':'more'}],'dp_index':None,'other':1};dp={'collection_id':COLLECTION,'canonical_uri':'content-sha256://'+sha,'extraction_status':'extracted','chunks':2,'embeddings':2}
    out=attach(actual,[c],dp,sha);assert out=={**actual,'dp_index':dp};assert attach(out,[c],dp,sha)==out
    with pytest.raises(ValueError,match='capture mismatch'):attach(actual,[{'url':'wrong'}],dp,sha)
    with pytest.raises(ValueError,match='invalid DP'):attach(actual,[c],{**dp,'embeddings':1},sha)
    with pytest.raises(ValueError,match='identity differs'):attach(out,[c],{**dp,'document_id':'other'},sha)
