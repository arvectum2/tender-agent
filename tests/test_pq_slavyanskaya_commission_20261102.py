"""First-party final protocol: ranked anonymous applications, not signed suppliers."""
import pytest

from scripts.market_intelligence import enrich_pq_slavyanskaya_commission_20261102 as m


def test_original_protocol_and_exact_quotes():
    proof = m.proof()
    assert proof["sha256"] == m.SHA
    assert len(proof["quotes"]) == 5


def test_sha_mismatch_fails_closed(monkeypatch):
    monkeypatch.setattr(m, "SHA", "0" * 64)
    with pytest.raises(ValueError, match="SHA/receipt"):
        m.proof()


def test_offer_vs_contract_price_and_anonymous_participant():
    assert m.FIELDS["bid"] == "20107269.94"
    assert m.FIELDS["protocol_participant_count"] == 4
    assert "17 793 360,90" in m.FIELDS["protocol_status_note"]
    assert "20 442 391,10" in m.FIELDS["protocol_status_note"]
    assert "не продажа оборудования PQ 6–35 кВ" in m.FIELDS["protocol_status_note"]
    assert "winner" not in m.FIELDS
    assert "contract_signatory" not in m.FIELDS


def test_old_null_guard_rejects_conflict():
    row = {"id": m.CID, "owner": "tender-agent", "hash": "", "meta": {},
           "data": {"canonical_id": m.CID, "procedure_id": "32515225588",
                    "scope": "design", "customer": {"inn": "4716016979"},
                    "nmck_rub": "27175270", "contract_registered_price_rub": "20442391.10",
                    "contract_signed_date": "2025-11-19",
                    "registered_signed_contract_verified": True, "bid": "conflict"}}
    with pytest.raises(RuntimeError, match="guard"):
        m.prepare(row, {"sha256": m.SHA})


def test_client_report_requires_source_bound_cas():
    from scripts.market_intelligence.export_fgi_deck_snapshot import (
        source_bound_bid,
        source_bound_commission_note,
        verified_slavyanskaya_commission,
    )
    source = {"sha256": m.SHA, "url": m.URL}
    data = {**m.FIELDS, "canonical_id": m.CID, "scope": "design",
            "contract_registered_price_rub": "20442391.10",
            "registered_signed_contract_verified": True,
            "winner": None, "contract_signatory": None,
            "evidence": [{"sha256": m.SHA, "url": m.URL}]}
    meta = {m.KEY: {"fields": m.FIELDS, "proof": source,
                    "signed_supplier_verified": False,
                    "paid_equipment_sale_verified": False}}
    assert verified_slavyanskaya_commission(data, meta)
    assert source_bound_bid(data, meta) == "20107269.94"
    assert "второе место" in source_bound_commission_note(data, meta)
    data["evidence"][0]["sha256"] = "0" * 64
    assert not verified_slavyanskaya_commission(data, meta)
    assert source_bound_bid(data, meta) is None
    assert source_bound_commission_note(data, meta) is None
