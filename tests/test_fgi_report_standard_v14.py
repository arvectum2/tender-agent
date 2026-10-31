"""Verified EIS UKRM contract must override stale secondary report wording."""
from scripts.market_intelligence.export_fgi_deck_snapshot import (
    source_bound_bashkirenergo_note,
    verified_bashkirenergo_contract,
)


def _proof():
    return {
        "canonical_id": "223fz:32515582393:lot1",
        "scope": "supply",
        "contract_registry_number": "50277071467260001550000",
        "contract_number": "РЭС-1.26.1/Д-01071",
        "contract_signed_date": "2026-02-27",
        "contract_registered_price_rub": "4850000.00",
        "registered_signed_contract_verified": True,
    }, {"eis_bashkirenergo_contract_enrichment": {
        "supplier_verified": False,
        "payment_verified": False,
        "sources": [
            {"sha256": "284e532d010d202980375fb4d684dd0616d8665d7c726e7494e2b5c1a6670595"},
            {"sha256": "bac0d89f450f32cdfb6cada70f6976dfaec1ade599ff104898c5338a91a1d553"},
        ],
    }}


def test_verified_contract_note_distinguishes_registered_price_from_sale():
    data, metadata = _proof()
    assert verified_bashkirenergo_contract(data, metadata)
    note = source_bound_bashkirenergo_note(data, metadata)
    assert "4 850 000,00" in note
    assert "не доказывает фактическую" in note
    assert "Подписавший поставщик" in note


def test_missing_or_wrong_sha_cannot_upgrade_contract():
    data, metadata = _proof()
    metadata["eis_bashkirenergo_contract_enrichment"]["sources"][0]["sha256"] = "f" * 64
    assert not verified_bashkirenergo_contract(data, metadata)
    assert source_bound_bashkirenergo_note(data, metadata) is None
