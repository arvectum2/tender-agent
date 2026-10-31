"""EIS registered design contract must not become a PQ equipment sale."""

from scripts.market_intelligence.export_fgi_deck_snapshot import (
    source_bound_tyazhinskaya_note,
    verified_tyazhinskaya_contract,
)


def sample():
    data = {
        "canonical_id": "223fz:32616354211:lot1",
        "scope": "design",
        "contract_registry_number": "65501231424260000440000",
        "contract_number": "14-СБП/2026",
        "contract_signed_date": "2026-09-23",
        "contract_registered_price_rub": "7406851.40",
        "registered_signed_contract_verified": True,
        "supplier_verified": False,
        "pq_equipment_only_contract_rub": None,
    }
    metadata = {"eis_tyazhinskaya_contract_enrichment": {
        "sources": [{"sha256": s} for s in (
            "a3df999a678442b7b2050702d97141326464b3a493c47cdcae853bb880b7453f",
            "2815d451811c14e869a2d25fad8a0d2a888950dbb7d6baa1bc5f5c4853bdfb49",
        )],
        "supplier_verified": False,
        "payment_verified": False,
    }}
    return data, metadata


def test_design_contract_original_and_conservative_disclosure():
    data, metadata = sample()
    assert verified_tyazhinskaya_contract(data, metadata)
    note = source_bound_tyazhinskaya_note(data, metadata)
    assert "НЕ продажа оборудования" in note
    assert "подписавший подрядчик" in note


def test_sha_drift_blocks_promotion():
    data, metadata = sample()
    metadata["eis_tyazhinskaya_contract_enrichment"]["sources"][1]["sha256"] = "0" * 64
    assert not verified_tyazhinskaya_contract(data, metadata)
    assert source_bound_tyazhinskaya_note(data, metadata) is None


def test_supplier_claim_blocks_promotion():
    data, metadata = sample()
    data["supplier_verified"] = True
    assert not verified_tyazhinskaya_contract(data, metadata)
