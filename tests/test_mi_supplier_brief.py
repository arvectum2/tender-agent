"""S0: supplier profile is evidence-limited, safe and deterministic."""
import json
from pathlib import Path

import pytest

from src.modules.market_intelligence.portfolio_pipeline import PortfolioInputError
from src.modules.market_intelligence.supplier_brief import build_brief

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "data/market_intelligence/supplier_profiles/fgi_power_quality.json"


def test_fgi_profile_is_reproducible_and_never_claims_supplier_sales():
    b = build_brief(PROFILE, root=ROOT)
    assert b == build_brief(PROFILE, root=ROOT)
    assert b["status"] == "S0_UNVERIFIED"
    assert b["verified_signed_suppliers"] == 0
    assert b["verified_equipment_sales"] == 0
    assert b["study"]["voltage_kv"] == [6, 35]
    assert len(b["search_families"]) == 5
    assert len(b["profile_sha256"]) == 64


@pytest.mark.parametrize("field,value", [
    ("url", "http://example.com"),
    ("url", "https://127.0.0.1/x"),
    ("url", "https://bad:password@example.com/"),
    ("ontology", "../fake.yaml"),
    ("family", "unverified-nonexistent-family"),
    ("voltage", [-1, 35]),
    ("date", "2020-01-01"),
])
def test_profile_rejects_bad_or_unverified_inputs(tmp_path, field, value):
    obj = json.loads(PROFILE.read_text(encoding="utf8"))
    if field == "url":
        obj["supplier"]["official_portfolio_urls"] = [value]
    if field == "ontology":
        obj["ontology_file"] = value
    if field == "family":
        obj["family_ids"].append(value)
    if field == "voltage":
        obj["study"]["voltage_kv"] = value
    if field == "date":
        obj["study"]["from"] = value
    p = tmp_path / "profile.json"
    p.write_text(json.dumps(obj), encoding="utf8")
    with pytest.raises((PortfolioInputError, ValueError)):
        build_brief(p, root=ROOT)


def test_symlink_profile_denied(tmp_path):
    link = tmp_path / "alias"
    link.symlink_to(PROFILE)
    with pytest.raises(PortfolioInputError):
        build_brief(link, root=ROOT)
