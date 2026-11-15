import pytest

from scripts.research.gpb_delta_sync import plan


def test_immutable_prior_and_missing_group_only():
    l={"external_id":"etp:1","sha256":"a"*64,"document_url":"u","document_role":"published_protocol"}
    r={"external_id":"etp:1","protocol_sha256":"a"*64,"document_url":"u","decision":"BEST_BID_SELECTED_NOT_SIGNED_CONTRACT","parser_schema":"gpb_best_bid_v2","participant_legal_identity":None,"contract_amount":None}
    assert plan([l],[r],{})==([l],[r])
    meta={"source":"etp_gpb","capture_status":"verified_private_original","capture_receipts":[l],"dp_index":None,"protocol_decision":r}
    assert plan([l],[r],{("etp:1","a"*64):meta})==([],[])
    with pytest.raises(ValueError,match="conflicts"):
        plan([l],[r|{"best_bid_rub":"99"}],{("etp:1","a"*64):meta})
    extra=l|{"document_url":"v"}
    assert plan([l,extra],[r|{"document_url":"v"}],{("etp:1","a"*64):meta})==([l,extra],[])
