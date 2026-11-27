"""First-party supplier product evidence remains separate from signed sales."""
from pathlib import Path

import pytest

from src.modules.market_intelligence.portfolio_pipeline import PortfolioInputError
from src.modules.market_intelligence.supplier_source_evidence import audit_supplier_html


def _html(tmp_path: Path, body: str, suffix: str = "</html>") -> Path:
    p = tmp_path / "source.html"
    p.write_text("<html><body><p>Authoritative first-party product specifications, bounded testing fixture.</p>" + body + "</body>" + suffix, encoding="utf-8")
    return p


def _audit(p: Path, **overrides):
    kwargs = {
        "source": p, "url": "https://supplier.example.org/products/svg",
        "quotes": ["6.6 kV dynamic reactive compensation"],
        "transport_complete": True,
    }
    kwargs.update(overrides)
    return audit_supplier_html(**kwargs)


def test_verified_quote_does_not_verify_procurement_sale(tmp_path):
    p = _html(tmp_path, "6.6   kV dynamic reactive compensation")
    result = _audit(p)
    assert result["source_grade"] == "first_party_complete_quote_verified"
    assert result["verified_technical_quotes"] == ["6.6 kV dynamic reactive compensation"]
    assert len(result["source_sha256"]) == 64
    assert result["verified_signed_supplier"] is False
    assert result["eligible_for_market_turnover"] is False


def test_truncated_transport_cannot_promote_completeness(tmp_path):
    p = _html(tmp_path, "6.6 kV dynamic reactive compensation", "")
    assert _audit(p, transport_complete=False)["source_grade"] == "first_party_partial_quote_verified"
    with pytest.raises(PortfolioInputError, match="truncated"):
        _audit(p)


def test_quote_not_present_fails_closed(tmp_path):
    p = _html(tmp_path, "Some other claim")
    with pytest.raises(PortfolioInputError, match="not found"):
        _audit(p)


def test_script_borne_prompt_does_not_count_as_product_quote(tmp_path):
    p = _html(tmp_path, "<script>6.6 kV dynamic reactive compensation</script>")
    with pytest.raises(PortfolioInputError, match="not found"):
        _audit(p)


@pytest.mark.parametrize("url", [
    "http://supplier.example.org/products",
    "https://127.0.0.1/data",
    "https://user:password@supplier.example.org/a",
])
def test_bad_source_url_fails(tmp_path, url):
    p = _html(tmp_path, "6.6 kV dynamic reactive compensation")
    with pytest.raises(PortfolioInputError):
        _audit(p, url=url)


def test_symlink_or_malformed_quote_fails(tmp_path):
    p = _html(tmp_path, "6.6 kV dynamic reactive compensation")
    l = tmp_path / "alias.html"
    l.symlink_to(p)
    with pytest.raises(PortfolioInputError):
        _audit(l)
    with pytest.raises(PortfolioInputError):
        _audit(p, quotes=["fabricated"])
