"""Meleuz original SHA provenance and report disclosure regression."""
from scripts.market_intelligence.export_fgi_deck_snapshot import (
    source_bound_bid,
    source_bound_meleuz_note,
    verified_meleuz_contract,
)


def sample():
    data = {
        "canonical_id": "223fz:32616296475:lot1",
        "contract_registry_number": "50263017332260000870000",
        "contract_registered_price_rub": "3865725.99",
        "contract_signed_date": "2026-09-21",
        "registered_signed_contract_verified": True,
        "supplier_verified": False,
        "pq_equipment_only_contract_rub": None,
        "voltage_kv": "не более 6,3 кВ (требование ТЗ)",
        "power": "не менее 500 кВАр (требование ТЗ)",
        "commission_first_place_bid_rub": "3865725.99",
    }
    sha = [
        "51d201695c4aa97264e17922a053ba6eca03b0032c13d7cd815dff487c9de90f",
        "f598adc6ffb6281ac20b025a86a1632091d2f9851dc7c2e018e9b04514fae270",
        "b3a03bb02d5b84928e91e344de90310679189dc95e84f99d3b8cc7df989aa473",
        "ca9a840c69bce647287c4571b675d57f401f89a20ae3d24f3842d8e24485b781",
    ]
    metadata = {"meleuz_eis_20261031_enrichment": {
        "sources": [{"sha256": s} for s in sha],
        "supplier_verified": False,
        "equipment_only_price_verified": False,
    }}
    return data, metadata

def test_source_bound_report_fields():
    data, metadata = sample()
    assert verified_meleuz_contract(data, metadata)
    assert source_bound_bid(data, metadata) == "3865725.99"
    note = source_bound_meleuz_note(data, metadata)
    assert "шеф-монтаж" in note
    assert "не установлены" in note

def test_sha_drift_blocks_report_promotion():
    data, metadata = sample()
    metadata["meleuz_eis_20261031_enrichment"]["sources"][0]["sha256"] = "0" * 64
    assert not verified_meleuz_contract(data, metadata)
    assert source_bound_meleuz_note(data, metadata) is None

def test_supplier_misclassification_blocks_report_promotion():
    data, metadata = sample()
    data["supplier_verified"] = True
    assert not verified_meleuz_contract(data, metadata)

