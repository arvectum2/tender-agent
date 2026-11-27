"""Source-bound Tyazhinskaya commission: one anonymous application, design not hardware."""
import pytest

from scripts.market_intelligence import enrich_pq_tyazhinskaya_commission_20261102 as m


def test_exact_original_and_receipt():
    p = m.proof()
    assert p["sha256"] == m.SHA
    assert len(p["quotes"]) == 6


def test_sha_mismatch_fails_closed(monkeypatch):
    monkeypatch.setattr(m, "SHA", "0" * 64)
    with pytest.raises(ValueError, match="SHA/receipt"):
        m.proof()


def test_scope_and_roles_are_conservative():
    assert m.FIELDS["bid"] == "7406851.40"
    assert m.FIELDS["protocol_participant_count"] == 1
    assert "несостоявшейся" in m.FIELDS["protocol_status_note"]
    assert "не продажа оборудования" in m.FIELDS["protocol_status_note"]
    assert "winner" not in m.FIELDS
    assert "contract_signatory" not in m.FIELDS


def test_old_null_conflict_fails():
    row = {"id": m.CID, "owner": "tender-agent", "hash": "", "meta": {},
           "data": {"canonical_id": m.CID, "procedure_id": "32616354211",
                    "scope": "design", "customer": {"inn": "5501231424"},
                    "nmck_rub": "7519646.09", "contract_registered_price_rub": "7406851.40",
                    "contract_signed_date": "2026-09-23",
                    "registered_signed_contract_verified": True, "bid": "conflict"}}
    with pytest.raises(RuntimeError, match="guard"):
        m.prepare(row, {"sha256": m.SHA})


def test_export_requires_sha_bound_evidence():
    from scripts.market_intelligence.export_fgi_deck_snapshot import (
        source_bound_bid,
        source_bound_commission_note,
        verified_tyazhinskaya_commission,
    )
    data = {**m.FIELDS, "canonical_id": m.CID, "scope": "design",
            "contract_registered_price_rub": "7406851.40",
            "registered_signed_contract_verified": True,
            "winner": None, "contract_signatory": None,
            "evidence": [{"sha256": m.SHA, "url": m.URL}]}
    meta = {m.KEY: {"fields": m.FIELDS,
                    "proof": {"sha256": m.SHA, "url": m.URL},
                    "signed_supplier_verified": False,
                    "paid_equipment_sale_verified": False}}
    assert verified_tyazhinskaya_commission(data, meta)
    assert source_bound_bid(data, meta) == "7406851.40"
    assert "одна заявка" in source_bound_commission_note(data, meta)
    data["evidence"][0]["sha256"] = "0" * 64
    assert not verified_tyazhinskaya_commission(data, meta)
    assert source_bound_bid(data, meta) is None
    assert source_bound_commission_note(data, meta) is None
