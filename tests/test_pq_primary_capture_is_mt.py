"""Only the native public UUID procurement card is allowed from is-mt.pro."""
import pytest

from scripts.market_intelligence.capture_primary_source import source_url

CARD = "https://is-mt.pro/Purchase/Details?id=c396eb0d-7a51-447e-9fac-d0c030f41c60"


def test_is_mt_public_readonly_ajax_tables_allowlisted():
    for path in ("ListCgc", "ListOffersWithChangeHistory"):
        url = ("https://is-mt.pro/Purchase/" + path
               + "?id=c396eb0d-7a51-447e-9fac-d0c030f41c60"
               + "&cache=172e3e29-8f04-490d-9d15-f5fa7a42720b")
        assert source_url(url) == url


def test_is_mt_public_procurement_card_allowlisted():
    assert source_url(CARD) == CARD


@pytest.mark.parametrize("url", [
    "http://is-mt.pro/Purchase/Details?id=c396eb0d-7a51-447e-9fac-d0c030f41c60",
    "https://evil.is-mt.pro/Purchase/Details?id=c396eb0d-7a51-447e-9fac-d0c030f41c60",
    "https://is-mt.pro/Purchase/Details?id=../../secrets",
    "https://is-mt.pro/Purchase/Details?id=c396eb0d-7a51-447e-9fac-d0c030f41c60&extra=1",
    "https://is-mt.pro/Purchase/Details?id=c396eb0d-7a51-447e-9fac-d0c030f41c60#fragment",
    "https://is-mt.pro/Purchase/Edit?id=c396eb0d-7a51-447e-9fac-d0c030f41c60",
    "https://is-mt.pro/Purchase/ListCgc?id=c396eb0d-7a51-447e-9fac-d0c030f41c60",
    "https://is-mt.pro/Purchase/ListCgc?id=c396eb0d-7a51-447e-9fac-d0c030f41c60&cache=bad",
    "https://is-mt.pro/Purchase/ListOffersWithChangeHistory?id=c396eb0d-7a51-447e-9fac-d0c030f41c60&cache=172e3e29-8f04-490d-9d15-f5fa7a42720b&extra=1",
])
def test_is_mt_nonpublic_or_unsafe_paths_rejected(url):
    with pytest.raises(ValueError, match="allowlisted"):
        source_url(url)
