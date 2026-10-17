"""Official first-party notice subject negative selection for PRICE-01, no pricing mix."""
import json
from pathlib import Path

import pytest

from scripts.price01.audit_second_notice_comparability import (
    AKSAY,
    AKSIOMA,
    assess_narrow_web_vs_gis,
    collect,
    original_notice_subject,
)

RECEIPT = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "docs/roadmap/price01_second_official_notice_incomparable_2026-10-18.json"
    ).read_text()
)


def _cases():
    return [dict(x) for x in RECEIPT["original_sources"]]


def test_source_verified_web_site_and_geographic_forestry_module_excluded():
    aksay, aksioma = _cases()
    result = assess_narrow_web_vs_gis(aksay, aksioma)
    assert result["candidate_registry_number"] == AKSIOMA
    assert result["candidate_comparability"] == "EXCLUDED_SCOPE_MISMATCH"
    assert result["approved_additional_comparable_procurements"] == 0
    assert result["cross_procurement_compatible_count_for_aksay_website"] == 1
    assert result["candidate_price_must_not_be_in_aksay_website_distribution"] is True
    assert result["price_forecast_performed"] is False
    assert result["autonomous_bid_performed"] is False


@pytest.mark.parametrize(("kind", "value"), [
    ("aksay_subject", "Оказание услуг по сопровождению сайта"),
    ("candidate_subject", "Услуга по разработке веб сайта"),
    ("candidate_subject", "Разработка программного обеспечения"),
    ("aksay_id", "0187200001726001304"),
    ("candidate_id", AKSAY),
])
def test_altered_source_never_becomes_an_admitted_comparable(kind, value):
    aksay, aksioma = _cases()
    if kind == "aksay_subject":
        aksay["original_procurement_subject"] = value
    elif kind == "candidate_subject":
        aksioma["original_procurement_subject"] = value
    elif kind == "aksay_id":
        aksay["procurement_number"] = value
    else:
        aksioma["procurement_number"] = value
    with pytest.raises(ValueError):
        assess_narrow_web_vs_gis(aksay, aksioma)


def test_no_original_local_files_needed_for_offline_regression(tmp_path):
    with pytest.raises(ValueError, match="unrecognized or unavailable"):
        original_notice_subject(tmp_path / "missing.zip", AKSAY)
    with pytest.raises(ValueError, match="unrecognized or unavailable"):
        original_notice_subject(tmp_path / "missing.zip", "9999999999999999999")


def test_bounded_source_receipt_claims_no_extra_comparable_procurement():
    assert RECEIPT["schema_version"] == "ta-price01-source-verified-negative-comparator-v1"
    assert RECEIPT["candidate_count"] == 1
    assert RECEIPT["approved_additional_comparable_procurements"] == 0
    assert RECEIPT["cross_procurement_compatible_count_for_aksay_website"] == 1
    assert RECEIPT["candidate_comparability"] == "EXCLUDED_SCOPE_MISMATCH"
    assert {c["procurement_number"] for c in RECEIPT["original_sources"]} == {AKSAY, AKSIOMA}
    for item in RECEIPT["original_sources"]:
        assert len(item["original_eis_zip_sha256"]) == 64
        assert len(item["source_notice_member_sha256"]) == 64
        assert item["source_is_original_verified_notice"] is True
    assert "лесного фонда" in RECEIPT["original_sources"][1]["original_procurement_subject"]
    assert RECEIPT["original_sources"][0]["original_procurement_subject"] == "Услуга по разработке веб сайта"


def test_collect_does_not_forge_originals_when_second_notice_missing(monkeypatch, tmp_path):
    import scripts.price01.audit_second_notice_comparability as audit

    def fake_subject(_path, number):
        if number == AKSAY:
            return _cases()[0]
        raise ValueError("no official candidate")

    monkeypatch.setattr(audit, "original_notice_subject", fake_subject)
    with pytest.raises(ValueError, match="no official candidate"):
        collect(root=tmp_path)
