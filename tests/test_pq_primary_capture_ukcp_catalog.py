"""UKCP first-party model reference is not proof of awarded OEM/supplier."""
import pytest

from scripts.market_intelligence.capture_primary_source import source_url


def test_exact_public_ukcp_model_catalogue_only():
    url = ("https://ukkz.com/en/catalog/capacitors/"
           "power-factor-correction-capacitors/"
           "high-voltage-power-factor-correction-capacitors.html")
    assert source_url(url) == url
    for bad in (url + "?download=1", "https://ukkz.com/en/",
                "https://evil.ukkz.com/en/catalog/capacitors/",
                url.replace("https://", "http://")):
        with pytest.raises(ValueError):
            source_url(bad)
