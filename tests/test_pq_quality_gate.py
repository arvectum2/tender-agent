import copy

import pytest

from src.modules.market_intelligence.pq_quality_gate import audit


def _sources():
    c = {
        "schema_version": "pq-discovery-coverage/1",
        "candidate_denominator": 5,
        "source_category_counts": {"223fz": 3, "commercial_or_unresolved": 2},
        "numbered_223_candidate_lot_rows": 3,
        "distinct_223_notice_numbers": 2,
        "additional_lot_rows_sharing_223_notice": 1,
        "commercial_or_nonstandard_candidate_rows": 2,
        "primary_original_source_types": {
            "official_223_unique_notices_with_files": 1,
            "original_commercial_etp_unique_cards": 1,
            "original_b2b_center_unique_cards": 1,
        },
        "unique_notice_or_etp_numbers_with_primary_original": 3,
        "candidate_rows_with_primary_original": 4,
        "candidate_rows_without_verified_primary_original": 1,
        "source_state_counts": {
            "original_eis_documents_verified": 2,
            "original_commercial_card_html_sha_verified": 1,
            "original_commercial_b2b_html_sha_verified": 1,
            "official_notice_receipt_without_files": 1,
        },
        "period_search_coverage": [
            {"month": "2026-10", "coverage_state": "not_demonstrated",
             "zero_procurements_claimed": False}
        ],
    }
    p = {
        "schema_version": "pq-reviewed-project-links-audit/1",
        "candidate_rows": 5,
        "candidate_need_groups_after_only_proven_reissue_merges": 4,
        "source_verified_relation_edges": 2,
        "same_lot_reissue_links": 1,
        "shared_parent_program_edges_no_contract_merge": 1,
        "same_notice_distinct_lot_groups": [{
            "registry_number": "32616474682", "collapse_lots": False}],
        "national_unique_project_count": None,
        "verified_equipment_market_value_rub": None,
    }
    m = {
        "schema_version": "pq-verified-partial-market/1",
        "v29_candidate_leads": 5,
        "source_number_223_leads": 2,
        "source_223_lot_candidate_rows": 3,
        "non_223_or_nonstandard_leads": 2,
        "primary_eis_cases_with_files": 1,
        "primary_etp_cases_verified": 1,
        "primary_b2b_center_cases_verified": 1,
        "pq_equipment_market_value_rub": None,
        "verified_signed_contract_suppliers": 0,
        "sample_is_commission_bid_prices_not_signed_contracts": True,
        "completeness": "partial_do_not_extrapolate",
        "primary_eis_no_document_cases": ["32616400421"],
        "commission_facts_verified": 2,
        "public_223_contract_register_lots": 1,
    }
    return c, p, m


def test_partial_quality_passes_arithmetic_without_claiming_full_market():
    c, p, m = _sources()
    result = audit(coverage=c, projects=p, market=m)
    assert result["source_arithmetic_consistency_passed"] is True
    assert result["full_market_acceptance_passed"] is False
    assert result["source_missing_candidate_rows"] == 1
    assert result["months_without_exhaustive_source_discovery_proof"] == 1
    assert result["market_volume_rub"] is None
    assert all(x["passed"] for x in result["source_consistency_checks"])


def test_false_commercial_count_is_detected():
    c, p, m = _sources()
    m["non_223_or_nonstandard_leads"] = 3
    with pytest.raises(ValueError, match="true_non_223_candidate_rows"):
        audit(coverage=c, projects=p, market=m)


def test_adjacent_epc_total_cannot_be_promoted_to_market_value():
    c, p, m = _sources()
    m["pq_equipment_market_value_rub"] = "1517360443.50"
    with pytest.raises(ValueError, match="no_unverified_contract_or_tam_inference"):
        audit(coverage=c, projects=p, market=m)


def test_month_without_search_cannot_be_treated_as_zero_procurements():
    c, p, m = _sources()
    c["period_search_coverage"][0]["zero_procurements_claimed"] = True
    with pytest.raises(ValueError, match="no_false_negative"):
        audit(coverage=c, projects=p, market=m)
