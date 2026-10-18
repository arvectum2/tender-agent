"""Source-bounded archival PRICE-01 prices for the existing private Operator Workspace.

Static, version-controlled *aggregate* of an independently EIS-verified original
protocol. No bidder-by-bidder rows, external contacts, DB or privileged file reads.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from fastapi import HTTPException

from src.tender_research.competitive_bid_protocol import AKSAY, AKSAY_ZIP_SHA256

_AGGREGATE_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs/roadmap/price01_aksay_original_protocol_baseline_2026-10-17.json"
)
_JSON_SHA = "8f5c776a269f8a4ca0363bc1537f7d95651f62e67ed964f9e42a94bce1868e8c"
_CSV_SHA = "264b4a16a149eaeb4fdd76adb03931a4e54c958e8b30212227f05200714638b0"
_XML_SHA = "2b9f510c48e7d828c432e32b4dca3a4fff8edb75c66c3da37d46a12af3456af5"
_REQUIRED = {
    "bids_total": 55, "admitted_count": 45, "rejected_count": 10,
    "original_bid_rows_individually_cross_checked": 55,
    "original_records_consistent": True, "comparable_distinct_procurements": 1,
    "cross_procurement_price_evidence": "INSUFFICIENT_EVIDENCE",
    "cost_break_even_scenarios": None, "is_win_probability_forecast": False,
    "is_bid_recommendation": False, "submission_or_payment_performed": False,
}
_PRICE_AMOUNTS = re.compile(r"\d{1,12}(?:\.\d{1,2})?\Z")


def archived_competitive_price_context(registry_number: str) -> dict:
    """No accidental substitution of the Aksay bid distribution for another SOW."""
    if not re.fullmatch(r"\d{19}", registry_number) or registry_number != AKSAY:
        raise HTTPException(status_code=404, detail="Нет проверенного конкурентного протокола для этой закупки")
    try:
        if not _AGGREGATE_PATH.is_file() or _AGGREGATE_PATH.stat().st_size > 16_384:
            raise ValueError("archival aggregate missing or unexpectedly large")
        report = json.loads(_AGGREGATE_PATH.read_text(encoding="utf8"))
        for field, expected in _REQUIRED.items():
            if report.get(field) != expected:
                raise ValueError("archived protocol aggregate changed")
        if (
            report.get("schema_version") != "ta-price01-protocol-one-procedure-v1"
            or report.get("procurement_number") != AKSAY
            or report.get("protocol_date") != "2026-10-14"
            or report.get("original_eis_zip_sha256") != AKSAY_ZIP_SHA256
            or report.get("official_protocol_xml_sha256") != _XML_SHA
            or report.get("statistics_json_sha256") != _JSON_SHA
            or report.get("bids_csv_sha256") != _CSV_SHA
        ):
            raise ValueError("original source provenance mismatch")
        prices = report["admitted_bid_prices_rub"]
        if set(prices) != {"min", "q1_nearest_rank", "median", "q3_nearest_rank", "max"}:
            raise ValueError("price statistics fields changed")
        for amount in (*prices.values(), report["winner"]["price_rub"],
                       report["arvectum_bid"]["price_rub"], report["nmck_rub"]):
            if not isinstance(amount, str) or _PRICE_AMOUNTS.fullmatch(amount) is None:
                raise ValueError("malformed archived protocol price")
        if (
            [prices["min"], prices["median"], prices["max"]]
            != ["28400.0", "74000.0", "150000.0"]
            or prices["q1_nearest_rank"] != "54900.0"
            or prices["q3_nearest_rank"] != "110000.0"
            or report["winner"] != {"application_id": "122023425", "rank": 1, "price_rub": "28400.0"}
            or report["arvectum_bid"].get("application_id") != "122031738"
            or report["arvectum_bid"].get("rank") != 38
            or report["arvectum_bid"].get("price_rub") != "119000.0"
            or report["arvectum_bid"].get("admitted") is not True
            or report["arvectum_bid"].get("admitted_offers_with_lower_price") != 37
            or report.get("rejection_reason_counts") != {
                "missing_software_registry_document_old_notice": 9,
                "inapplicable_software_registry_entry": 1,
            }
        ):
            raise ValueError("reviewed source factual values changed")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Проверенный архив цен временно недоступен; данные не подменяются",
        ) from exc
    # Strict allowlisted public aggregate projection; no raw per-app bidder rows or private DB.
    return {
        "state": "VERIFIED_ARCHIVED_SINGLE_PROCEDURE",
        "registry_number": AKSAY,
        "protocol_date": report["protocol_date"],
        "currency": "RUB",
        "evidence": {
            "eis_original_zip_sha256": AKSAY_ZIP_SHA256,
            "eis_original_xml_sha256": _XML_SHA,
            "normalized_json_sha256": _JSON_SHA,
            "normalized_csv_sha256": _CSV_SHA,
            "bid_rows_crosschecked_with_original": 55,
        },
        "nmck_rub": report["nmck_rub"],
        "admitted_count": 45,
        "rejected_count": 10,
        "admitted_only_prices_rub": dict(prices),
        "winner_price_rub": report["winner"]["price_rub"],
        "company_price_rub": report["arvectum_bid"]["price_rub"],
        "company_rank_admitted": 38,
        "rejected_reason_counts": dict(report["rejection_reason_counts"]),
        "cross_procurement_comparison_state": "INSUFFICIENT_EVIDENCE",
        "cost_basis": "NOT_PROVIDED",
        "cost_scenarios": None,
        "forecast_or_bid_recommendation": False,
        "company_go": False,
    }


_COHORT_REPORT_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs/roadmap/price01_website_cohort_official_2026-10-18.json"
)
_COHORT_REPORT_SHA256 = "65038a3e607bb2e2e51b1dffc05ee10c36a00b59e8817141a4c6be3146a9e963"
_COHORT_CASES = {
    "0158300034526000388": ("BASELINE_ONLY", 55, 45),
    "0132300001726000686": ("NOT_COMPARABLE_REGULATED_OFFICIAL_SITE", 6, 1),
    "0119200000126013647": ("RELATED_SCOPE_REQUIRES_NORMALIZATION", 30, 30),
    "0377100005726000128": ("RELATED_SCOPE_REQUIRES_NORMALIZATION", 28, 28),
    "0372200203126000012": ("NOT_COMPARABLE_CUSTOM_CMS", 10, 9),
    "0884200000526000012": ("NOT_COMPARABLE_COMPOUND_SUPPORT", 11, 11),
}


def archived_website_price_cohort() -> dict:
    """Five separately sourced historical website cases + Aksay, NEVER a blend."""
    try:
        if (_COHORT_REPORT_PATH.is_symlink()
                or not _COHORT_REPORT_PATH.is_file()
                or _COHORT_REPORT_PATH.stat().st_size > 64_000):
            raise ValueError("website cohort aggregate unavailable")
        raw = _COHORT_REPORT_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != _COHORT_REPORT_SHA256:
            raise ValueError("website source-bound receipt SHA mismatch")
        report = json.loads(raw)
        if (
            report.get("schema_version") != "ta-price01-official-website-original-scope-cohort-v1"
            or report.get("original_verified_procedures") != 6
            or report.get("original_procedures_with_admitted_final_prices") != 5
            or report.get("original_procedures_without_final_price") != 1
            or report.get("new_admitted_same_basket_procurements") != 0
            or report.get("aksay_website_same_basket_count") != 1
            or report.get("profit_or_win_probability_forecast") is not False
            or report.get("autonomous_bid_or_payment") is not False
        ):
            raise ValueError("unverified cohort schema or inappropriate recommendation")
        cases = report["cases"]
        if not isinstance(cases, list) or len(cases) != 6:
            raise ValueError("historical cohort case count changed")
        out = []
        for case in cases:
            num = case["registry_number"]
            expected = _COHORT_CASES.get(num)
            if expected is None or (case["scope_comparison_state"], case["total"], case["admitted"]) != expected:
                raise ValueError("unknown/changed original cohort source")
            if (
                case["accepted_to_aksay_normalized_basket"] is not False
                or case["total"] - case["admitted"] != case["rejected"]
                or not all(len(case[k]) == 64 for k in (
                    "official_zip_sha256", "original_final_xml_sha256",
                    "original_technical_scope_docx_sha256", "original_notice_xml_sha256",
                ))
                or not case["source_scope_anchors_verified"]
            ):
                raise ValueError("source provenance or comparison integrity mismatch")
            for field in ("admitted_price_low_rub", "admitted_price_median_rub", "admitted_price_high_rub"):
                price = case[field]
                if price is not None and (not isinstance(price, str) or re.fullmatch(r"\d{1,12}(?:\.\d{1,3})?", price) is None):
                    raise ValueError("invalid original monetary evidence")
            if case["source_price_field_state"] == "MISSING_FINAL_PRICE_IN_ORIGINAL_EOK_PROTOCOL":
                if any(case[f] is not None for f in (
                    "admitted_price_low_rub", "admitted_price_median_rub", "admitted_price_high_rub",
                )):
                    raise ValueError("missing final price replaced with unsupported amount")
            elif case["source_price_field_state"] != "VERIFIED_ADMITTED_FINAL_PRICE":
                raise ValueError("unverified original price status")
            out.append({
                "registry_number": num,
                "original_notice_subject": case["original_notice_subject"],
                "total": case["total"],
                "admitted": case["admitted"],
                "rejected": case["rejected"],
                "admitted_price_status": case["source_price_field_state"],
                "admitted_price_low_rub": case["admitted_price_low_rub"],
                "admitted_price_median_rub": case["admitted_price_median_rub"],
                "admitted_price_high_rub": case["admitted_price_high_rub"],
                "sub_ruble_source_bid_observed": case["extreme_sub_ruble_bid_detected"],
                "original_scope_comparison_state": case["scope_comparison_state"],
                "original_scope_comparison_reason": case["scope_comparison_reason"],
                "scope_original_anchors": list(case["source_scope_anchors_verified"]),
                "eis_original_zip_sha256": case["official_zip_sha256"],
                "original_final_xml_sha256": case["original_final_xml_sha256"],
                "original_tz_docx_sha256": case["original_technical_scope_docx_sha256"],
            })
        if len({row["registry_number"] for row in out}) != 6:
            raise ValueError("duplicate independent source cohort")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Проверенный архив сайтов недоступен: показывать неподтверждённые цены запрещено",
        ) from exc
    return {
        "schema_version": "ta-price01-website-cohort-private-projection-v1",
        "state": "INDEPENDENT_HISTORICAL_WEBSITE_CASES_NOT_POOLED",
        "source_cohort_receipt_sha256": _COHORT_REPORT_SHA256,
        "verified_original_procedures": 6,
        "same_basket_procurements_as_aksay": 1,
        "additional_equivalent_procurements": 0,
        "all_prices_are_individual_protocol_statistics": True,
        "market_aggregated_price_rub": None,
        "forecast_or_bid_recommendation": False,
        "owner_commercial_go": False,
        "cases": out,
    }


_WORKLOAD_REPORT_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs/roadmap/price01_workload_normalization_2026-10-18.json"
)
_WORKLOAD_REPORT_SHA256 = "fefb77d99df0999e626a916d3edc58a942a75cec894c7c56da309f1f6b0ce74f"
_WORKLOAD_CASES = {
    "0158300034526000388": ("AKSAY", 14, 8),
    "0119200000126013647": ("KRASNOYARSK", 10, 9),
    "0377100005726000128": ("CHEMAL", 21, 9),
}
_WORKLOAD_ORIGINAL_DOCX_SHA256 = {
    "0158300034526000388": "0e40a162e85a69b496fb350e846a39c90695033fd5a46ebfb2683f9996132f7a",
    "0119200000126013647": "35110af58a89e8d1c77ac6077d675e146af826269f149463d7f0a4b730fdaac4",
    "0377100005726000128": "a099f70cda44c5cdd52fe5ddcab6c462d24a5222f167d97d88d7e47b6a2481cd",
}


def archived_website_workload_normalization() -> dict:
    """Original SHA-attested workload facts, not a price estimate or cost ratio."""
    try:
        path = _WORKLOAD_REPORT_PATH
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 40_000:
            raise ValueError("original workload report unavailable")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != _WORKLOAD_REPORT_SHA256:
            raise ValueError("source workload report hash mismatch")
        report = json.loads(raw)
        if (
            report.get("schema_version") != "ta-price01-verified-workload-no-financial-coefficients-v1"
            or report.get("baseline_aksay_contracts_count") != 1
            or report.get("new_equivalent_website_contracts") != 0
            or report.get("other_related_site_contracts_requiring_cost_normalization") != 2
            or report.get("labor_hours_comparable") is not False
            or report.get("company_costs_user_supplied") is not False
            or any(report.get(field) is not None for field in (
                "scope_normalization_adjustment_rub",
                "cross_tender_market_price_rub",
                "bid_recommendation_rub",
                "monetary_multiplier_per_working_day",
            ))
        ):
            raise ValueError("invalid price normalization or commercial input")
        cases = report["cases"]
        if not isinstance(cases, list) or len(cases) != 3:
            raise ValueError("invalid number of original reviewed TЗ")
        projected = []
        for case in cases:
            number = case["registry_number"]
            expected = _WORKLOAD_CASES.get(number)
            if (
                not expected
                or case.get("case_key") != expected[0]
                or case.get("original_technical_scope_docx_sha256")
                != _WORKLOAD_ORIGINAL_DOCX_SHA256[number]
                or case.get("money_or_labor_conversion_estimated") is not False
                or len(case.get("verified_dimensions", [])) != expected[2]
            ):
                raise ValueError("unrecognized original workload source")
            metrics = case["verified_dimensions"]
            if len({d.get("dimension") for d in metrics}) != expected[2]:
                raise ValueError("duplicate source dimension")
            duration = [d for d in metrics if d.get("dimension") == "delivery_working_days"]
            if len(duration) != 1 or duration[0].get("source_value") != expected[1]:
                raise ValueError("unexpected attested original contractual deadline")
            unknown = case["unknown_inputs"]
            if (
                any(unknown.get(f) is not None for f in (
                    "actual_labor_hours", "actual_labor_cost_rub", "cms_license_cost_rub",
                    "hosting_and_domain_cost_rub", "optional_integrations_cost_rub",
                    "actual_support_reserve_cost_rub", "actual_initial_content_pages",
                    "num_custom_site_page_templates",
                ))
                or unknown.get("initial_content_pages_cap")
                != (40 if number == "0377100005726000128" else None)
            ):
                raise ValueError("unverified costing information in public history")
            for metric in metrics:
                if (
                    metric.get("source_state") != "ATTESTED_FROM_EXACT_DOCX"
                    or not metric.get("source_quote")
                    or not metric.get("reviewed_interpretation")
                    or len(metric.get("source_line_sha256", "")) != 64
                    or not isinstance(metric.get("source_line_ordinal"), int)
                    or metric["source_line_ordinal"] < 0
                    or not isinstance(metric.get("unit"), str)
                    or not isinstance(metric.get("constraint_kind"), str)
                    or not isinstance(metric.get("source_value"), (int, str))
                ):
                    raise ValueError("unverifiable quoted requirement")
            projected.append({
                "registry_number": number,
                "case_key": case["case_key"],
                "original_technical_scope_docx_sha256": case["original_technical_scope_docx_sha256"],
                "verified_dimensions": [
                    {k: d[k] for k in (
                        "dimension", "source_value", "unit", "constraint_kind",
                        "reviewed_interpretation", "source_quote",
                        "source_line_ordinal", "source_line_sha256",
                    )} for d in metrics
                ],
                "costs_or_labor_hours_known": False,
                "initial_content_pages_cap": unknown["initial_content_pages_cap"],
                "actual_content_pages_known": False,
            })
        if {case["registry_number"] for case in projected} != set(_WORKLOAD_CASES):
            raise ValueError("missing or duplicate original website requirements")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Исходная матрица технических заданий недоступна или не проверена",
        ) from exc
    return {
        "state": "ATTESTED_CONTRACT_WORKLOAD_NOT_PRICE_NORMALIZATION",
        "receipt_sha256": _WORKLOAD_REPORT_SHA256,
        "source_cases_count": 3,
        "comparable_basket_procurements_count": 1,
        "additional_equivalent_projects": 0,
        "work_unit_rate_rub": None,
        "cross_tender_normalized_price_rub": None,
        "estimated_company_labor_hours": None,
        "bid_recommendation": False,
        "owner_approved": False,
        "cases": projected,
    }
