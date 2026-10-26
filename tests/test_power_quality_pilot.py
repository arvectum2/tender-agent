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
    assert result["distinct_procedure_lots"] == 36
    assert result["period_sample_counts"] == {
        "2023": 1, "2024": 5, "2025": 5, "2026": 25
    }
    assert result["verified_award_count"] == 0
    assert result["verified_winner_count"] == 0
    assert result["market_size_rub"] is None
    assert result["population_completeness"] == "UNKNOWN"
    assert result["category_counts"] == {"ukrm": 29, "statcom": 5, "harmonic_filter": 2}
    assert result["work_package_counts"] == {
        "supply": 26, "maintenance": 3, "epc": 6, "design": 1
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
    assert report["seed_records"] == 37
    assert report["distinct_procedure_lots"] == 36
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


def test_primary_original_case_dossiers_keep_award_contract_and_tam_separate(seed):
    dossiers = json.loads((DATA / "official_case_dossiers_20261026.v1.json").read_text(encoding="utf-8"))
    cases = {case["number"]: case for case in dossiers["cases"]}
    assert set(cases) == {"32615614821", "32616120582", "32615969197", "32616497692", "0372100005626000037"}
    assert len(seed["records"]) == 36
    assert dossiers["verified_signed_contracts"] == 0
    assert dossiers["national_6_35kv_market_size_rub"] is None
    assert cases["32615614821"]["signed_contract_price_rub"] is None
    assert cases["32615614821"]["owner_supplied_equipment_estimate_rub"] == "4900000"
    assert cases["32615614821"]["selected_offer_rub"] == "1833358.30"
    assert cases["32616120582"]["selected_bid_application"] == "4149972340"
    assert cases["32616120582"]["selected_bid_price_rub"] == "17000000.00"
    assert cases["32616120582"]["signed_contract_verified"] is False
    assert cases["32616120582"]["equipment_contract_value_rub"] is None
    assert cases["0372100005626000037"]["target_6_35kv"] is False
    assert cases["32615969197"]["winner"] is None
    assert cases["32615969197"]["signed_contract"] is False
    assert cases["32615969197"]["initial_design_nmck_rub"] == "518960.00"


def test_official_source_coverage_is_bounded_and_not_national_completeness():
    proof = json.loads((DATA / "official_source_coverage_20261026.v3.json").read_text(encoding="utf-8"))
    assert proof["industrial_eight_regions"]["verified_day_slots"] == 33
    assert proof["industrial_eight_regions"]["sha_verified_archives"] == 42
    assert proof["industrial_eight_regions"]["incomplete_day_slots"] == 15
    assert proof["moscow_spb"]["verified_day_slots"] == 53
    assert proof["moscow_spb"]["sha_verified_archives"] == 176
    assert all(
        x["historical_exhaustiveness_verified"] is False
        and x["winner_contracts_verified"] is False
        and x["invalid_evidence_day_slots"] == 0
        for x in (proof["industrial_eight_regions"], proof["moscow_spb"])
    )


def test_karelia_alias_is_deduplicated_to_one_official_223fz_procedure(seed, ontology):
    report = analyze_pilot(seed, ontology)
    matches = [r for r in report["leads"] if r["procedure_id"] == "32616120582"]
    assert len(matches) == 1
    assert matches[0]["canonical_id"] == "223fz:32616120582:lot1"
    assert matches[0]["source_aliases"] == ["26Т0110040.0017"]
    assert len(matches[0]["evidence"]) == 3
    assert not any(r["procedure_id"] == "26Т0110040.0017" for r in report["leads"])

def test_20261026_extended_18_region_original_eis_coverage_snapshot():
    proof = json.loads((DATA / "official_source_coverage_20261026.v4.json").read_text(encoding="utf-8"))
    totals = proof["sampled_cohort_totals_not_national_market"]
    assert len(proof["cohorts"]) == 3
    assert totals["verified_day_slots"] == 144
    assert totals["sha_verified_archives"] == 298
    assert totals["xml_documents_inspected_not_unique_tenders"] == 21183
    assert totals["incomplete_day_slots"] == 45
    assert totals["invalid_evidence_day_slots"] == 0
    assert proof["assertions"]["national_market_census"] is False
    assert proof["assertions"]["equipment_turnover_estimate_rub"] is None


def test_fgi_portfolio_screen_does_not_assert_approved_substitution():
    proof = json.loads((DATA / "fgi_fit_source_bound_20261026.v1.json").read_text(encoding="utf-8"))
    assert proof["commercial_guardrails"]["direct_FGI_awards_verified"] == 0
    assert proof["commercial_guardrails"]["claims_of_substitution_approved"] == 0
    assert proof["commercial_guardrails"]["separate_PQ_hardware_TAM_rub"] is None
    assert all(row["strict_equivalent_approved"] is False for row in proof["technical_fit"])
    assert all(row["verified_FGI_vendor_award"] is False for row in proof["technical_fit"])


def test_20261026_secondary_extension_preserves_real_world_risk_gates(seed, ontology):
    report = analyze_pilot(seed, ontology)
    assert len(seed["records"]) == 36
    ids = {r["procedure_id"] for r in report["leads"]}
    assert {"РН41205245", "895449", "77907981", "77795100", "86829457", "1190793", "1234013"} <= ids
    assert report["market_size_rub"] is None
    assert report["verified_award_count"] == 0
    rosneft = next(r for r in report["leads"] if r["procedure_id"] == "РН41205245")
    assert rosneft["customer"]["inn"] == "2465142996"
    assert "четыре" in rosneft["notes"].lower() or "4 отдель" in rosneft["notes"]
    assert rosneft["nmck_rub"] is None
    rmk = next(r for r in report["leads"] if r["procedure_id"] == "895449")
    assert rmk["quantity"] == 6
    assert rmk["scope"] == "epc"
    assert "низковольтными" in rmk["notes"]
    unknown_2025 = next(r for r in report["leads"] if r["procedure_id"] == "86829457")
    assert unknown_2025["quantity"] is None
    assert unknown_2025["customer"]["inn"] is None
    for pid in ("1190793", "1234013"):
        row = next(r for r in report["leads"] if r["procedure_id"] == pid)
        assert row["platform"].startswith("Тендер.Про")
        assert row["quantity"] is None
        assert row["status"] == "unknown"
        assert row["nmck_rub"] is None


def test_elektroschit_two_2024_indices_are_not_mistaken_for_awards(seed, ontology):
    result = analyze_pilot(seed, ontology)
    buys = [r for r in result["leads"] if r["procedure_id"] in ("77907981", "77795100")]
    assert len(buys) == 2
    assert all(r["customer"]["inn"] is None for r in buys)
    assert all(r["reported_price_kind"] is None for r in buys)
    assert all(r["status"] == "unknown" for r in buys)
    assert result["verified_winner_count"] == 0


def test_primary_2024_2025_incremental_72_day_call_audit_is_source_bounded():
    data = json.loads((DATA / "official_source_coverage_20261026.v5.json").read_text(encoding="utf-8"))
    vals = data["sampled_cohort_totals_not_national_market"]
    assert vals["verified_day_slots"] == 202
    assert vals["incomplete_day_slots"] == 59
    assert vals["sha_verified_archives"] == 381
    assert vals["xml_documents_inspected_not_unique_tenders"] == 25629
    assert vals["invalid_evidence_day_slots"] == 0
    assert data["additional_2024_2025_official_collection"]["executed_soap_calls"] == 72
    assert data["additional_2024_2025_official_collection"]["reported_by_execution_verified"] == 58
    assert data["assertions"]["national_market_census"] is False
    assert data["assertions"]["equipment_turnover_estimate_rub"] is None


def test_vyartsilya_primary_10kv_3mvar_source_and_epc_price_split(seed, ontology):
    report = analyze_pilot(seed, ontology)
    row = next(r for r in report["leads"] if r["procedure_id"] == "32616497692")
    assert row["canonical_id"] == "223fz:32616497692:lot1"
    assert row["source_aliases"] == ["26Т0210040.0015"]
    assert row["nmck_rub"] == "79101498.40"
    assert row["quantity"] == 1
    assert row["status"] == "unknown"
    assert row["evidence"][0]["source_tier"] == "primary_platform"
    assert "3Мвар" in row["description"] or "3 Мвар" in row["description"]
    proof = json.loads((DATA / "official_case_dossiers_20261026.v1.json").read_text())
    c = next(x for x in proof["cases"] if x["number"] == "32616497692")
    assert c["ukrm"]["reactive_power_mvar"] == 3
    assert c["ukrm"]["equipment_specific_price_rub"] is None
    assert c["primary_budget_split_initial_with_vat"]["vyartsilya_ukrm_plus_bay_plus_cable_plus_design_rub"] == "8955286.21"
    assert c["primary_budget_split_initial_with_vat"]["oktyabr_transformer_and_reconstruction_rub"] == "70146212.19"
    assert c["signed_contract"] is False
    assert c["manufacturer_verified"] is False
    assert report["market_size_rub"] is None


def test_2025_ukrm6kv_rosneft_index_keeps_invented_notice_id_and_award_closed(seed, ontology):
    report=analyze_pilot(seed,ontology)
    item=next(r for r in report["leads"] if r["id"] == "pq-2025-rosneft-block-box-ukrm6kv-secondary")
    assert item["procedure_id"] is None
    assert "unverified" in item["canonical_id"]
    assert "6 кВ" in item["description"]
    assert item["customer"]["inn"] is None
    assert item["nmck_rub"] is None
    assert item["status"] == "unknown"
    assert item["evidence"][0]["source_tier"] == "third_party"
    assert report["market_size_rub"] is None
