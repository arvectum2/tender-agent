"""Read-only evidence checks for the Angarsk commission bid."""
import pytest

from scripts.market_intelligence import enrich_pq_angarsk_commission_20261102 as m


def test_official_original_and_verbatim_quotes():
    proof = m.proof()
    assert proof["sha256"] == m.SHA
    assert proof["url"] == m.URL
    assert len(proof["quotes"]) == 3


def test_sha_and_quote_are_fail_closed(monkeypatch):
    monkeypatch.setattr(m, "SHA", "0" * 64)
    with pytest.raises(ValueError, match="SHA/receipt"):
        m.proof()


def test_offer_is_not_signed_contract_or_equipment_sale():
    assert m.FIELDS["bid"] == "2590000.00"
    assert m.FIELDS["protocol_participant_count"] == 3
    assert "2 639 026,64" in m.FIELDS["protocol_status_note"]
    assert "не цена оборудования PQ" in m.FIELDS["protocol_status_note"]
    assert "winner" not in m.FIELDS
    assert "contract_signatory" not in m.FIELDS
