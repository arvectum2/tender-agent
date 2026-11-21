"""Retain primary tier when first-party capture uses the evidence tier key."""
from scripts.market_intelligence.export_fgi_deck_snapshot import safe_urls


def test_source_tier_fallback_and_sha():
    url = 'https://www.b2b-center.ru/market/test/'
    out = safe_urls([{'url': url, 'tier': 'first_party_original', 'sha256': 'a' * 64}])
    assert out == [{'url': url, 'tier': 'first_party_original', 'sha': 'a' * 64}]
