from unittest.mock import patch

import pytest

from scripts.market_intelligence.enrich_pq_rad_commission_32615966040 import (
    CARD,
    CARD_SHA,
    CID,
    MEMBER_SHA,
    RAR_SHA,
    WINNER,
    proof,
    source,
    write,
)


def test_source_pinned_committee_recommendation_not_signed():
    p = proof()
    assert CID == "223fz:32615966040:lot1"
    assert p["source_sha256"] == [CARD_SHA, RAR_SHA]
    assert p["member_sha256"] == MEMBER_SHA
    assert 'Участником № 490997 , ООО "ЭНЕРГОСЕТЬ"' in p["exact_original_quote"]
    assert WINNER in p["exact_original_quote"]
    assert p["signed_supplier_verified"] is False
    assert p["signed_contract_verified"] is False


def test_sha_mismatch_fails_closed():
    with pytest.raises(ValueError, match="mismatch"):
        source(CARD, "0" * 64, "LotCard")


def test_existing_winner_prevents_write():
    row = {"id": CID, "owner": "tender-agent", "data": {"winner": "existing"}}
    with patch("scripts.market_intelligence.enrich_pq_rad_commission_32615966040.psql") as db:
        with pytest.raises(RuntimeError, match="CAS"):
            write(row, {"rows": 117}, {})
        db.assert_not_called()
