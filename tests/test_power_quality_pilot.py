"""Real public-source seed contract tests; no claim of census or awards."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from src.modules.market_intelligence.power_quality_pilot import (
    PilotEvidenceError,
    analyze_pilot,
    render_pilot_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/market_intelligence/power_quality"


@pytest.fixture
def seed():
    return json.loads((DATA / "verified_public_leads_20261025.v2.json").read_text(encoding="utf-8"))


@pytest.fixture
def ontology():
    return yaml.safe_load((DATA / "ontology.v1.yaml").read_text(encoding="utf-8"))


def test_real_seed_is_bounded_and_has_no_invented_winners(seed, ontology):
    result = analyze_pilot(seed, ontology)
    assert result["distinct_procedure_lots"] == 27
    assert result["period_sample_counts"] == {
        "2023": 1, "2024": 1, "2025": 3, "2026": 22
    }
    assert result["verified_award_count"] == 0
    assert result["verified_winner_count"] == 0
    assert result["market_size_rub"] is None
    assert result["population_completeness"] == "UNKNOWN"
    assert result["category_counts"] == {"ukrm": 20, "statcom": 5, "harmonic_filter": 2}
    assert result["work_package_counts"] == {
        "supply": 19, "maintenance": 3, "epc": 4, "design": 1
    }


def test_exact_reporting_keeps_nmc_and_epc_gross_outside_component_tam(seed, ontology):
    result = analyze_pilot(seed, ontology)
    relevant = {r["procurement_id"]: r for r in result["market_model"]["procurements"]}
    assert relevant["32615969197"]["nmck_rub"] == "518960"
    assert relevant["32615969197"]["value_rub"] is None
    # The 21.12M reported total of an infrastructure EPC project is NOT
    # independently verified and not the price of the reactive compensator.
    assert result["market_model"]["observed_award_values_rub"]["epc_full_envelope_not_market_size"] == "0"
    assert result["market_model"]["market_size_rub"] is None


def test_no_false_open_status_or_sourced_winner_claim(seed, ontology):
    result = analyze_pilot(seed, ontology)
    assert result["market_model"]["counts"]["open_opportunities"] == 0
    assert all(p["winner"] is None for p in result["market_model"]["procurements"])
    assert all(p["attribution"] == "unpriced_or_not_awarded" for p in result["market_model"]["procurements"])


def test_all_source_links_and_excerpts_present(seed, ontology):
    for item in analyze_pilot(seed, ontology)["leads"]:
        assert item["evidence"]
        assert all(ev["source_tier"] in {"third_party", "primary_platform"} for ev in item["evidence"])
        assert all(ev["url"].startswith("https://") for ev in item["evidence"])
        assert all(ev["excerpt"] and ev["locator"] for ev in item["evidence"])


def test_repeated_lukoil_not_collapsed_as_mirror(seed, ontology):
    report = analyze_pilot(seed, ontology)
    lukoil = next(x for x in report["buyers_in_seed"] if "ЛУКОЙЛ-Западная Сибирь" in x["name"])
    assert lukoil["procedure_count"] == 2
    ids = [r["procedure_id"] for r in report["leads"] if "ЛУКОЙЛ-Западная Сибирь" in (r["customer"] or {}).get("name", "")]
    assert ids == ["COM07102500074", "COM16012600053"]


def test_no_bids_is_not_a_confirmed_cancelled_contract(seed, ontology):
    report = analyze_pilot(seed, ontology)
    proc = next(r for r in report["leads"] if r["procedure_id"] == "32615969197")
    assert proc["status"] == "no_bids_reported"
    assert proc["reported_price_kind"] == "nmck"
    assert proc.get("winner") is None
    assert "не подано" in proc["evidence"][0]["excerpt"]


def test_unverified_identifiers_not_promoted_to_known_ones(seed, ontology):
    report = analyze_pilot(seed, ontology)
    sukhodol = next(r for r in report["leads"] if r["id"] == "pq-2025-suhodol")
    assert sukhodol["procedure_id"] is None
    assert "unverified" in sukhodol["canonical_id"]


def test_duplicate_source_mirror_consolidates_with_evidence(seed, ontology):
    row = deepcopy(seed["records"][0])
    row["id"] += "-mirror"
    row["evidence"][0]["url"] = "https://example.org/source/mirror"
    seed["records"].append(row)
    report = analyze_pilot(seed, ontology)
    assert report["seed_records"] == 28
    assert report["distinct_procedure_lots"] == 27
    assert report["mirror_duplicates_removed"] == 1


def test_different_buyer_identity_rejected_as_conflicting_merge(seed, ontology):
    row = deepcopy(seed["records"][0])
    row["id"] += "-conflict"
    row["customer"] = {"name": "Different company", "inn": "7701020102"}
    seed["records"].append(row)
    with pytest.raises(PilotEvidenceError, match="canonical identity conflict"):
        analyze_pilot(seed, ontology)


@pytest.mark.parametrize(
    "field,value",
    [
        ("family", "not-a-category"), ("scope", "winning_vendor"),
        ("status", "awarded"), ("publication_date", "2022-02-04"),
        ("date_basis", "unknown_date"), ("quantity", -1),
        ("reported_price_kind", "final_contract"),
    ],
)
def test_unproven_facts_are_rejected(seed, ontology, field, value):
    seed["records"][0][field] = value
    with pytest.raises(PilotEvidenceError):
        analyze_pilot(seed, ontology)


def test_seed_must_not_invent_winning_supplier(seed, ontology):
    seed["records"][0]["winner"] = {"name": "Fake", "inn": "7701020102"}
    with pytest.raises(PilotEvidenceError, match="winner/award forbidden"):
        analyze_pilot(seed, ontology)


def test_unsafe_url_or_missing_locator_fails_closed(seed, ontology):
    seed["records"][0]["evidence"][0]["url"] = "file:///etc/passwd"
    with pytest.raises(PilotEvidenceError, match="HTTPS"):
        analyze_pilot(seed, ontology)
    seed["records"][0]["evidence"][0]["url"] = "https://example.org/a"
    seed["records"][0]["evidence"][0]["locator"] = ""
    with pytest.raises(PilotEvidenceError, match="locator"):
        analyze_pilot(seed, ontology)


def test_markdown_has_no_market_claim(seed, ontology):
    md = render_pilot_markdown(analyze_pilot(seed, ontology))
    assert "НЕ полный российский рынок" in md
    assert "COM16012600053" in md
    assert "не определён" in md


def test_pq_addendum_keeps_mixed_lot_and_unverified_contract_out_of_tam(seed, ontology):
    report = analyze_pilot(seed, ontology)
    mixed = next(row for row in report["leads"] if row["procedure_id"] == "1221629")
    assert mixed["family"] == "harmonic_filter"
    assert mixed["quantity"] == 2
    assert mixed["nmck_rub"] is None
    reconstruction = next(row for row in report["leads"] if row["procedure_id"] == "32615614821")
    assert reconstruction["scope"] == "epc"
    assert reconstruction["nmck_rub"] == "1432983.66"
    assert "1 833 358,30" in reconstruction["notes"]
    assert report["verified_award_count"] == 0
    assert report["market_size_rub"] is None


def test_pq_current_commercial_leads_not_falsely_claimed_open_or_awarded(seed, ontology):
    report = analyze_pilot(seed, ontology)
    for number in ("РН61004155", "АП125337"):
        row = next(r for r in report["leads"] if r["procedure_id"] == number)
        assert row["status"] == "unknown"
        assert row["nmck_rub"] is None
        assert row.get("winner") is None
    assert report["market_model"]["counts"]["open_opportunities"] == 0


def test_original_20261024_source_and_report_baselines_are_preserved():
    old_seed = json.loads((DATA / "verified_public_leads.v1.json").read_text(encoding="utf-8"))
    old_report = json.loads((DATA / "pilot_report.v1.json").read_text(encoding="utf-8"))
    assert old_seed["as_of"] == old_report["as_of"] == "2026-10-24"
    assert len(old_seed["records"]) == old_report["distinct_procedure_lots"] == 12
