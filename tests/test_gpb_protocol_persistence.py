import pytest

from scripts.research.link_gpb_document_receipts import reconcile_capture_metadata
from scripts.research.persist_gpb_protocol_decisions import attach_decision


def test_source_bound_decision_is_preserved_on_recapture():
    rc = {"sha256": "a", "document_url": "u", "external_id": "etp:1",
          "document_role": "published_protocol"}
    meta = {"source": "etp_gpb", "capture_status": "verified_private_original",
            "capture_receipts": [rc], "dp_index": None}
    decision = {"protocol_sha256": "a", "document_url": "u", "external_id": "etp:1",
                "decision": "BEST_BID_SELECTED_NOT_SIGNED_CONTRACT",
                "parser_schema": "gpb_best_bid_v2", "participant_legal_identity": None,
                "contract_amount": None}
    stored = attach_decision(meta, decision)
    assert attach_decision(stored, decision) == stored
    proposed = dict(meta)
    assert not reconcile_capture_metadata(stored, proposed)
    assert proposed["protocol_decision"] == decision
    with pytest.raises(ValueError, match="evidence mismatch"):
        attach_decision(meta, decision | {"protocol_sha256": "b"})
    with pytest.raises(ValueError, match="conflicts"):
        attach_decision(stored, decision | {"best_bid_rub": "99"})


def test_same_original_two_verified_publication_urls():
    rc = {"sha256": "a", "document_url": "u", "external_id": "etp:1",
          "document_role": "published_protocol"}
    meta = {"source": "etp_gpb", "capture_receipts": [rc, rc | {"document_url": "v"}]}
    row = {"protocol_sha256": "a", "document_url": "u", "external_id": "etp:1",
           "decision": "BEST_BID_SELECTED_NOT_SIGNED_CONTRACT",
           "parser_schema": "gpb_best_bid_v2", "participant_legal_identity": None,
           "contract_amount": None}
    stored = attach_decision(meta, row)
    assert attach_decision(stored, row | {"document_url": "v"}) == stored
    with pytest.raises(ValueError, match="evidence mismatch"):
        attach_decision(stored, row | {"document_url": "unverified"})
    with pytest.raises(ValueError, match="conflicts"):
        attach_decision(stored, row | {"document_url": "v", "best_bid_rub": "99"})
