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
    assert result["distinct_procedure_lots"] == 45
    assert result["period_sample_counts"] == {
        "2023": 1, "2024": 6, "2025": 7, "2026": 31
    }
    assert result["verified_award_count"] == 0
    assert result["verified_winner_count"] == 0
    assert result["market_size_rub"] is None
    assert result["population_completeness"] == "UNKNOWN"
    assert result["category_counts"] == {"ukrm": 37, "statcom": 5, "harmonic_filter": 2, "power_quality_system": 1}
    assert result["work_package_counts"] == {
        "supply": 30, "maintenance": 5, "epc": 7, "design": 3
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
        assert all(ev["source_tier"] in {"third_party", "primary_platform", "primary_judicial"} for ev in item["evidence"])
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
    assert report["seed_records"] == 46
    assert report["distinct_procedure_lots"] == 45
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
    assert set(cases) == {"32615614821", "32616120582", "32615969197", "32616103025", "32616497692", "32616433248", "32616412267", "32616280467", "0372100005626000037", "court:A75-24845/2025"}
    assert len(seed["records"]) == 45
    assert dossiers["verified_signed_contracts"] == 4
    assert dossiers["national_6_35kv_market_size_rub"] is None
    assert cases["32615614821"]["signed_contract_price_rub"] == "1833358.30"
    assert cases["32615614821"]["owner_supplied_equipment_estimate_rub"] == "4900000"
    assert cases["32615614821"]["selected_offer_rub"] == "1833358.30"
    assert cases["32616120582"]["selected_bid_application"] == "4149972340"
    assert cases["32616120582"]["selected_bid_price_rub"] == "17000000.00"
    assert cases["32616120582"]["signed_contract_verified"] is True
    assert cases["32616120582"]["signed_contract_price_rub"] == "17000000.00"
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
    assert len(matches[0]["evidence"]) == 4
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
    assert len(seed["records"]) == 45
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


def test_pionerskaya_2026_two_procurements_one_unfulfilled_project(seed, ontology):
    report = analyze_pilot(seed, ontology)
    first = next(x for x in report["leads"] if x["procedure_id"] == "32615969197")
    repeat = next(x for x in report["leads"] if x["procedure_id"] == "32616103025")
    assert first["project_equivalence_key"] == repeat["project_equivalence_key"]
    assert first["canonical_id"] != repeat["canonical_id"]
    assert repeat["related_procedures"] == ["32615969197"]
    assert first["status"] == repeat["status"] == "no_bids_reported"
    assert first["nmck_rub"] == "518960"
    assert repeat["nmck_rub"] == "518960.00"
    assert repeat["evidence"][0]["source_tier"] == "primary_platform"
    assert repeat["quantity"] is None
    assert report["market_size_rub"] is None
    dossiers = json.loads((DATA / "official_case_dossiers_20261026.v1.json").read_text())
    p = next(x for x in dossiers["cases"] if x["number"] == "32616103025")
    assert p["unique_market_project_count_increment"] == 0
    assert p["separate_procurement_procedure_count_increment"] == 1
    assert p["winner_in_original_protocol"] is None
    assert p["signed_contract_price_rub"] is None


def test_verified_35kv_3p5mvar_source_bidder_and_estimate_are_not_signed_contract(seed, ontology):
    report=analyze_pilot(seed, ontology)
    row=next(x for x in report["leads"] if x["procedure_id"]=="32616433248")
    assert row["canonical_id"] == "223fz:32616433248:lot1"
    assert row["source_aliases"] == ["26Т0210040.0017"]
    assert row["quantity"] == 1
    assert row["nmck_rub"] == "56330673.93"
    assert row["scope"] == "epc"
    assert row["status"] == "source_reports_closed"
    assert "3,5 Мвар" in row["description"]
    assert row["evidence"][0]["source_tier"] == "primary_platform"
    assert report["verified_award_count"] == 0
    assert report["market_size_rub"] is None

    docs=json.loads((DATA / "official_case_dossiers_20261026.v1.json").read_text(encoding="utf-8"))
    case=next(x for x in docs["cases"] if x["number"] == "32616433248")
    assert case["ukrm"]["voltage_kv"] == 35
    assert case["ukrm"]["rated_mvar_min"] == 3.5
    assert case["ukrm"]["step_primary_kvar"] == 1000
    assert case["ukrm"]["additional_step_kvar"] == 500
    assert case["ukrm"]["equipment_estimate_2025_base_rub"] == "10780666.67"
    assert case["protocol_applicant"]["inn"] == "7801564611"
    assert case["protocol_applicant"]["ogrn"] == "1117847714742"
    assert case["protocol_applicant"]["bid_offer_rub"] == "56330673.93"
    assert case["commission_result"]["failed_competition_due_to_one_bid"] is True
    assert case["commission_result"]["pre_contract_price_reduction_negotiations_recommended"] is True
    assert case["signed_contract_verified"] is False
    assert case["signed_contract_price_rub"] is None
    assert case["manufacturer_of_UKRM_verified"] is False
    assert case["equipment_only_final_price_rub"] is None


def test_2025_progazstroy_and_rn_burenie_keep_sourcing_and_services_distinct(seed,ontology):
    report=analyze_pilot(seed,ontology)
    prod=next(x for x in report["leads"] if x["procedure_id"]=="4256170")
    assert prod["publication_date"] == "2025-12-01"
    assert prod["quantity"] == 2
    assert prod["scope"] == "supply"
    assert prod["customer"]["inn"] == "9709099564"
    assert "10кВ" in prod["description"] or "10 кВ" in prod["description"]
    assert prod["evidence"][0]["source_tier"]=="third_party"
    assert prod["status"] == "unknown"
    service=next(x for x in report["leads"] if x["procedure_id"]=="РН51202455")
    assert service["customer"]["inn"] == "7706613770"
    assert service["scope"] == "maintenance"
    assert "6 кВ" in service["description"]
    assert service["nmck_rub"] is None
    assert report["verified_award_count"] == 0
    assert report["market_size_rub"] is None


def test_primary_angarsk_6kv_pq_services_have_protocol_prices_but_no_equipment_revenue(seed,ontology):
    report=analyze_pilot(seed,ontology)
    p=next(r for r in report["leads"] if r["procedure_id"]=="32616412267")
    assert p["customer"]["inn"] == "3801006828"
    assert p["scope"] == "maintenance"
    assert p["quantity"] is None
    assert p["nmck_rub"] == "4295282.00"
    assert p["evidence"][0]["source_tier"] == "primary_platform"
    assert "2 590 000" in p["evidence"][0]["excerpt"]
    cases=json.loads((DATA/"official_case_dossiers_20261026.v1.json").read_text(encoding="utf-8"))
    c=next(row for row in cases["cases"] if row["number"]=="32616412267")
    assert c["installed_ukrm"]["count"] == 2
    assert c["installed_ukrm"]["each_kvar"] == 900
    assert c["installed_ukrm"]["already_installed"] is True
    assert c["official_final_protocol"]["first_place_application"] == "2"
    assert c["official_final_protocol"]["first_place_offer_rub"] == "2590000.00"
    assert c["official_final_protocol"]["signed_contract_price_verified"] is False
    assert c["cost_estimate"]["both_installed_ukrm_testing_section_rub"] == "702878.82"
    assert c["cost_estimate"]["not_new_equipment_sales"] is True
    assert c["market_6_35kv_new_equipment_tam_rub"] is None
    assert report["market_size_rub"] is None


def test_dynamic_pq_original_10kv_160kvar_design_procedure_keeps_hw_sales_null(seed,ontology):
    report=analyze_pilot(seed,ontology)
    lead=next(row for row in report["leads"] if row["procedure_id"]=="32616280467")
    assert lead["family"]=="power_quality_system"
    assert lead["scope"]=="design"
    assert lead["customer"]["inn"]=="6450925977"
    assert lead["nmck_rub"]=="3683790.00"
    assert lead["quantity"]==1
    assert lead["evidence"][0]["source_tier"]=="primary_platform"
    source=json.loads((DATA/"official_case_dossiers_20261026.v1.json").read_text())
    case=next(x for x in source["cases"] if x["number"]=="32616280467")
    assert case["technology"]["required_reactive_inductive_compensation_kvar_min"]==160
    assert case["technology"]["nominal_network_kv"]==10
    assert case["technology"]["cabinet_type_named"]=="АДФ-У"
    assert case["primary_final_protocol"]["best_application_bid_rub"]=="3680106.21"
    assert case["primary_final_protocol"]["second_bid_rub"]=="3681948.11"
    assert case["primary_final_protocol"]["signed_contract_registry_verified"] is True
    assert case["secondary_contract_registry_claim"]["verified_original_signed_registry"] is False
    assert case["equipment_sale_rub"] is None
    assert case["new_equipment_purchased_in_this_tender"] is False
    assert report["market_size_rub"] is None


def test_rd223_original_registry_two_contracts_without_fake_hardware_revenue(seed,ontology):
    snapshot=json.loads((DATA/"official_registry_contracts_20261026.v1.json").read_text())
    assert snapshot["registered_contract_count"] == 4
    assert snapshot["primary_version_count"] == 5
    assert snapshot["equipment_only_signed_contracts_verified"] == 0
    by={x["registry_number"]:x for x in snapshot["contracts"]}
    assert len(by["50277071467260002650000"]["official_revisions"]) == 2
    first=by["50277071467260002650000"]["contract_latest"]
    assert first["linked_procurement"]=="32615614821"
    assert first["contract_date"]=="2026-04-14"
    assert first["registered_total_price_rub"]=="1833358.30"
    assert first["supplier_inn"] is None
    assert first["pq_equipment_sale_rub"] is None
    second=by["56450925977260018070000"]["contract_latest"]
    assert second["linked_procurement"]=="32616280467"
    assert second["registered_total_price_rub"]=="3680106.21"
    assert second["supplier_inn"] is None
    assert second["pq_equipment_sale_rub"] is None
    service=by["53801006828260000720000"]["contract_latest"]
    assert service["linked_procurement"]=="32616412267"
    assert service["contract_date"]=="2026-10-19"
    assert service["registered_total_price_rub"]=="2639026.64"
    assert service["supplier_inn"] is None
    assert service["pq_equipment_sale_rub"] is None
    sortavala=by["57802312751260008280000"]["contract_latest"]
    assert sortavala["linked_procurement"]=="32616120582"
    assert sortavala["contract_date"]=="2026-08-19"
    assert sortavala["registered_total_price_rub"]=="17000000.00"
    assert sortavala["supplier_inn"] is None
    assert sortavala["pq_equipment_sale_rub"] is None
    rows=analyze_pilot(seed,ontology)["leads"]
    for purchase in ("32615614821","32616280467","32616412267","32616120582"):
        r=next(x for x in rows if x["procedure_id"]==purchase)
        assert r["registry_contract"]["signed_contract_registry_verified"] is True
        assert r["registry_contract"]["equipment_price_component_rub"] is None


def test_court_verified_one_medium_voltage_equipment_supply_is_not_national_tam(seed,ontology):
    report=analyze_pilot(seed,ontology)
    case=next(r for r in report["leads"] if r["id"]=="pq-2024-judicial-contract-electroschit-ukrm-10p5-13mvar")
    assert case["date_basis"]=="judicial_contract_date"
    assert case["publication_date"]=="2024-10-29"
    assert case["procedure_id"] is None
    assert case["contract_number"]=="03/34-24"
    assert case["customer"]["inn"]=="8602177031"
    assert case["supplier_by_court"]["inn"]=="1644023432"
    assert case["verified_equipment_supply_contract_price_rub"]=="21307585.20"
    assert case["evidence"][0]["source_tier"]=="primary_judicial"
    assert case["nmck_rub"] is None
    assert report["market_size_rub"] is None
    proof=json.loads((DATA/"verified_equipment_supply_court_20261026.v1.json").read_text())
    assert proof["primary_judicial_case_count"]==1
    assert proof["verified_price_of_specific_medium_voltage_equipment_rub"]=="21307585.20"
    assert proof["not_national_equipment_market_size"] is True


def test_0p4kv_commercial_false_positive_removed_and_gaysky_gok_is_distinct(seed,ontology):
    report=analyze_pilot(seed,ontology)
    low=next(r for r in report["leads"] if r["procedure_id"]=="945712")
    assert low["target_6_35kv"] is False
    assert low["voltage_kv_verified_secondary"]==0.4
    assert low["quantity"]==9
    high=next(r for r in report["leads"] if r["procedure_id"]=="119199-ТТ")
    assert high["customer"]["inn"]=="5604000700"
    assert high["quantity"]==2
    assert high["status"]=="source_reports_closed"
    assert "6 кВ" in high["description"]
    assert high["nmck_rub"] is None


def test_angarsk_original_rd223_registered_service_total_is_not_best_offer_or_hardware(seed):
    proof=json.loads((DATA/"official_case_dossiers_20261026.v1.json").read_text())
    case=next(x for x in proof["cases"] if x["number"]=="32616412267")
    assert case["official_registered_contract_number"]=="53801006828260000720000"
    assert case["signed_contract_registry_verified"] is True
    assert case["signed_contract_price_rub"]=="2639026.64"
    assert case["official_final_protocol"]["first_place_offer_rub"]=="2590000.00"
    assert case["protocol_best_bid_differs_from_registered_price"] is True
    assert case["registered_value_is_service_not_new_ukrm"] is True
    assert case["legal_executor_inn_from_public_registry"] is None
    assert case["installed_ukrm"]["already_installed"] is True


def test_gaysky_2026_two_procedures_but_unverified_two_independent_demands(seed,ontology):
    r=analyze_pilot(seed,ontology)
    first=next(row for row in r["leads"] if row["procedure_id"]=="119199-ТТ")
    second=next(row for row in r["leads"] if row["procedure_id"]=="135171-ТТ")
    assert first["canonical_id"] != second["canonical_id"]
    assert first["project_equivalence_key"]==second["project_equivalence_key"]
    assert first["possible_related_procedures"] == ["135171-ТТ"]
    assert second["possible_related_procedures"] == ["119199-ТТ"]
    assert first["customer"]["inn"] == second["customer"]["inn"]=="5604000700"
    assert first["quantity"]==second["quantity"]==2
    assert first["nmck_rub"] is None and second["nmck_rub"] is None
    assert all(x["evidence"][0]["source_tier"] == "third_party" for x in (first,second))
    assert r["market_size_rub"] is None


def test_sortavala_6kv_epc_registry_contract_not_price_of_bank(seed):
    registry=json.loads((DATA/"official_registry_contracts_20261026.v1.json").read_text())
    contracts={x["registry_number"]:x for x in registry["contracts"]}
    x=contracts["57802312751260008280000"]["contract_latest"]
    assert x["registered_total_price_rub"]=="17000000.00"
    assert x["buyer_inn"]=="7802312751"
    assert x["supplier_inn"] is None
    assert x["pq_equipment_sale_rub"] is None
    row=next(r for r in seed["records"] if r["procedure_id"]=="32616120582")
    assert row["registry_contract"]["signed_contract_registry_verified"] is True
    assert row["registry_contract"]["equipment_price_component_rub"] is None
    assert row["nmck_rub"] == "21120361.66"
