from scripts.market_intelligence.enrich_pq_lopcha_p0_20261031 import CASES, INN
from scripts.market_intelligence.export_fgi_deck_snapshot import verified_lopcha_p0


def test_lopcha_p0_source_binding():
    for n, (scope, _, sha) in CASES.items():
        url = f"https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber={n}"
        source = {"url": url, "sha256": sha, "exact_original_quote": "ИНН 4716016979"}
        data = {"canonical_id": f"223fz:{n}:lot1", "procedure_id": n,
                "scope": scope, "buyer_inn": INN,
                "source_urls": [{"url": url, "tier": "first_party", "sha": sha}]}
        meta = {"eis_lopcha_p0": {"fields": ["buyer_inn", "source_urls"], "source": source}}
        assert verified_lopcha_p0(data, meta)
        assert not verified_lopcha_p0(data, {})
        assert not verified_lopcha_p0({**data, "source_urls": []}, meta)
        assert not verified_lopcha_p0(data, {"eis_lopcha_p0": {
            **meta["eis_lopcha_p0"], "source": {**source, "sha256": "0"*64}}})
