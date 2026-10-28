"""Source-accountable S10 quality gate for a partial Power Quality market study.

A passing consistency audit permits publication of a clearly partial result.
It is never evidence of exhaustive market discovery or signed contract prices.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def audit(*, coverage: dict, projects: dict, market: dict,
          data_platform: dict | None = None) -> dict:
    if (coverage.get("schema_version") != "pq-discovery-coverage/1"
            or projects.get("schema_version") != "pq-reviewed-project-links-audit/1"
            or market.get("schema_version") != "pq-verified-partial-market/1"):
        raise ValueError("Unrecognized source-based MI report artifacts")
    observed = coverage["candidate_denominator"]
    kinds = coverage["source_category_counts"]
    states = coverage["source_state_counts"]
    etp_native = coverage["primary_original_source_types"]
    checks = [
        {
            "id": "candidate_partitions",
            "passed": observed == sum(kinds.values()) == market["v29_candidate_leads"],
            "expected": observed,
        },
        {
            "id": "distinct_223_notices_vs_lot_rows",
            "passed": (
                coverage["numbered_223_candidate_lot_rows"] ==
                coverage["distinct_223_notice_numbers"] +
                coverage["additional_lot_rows_sharing_223_notice"]
                and coverage["distinct_223_notice_numbers"] ==
                market["source_number_223_leads"]
                and coverage["numbered_223_candidate_lot_rows"] ==
                market["source_223_lot_candidate_rows"]
            ),
        },
        {
            "id": "true_non_223_candidate_rows",
            "passed": (
                coverage["commercial_or_nonstandard_candidate_rows"] ==
                market["non_223_or_nonstandard_leads"] ==
                observed - coverage["numbered_223_candidate_lot_rows"]
            ),
        },
        {
            "id": "distinct_primary_source_procedures",
            "passed": (
                coverage["unique_notice_or_etp_numbers_with_primary_original"] ==
                etp_native["official_223_unique_notices_with_files"] +
                etp_native.get("native_rad_223_unique_notice_originals_without_eis_duplicates", 0) +
                etp_native["original_commercial_etp_unique_cards"] +
                etp_native["original_b2b_center_unique_cards"]
                and etp_native["official_223_unique_notices_with_files"] ==
                market["primary_eis_cases_with_files"]
                and etp_native.get("native_rad_223_unique_notice_originals_without_eis_duplicates", 0) ==
                market.get("primary_rad_223_cases_without_eis_originals", 0)
                and etp_native["official_223_unique_notices_with_files"] +
                etp_native.get("native_rad_223_unique_notice_originals_without_eis_duplicates", 0) ==
                market.get("primary_223_cases_with_originals_from_any_source", market["primary_eis_cases_with_files"])
                and etp_native["original_commercial_etp_unique_cards"] ==
                market["primary_etp_cases_verified"]
                and etp_native["original_b2b_center_unique_cards"] ==
                market["primary_b2b_center_cases_verified"]
            ),
        },
        {
            "id": "per_row_primary_source_coverage",
            "passed": (
                coverage["candidate_rows_with_primary_original"] +
                coverage["candidate_rows_without_verified_primary_original"] == observed
                and coverage["candidate_rows_with_primary_original"] ==
                sum(states.get(name, 0) for name in (
                    "original_eis_documents_verified",
                    "original_commercial_card_html_sha_verified",
                    "original_commercial_b2b_html_sha_verified",
                    "original_native_rad_223_etp_sha_verified"))
            ),
        },
        {
            "id": "project_linkage_is_reviewed_and_only_explicit_reissues_merge",
            "passed": (
                projects["candidate_rows"] == observed
                and projects["candidate_need_groups_after_only_proven_reissue_merges"] <= observed
                and projects["national_unique_project_count"] is None
                and projects["verified_equipment_market_value_rub"] is None
                and projects["same_lot_reissue_links"] +
                projects["shared_parent_program_edges_no_contract_merge"] ==
                projects["source_verified_relation_edges"]
                and all(row.get("collapse_lots") is False for row in
                        projects["same_notice_distinct_lot_groups"])
            ),
        },
        {
            "id": "no_unverified_contract_or_tam_inference",
            "passed": (
                market["pq_equipment_market_value_rub"] is None
                and market["verified_signed_contract_suppliers"] == 0
                and market["sample_is_commission_bid_prices_not_signed_contracts"] is True
                and market["completeness"] == "partial_do_not_extrapolate"
            ),
        },
        {
            "id": "no_false_negative_on_unavailable_eis_files",
            "passed": (
                (sorted(market["primary_eis_no_document_cases"]) ==
                 sorted(coverage["eis_public_notice_ids_without_eis_originals"])
                 if "eis_public_notice_ids_without_eis_originals" in coverage
                 else len(market["primary_eis_no_document_cases"]) ==
                 states.get("official_notice_receipt_without_files", 0))
                and all(row["zero_procurements_claimed"] is False for row in
                        coverage["period_search_coverage"])
            ),
        },
    ]
    wrong = [row["id"] for row in checks if not row["passed"]]
    if wrong:
        raise ValueError("Source integrity/consistency gate failed: " + ", ".join(wrong))
    months_unknown = sum(
        row.get("coverage_state") != "verified_exhaustive_period_search"
        for row in coverage["period_search_coverage"])
    missing_source = coverage["candidate_rows_without_verified_primary_original"]
    no_documents = market["primary_eis_no_document_cases"]
    dp = data_platform or {}
    dp_status = dp.get("status") if data_platform is not None else "not_reported"
    dp_pending = int(dp.get("pending", 0)) if data_platform is not None else None
    dp_complete = dp_status == "complete" and dp_pending in (0, None)
    return {
        "schema_version": "pq-s10-quality-gate/1",
        "status": "partial_source_consistent_market_incomplete",
        "data_platform_extraction_status": dp_status,
        "data_platform_extraction_complete": dp_complete,
        "data_platform_pending_source_files": dp_pending,
        "data_platform_source_bytes_preserved": bool(dp.get("original_shas_preserved", True)),
        "source_arithmetic_consistency_passed": True,
        "full_market_acceptance_passed": False,
        "source_consistency_checks": checks,
        "observed_candidate_rows": observed,
        "unique_primary_source_procedures": coverage[
            "unique_notice_or_etp_numbers_with_primary_original"],
        "source_missing_candidate_rows": missing_source,
        "months_without_exhaustive_source_discovery_proof": months_unknown,
        "eis_cases_without_downloaded_originals": no_documents,
        "source_verified_commission_decisions": market["commission_facts_verified"],
        "public_223_contract_register_entries": market["public_223_contract_register_lots"],
        "verified_signed_contract_suppliers": 0,
        "market_volume_rub": None,
        "pending_gates": [
            "documented calendar-bound EIS and native ETP searches, not just number-based discovery",
            "primary original outcome/protocol sources for still-unverified commercial candidates",
            "signed supplier evidence where accessible; contract register price alone insufficient",
            "line-item PQ equipment price allocations for large EPC programs",
            "independent QA review of duplicate asset/project and legal rights restrictions",
            *(
                ["Data Platform SDK extraction blocked or unfinished; source SHA retained without promoting text"]
                if not dp_complete else []
            ),
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--coverage", type=Path, required=True)
    p.add_argument("--projects", type=Path, required=True)
    p.add_argument("--market", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = audit(
        coverage=json.loads(args.coverage.read_text(encoding="utf-8")),
        projects=json.loads(args.projects.read_text(encoding="utf-8")),
        market=json.loads(args.market.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "source_consistency_checks"},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
