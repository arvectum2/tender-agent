"""Reproducible source-bound TЗ clauses and no invented monetary normalizer."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest
from docx import Document

from scripts.price01.normalize_website_workload import (
    _CASES,
    _RULES,
    attest_rule,
    audit_workload_case,
    extract_source_lines,
)

REPORT = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "docs/roadmap/price01_workload_normalization_2026-10-18.json"
    ).read_text(encoding="utf-8")
)


def _docx_bytes(lines: list[str]) -> bytes:
    document = Document()
    for text in lines:
        document.add_paragraph(text)
    data = io.BytesIO()
    document.save(data)
    return data.getvalue()


def test_workload_source_literal_attestations_without_fabricated_costs():
    assert REPORT["schema_version"] == "ta-price01-verified-workload-no-financial-coefficients-v1"
    assert REPORT["baseline_aksay_contracts_count"] == 1
    assert REPORT["new_equivalent_website_contracts"] == 0
    assert REPORT["other_related_site_contracts_requiring_cost_normalization"] == 2
    assert REPORT["labor_hours_comparable"] is False
    assert REPORT["company_costs_user_supplied"] is False
    for field in (
        "scope_normalization_adjustment_rub",
        "cross_tender_market_price_rub",
        "bid_recommendation_rub",
        "monetary_multiplier_per_working_day",
    ):
        assert REPORT[field] is None
    assert len(REPORT["cases"]) == 3
    assert {r["registry_number"] for r in REPORT["cases"]} == set(_CASES)
    for case in REPORT["cases"]:
        assert len(case["original_technical_scope_docx_sha256"]) == 64
        assert case["money_or_labor_conversion_estimated"] is False
        assert case["unknown_inputs"]["actual_labor_hours"] is None
        assert case["unknown_inputs"]["actual_labor_cost_rub"] is None
        assert case["unknown_inputs"]["cms_license_cost_rub"] is None
        assert case["unknown_inputs"]["hosting_and_domain_cost_rub"] is None
        assert case["unknown_inputs"]["num_custom_site_page_templates"] is None
        assert len(case["verified_dimensions"]) == len(_RULES[case["registry_number"]])
        for dimension in case["verified_dimensions"]:
            assert dimension["source_state"] == "ATTESTED_FROM_EXACT_DOCX"
            assert len(dimension["source_line_sha256"]) == 64
            assert dimension["source_quote"]
            assert dimension["reviewed_interpretation"]
            assert dimension["source_line_ordinal"] >= 0


def test_workload_page_unknowns_and_explicit_40_page_cap_not_zero_pages():
    by = {case["case_key"]: case for case in REPORT["cases"]}
    def value(key: str, dimension: str):
        return next(
            (r["source_value"] for r in by[key]["verified_dimensions"] if r["dimension"] == dimension),
            None,
        )
    assert [value(c, "delivery_working_days") for c in ("AKSAY", "KRASNOYARSK", "CHEMAL")] == [
        14, 10, 21,
    ]
    assert value("AKSAY", "initial_content_pages_max") is None
    assert value("KRASNOYARSK", "initial_content_pages_max") is None
    assert value("CHEMAL", "initial_content_pages_max") == 40
    assert by["CHEMAL"]["unknown_inputs"]["initial_content_pages_cap"] == 40
    assert by["CHEMAL"]["unknown_inputs"]["actual_initial_content_pages"] is None
    assert by["AKSAY"]["unknown_inputs"]["initial_content_pages_cap"] is None
    assert by["KRASNOYARSK"]["unknown_inputs"]["initial_content_pages_cap"] is None
    assert by["AKSAY"]["unknown_inputs"]["content_pages_scope"] == "NOT_QUANTIFIED_IN_REVIEWED_TZ"
    assert value("AKSAY", "postacceptance_obligation") == "ROUTINE_SUPPORT_EXCLUDED"
    assert value("KRASNOYARSK", "postacceptance_obligation") == "ONGOING_SUPPORT_12_MONTHS_WITH_SLA"
    assert value("CHEMAL", "postacceptance_obligation") == "DEFECT_WARRANTY_12_MONTHS"
    assert value("AKSAY", "cms_platform") == "RUSSIAN_REGISTRY_CMS_CONTRACTOR_CHOICE"
    assert value("KRASNOYARSK", "cms_platform") == "RUSSIAN_CMS_PRODUCT_NOT_PINNED"
    assert value("CHEMAL", "cms_platform") == "BITRIX_STANDARD_1_YEAR_PAID_BY_CONTRACTOR"


def test_exact_quote_audit_rejects_missing_duplicate_or_changed_clauses():
    rule = _RULES["0158300034526000388"][0]
    evidence = attest_rule([rule.source_phrase, "Other line"], rule)
    assert evidence["source_value"] == 14
    assert evidence["source_line_ordinal"] == 0
    assert evidence["source_line_sha256"] == hashlib.sha256(
        rule.source_phrase.encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="missing or ambiguous"):
        attest_rule(["Work for 7 days"], rule)
    with pytest.raises(ValueError, match="missing or ambiguous"):
        attest_rule([rule.source_phrase, rule.source_phrase], rule)


def test_synthetic_docx_source_sha_and_clause_integrity_enforced():
    num = "0158300034526000388"
    rules = _RULES[num]
    lines = [r.source_phrase for r in rules] + ["unused line", "extra line", "extra"]
    data = _docx_bytes(lines)
    sha = hashlib.sha256(data).hexdigest()
    result = audit_workload_case(num, data, expected_sha=sha)
    assert result["registry_number"] == num
    assert len(result["verified_dimensions"]) == len(rules)
    assert result["unknown_inputs"]["actual_labor_cost_rub"] is None
    with pytest.raises(ValueError, match="DOCX SHA"):
        audit_workload_case(num, data + b"bad", expected_sha=sha)
    changed = _docx_bytes([r.source_phrase for r in rules[:-1]] + ["wrong", "extra", "tail"])
    with pytest.raises(ValueError, match="changed, missing or ambiguous"):
        audit_workload_case(num, changed, expected_sha=hashlib.sha256(changed).hexdigest())


def test_synthetic_source_word_requirements_boundary_rejections():
    with pytest.raises(ValueError, match="bounded"):
        extract_source_lines(b"NO DOCX")
    with pytest.raises(ValueError, match="unknown procurement"):
        audit_workload_case("0000000000000000000", b"opaque")


def test_no_proprietary_source_docx_files_committed_in_report():
    serialized = json.dumps(REPORT, ensure_ascii=False)
    assert "file:///Volumes/" not in serialized
    assert "/Volumes/ArvectumSSD" not in serialized
    assert '"bid_recommendation_rub": 28400' not in serialized
    assert "application_id" not in serialized
    assert "appNumber" not in serialized
