from scripts.market_intelligence.export_fgi_deck_snapshot import (
    source_bound_rad_sources,
    verified_rad_commission,
)


def test_rad_commission_source_bound_and_not_signed():
    data = {"winner": 'ООО "ЭНЕРГОСЕТЬ"'}
    proof = {
        "role": "commission_recommended_contractor_not_signed_supplier",
        "field": "winner", "value": data["winner"],
        "signed_supplier_verified": False, "signed_contract_verified": False,
        "exact_original_quote": 'заключить договор с ООО "ЭНЕРГОСЕТЬ"',
        "member_sha256": "c" * 64,
        "source_sha256": ["a" * 64, "b" * 64],
        "source_urls": [
            "https://tender.lot-online.ru/etp/app/LotCard/page?x=1",
            "https://tender.lot-online.ru/etp/downloadppf?uuid=1",
        ],
    }
    meta = {"rad_commission_enrichment": proof}
    assert verified_rad_commission(data, meta) == proof
    assert len(source_bound_rad_sources(data, meta)) == 2
    assert verified_rad_commission({"winner": "other"}, meta) is None
    assert verified_rad_commission(data, {"rad_commission_enrichment": {
        **proof, "signed_supplier_verified": True,
    }}) is None
    assert source_bound_rad_sources(data, {}) == []
