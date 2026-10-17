"""First-party 44-FZ application guarantee is liquidity not an expense or GO."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.acceptance.audit_priority_eis_bid_security_original import (
    _SOURCES,
    original_application_security,
)
from scripts.acceptance.museum_multimedia_three_complex_budget import build

ROOT = Path(__file__).resolve().parents[1] / "docs/roadmap"
SOURCE = json.loads((ROOT / "b2b_44fz_two_original_bid_securities_2026-10-17.json").read_text())
ORIGINAL_ATTACHMENTS = json.loads((ROOT / "b2b_priority_eis_documents_2026-10-17.json").read_text())
FINANCE = json.loads((ROOT / "b2b_museum_three_exhibits_cost_sensitivity_2026-10-17.json").read_text())


def original_xml(*, tag: str = "epNotificationEF2020",
                 number: str = "0161600001326000063",
                 amount: str = "16000.00", percent: str = "1.0",
                 extra_requirement: str = "") -> bytes:
    return f'''<export>
       <{tag}>
          <commonInfo><purchaseNumber>{number}</purchaseNumber></commonInfo>
          <notificationInfo><customerRequirementsInfo>
          <customerRequirementInfo><applicationGuarantee>
          <amount>{amount}</amount><part>{percent}</part>
          </applicationGuarantee></customerRequirementInfo>
          {extra_requirement}
          </customerRequirementsInfo></notificationInfo>
       </{tag}></export>'''.encode()


def test_44fz_bid_security_first_party_receipt_matches_pinned_zip_xml():
    assert SOURCE["schema_version"] == "b2b-original-44fz-two-application-guarantees-v1"
    assert SOURCE["reviewed_original_procurements"] == 2
    assert SOURCE["all_official_sources_historical_archive_only"] is True
    assert SOURCE["no_etp_action_or_payment"] is True
    assert SOURCE["company_bid_ready"] is False
    items = SOURCE["public_44fz_application_securities"]
    assert len(items) == 2
    assert {x["source_reg_number"] for x in items} == set(_SOURCES)
    prev = {x["procurement_number"]: x for x in ORIGINAL_ATTACHMENTS["procedures"]}
    for item in items:
        n = item["source_reg_number"]
        src = prev[n]
        expected = _SOURCES[n]
        assert item["source_kind"] == "ORIGINAL_EIS_GETDOCSIP_ARCHIVED_XML"
        assert item["source_archived_revision"] == 1
        assert item["source_archive_sha256"] == src["zip_sha256"] == expected["archive_sha256"]
        assert item["source_original_notice_sha256"] == src["notice_xml_sha256"] == expected["xml_sha256"]
        assert item["source_xml_exact_path"].endswith("applicationGuarantee/{amount,part}")
        assert item["application_security_part_percent"] == "1.00"
        assert Decimal(item["application_security_amount_rub"]) == Decimal(
            item["source_original_nmck_rub"]
        ) * Decimal("0.01")
        assert item["current_legal_bidding_status_verified"] is False
        assert item["eligible_to_bid"] is False
        assert item["cash_security_is_not_economic_expense"] is True
        assert item["guarantee_or_cash_method_is_owner_decision"] is True
    a = {x["source_reg_number"]: x for x in items}
    assert a["0161600001326000063"]["application_security_amount_rub"] == "16000.00"
    assert a["0816500000626015655"]["application_security_amount_rub"] == "45500.00"


def test_original_amount_parser_exact_source_path_and_no_go_assumptions():
    p = original_application_security(original_xml(),
                                      number="0161600001326000063",
                                      notice_type="epNotificationEF2020")
    assert p["application_security_amount_rub"] == "16000.00"
    assert p["application_security_part_percent"] == "1.00"


@pytest.mark.parametrize("change", [
    {"number": "1111111111111111111"},
    {"tag": "epNotificationEZK2020"},
    {"amount": "-16000"},
    {"amount": "NaN"},
    {"amount": "0"},
    {"amount": "infinite"},
    {"percent": "0"},
    {"extra_requirement": "<customerRequirementInfo/>"},
])
def test_source_ambiguity_or_invalid_security_rejected(change):
    data = original_xml(**change)
    with pytest.raises(ValueError):
        original_application_security(
            data, number="0161600001326000063",
            notice_type="epNotificationEF2020",
        )


def test_security_is_separate_liquidity_phase_and_never_double_expensed():
    assert build() == FINANCE
    museum = next(x for x in SOURCE["public_44fz_application_securities"]
                  if x["source_reg_number"] == "0161600001326000063")
    assert FINANCE["source_official_original_application_security_rub"] == museum[
        "application_security_amount_rub"
    ]
    assert FINANCE["application_security_is_not_expense_and_may_have_independent_guarantee_option"]
    assert FINANCE["bid_authorization"] is False
    for scenario in FINANCE["scenarios"]:
        for row in scenario["price_variants"]:
            assert row["source_application_security_bid_phase_rub"] == "16000.00"
            assert row["different_security_phases_not_summed_as_cost_or_required_concurrent_cash"]
            price = Decimal(row["assumed_bid_price_rub"])
            expected = (
                price - Decimal(row["cash_external_illustrative_rub"])
                - Decimal(row["shadow_own_labor_economic_cost_rub"])
                - Decimal(row["usn_six_percent_gross_planning_tax_rub"])
            )
            assert Decimal(row["economic_profit_after_shadow_labor_and_usn_rub"]) == expected
            assert Decimal(row["approx_upfront_cash_plus_security_upper_bound_rub"]) == (
                Decimal(row["cash_external_illustrative_rub"])
                + Decimal(row["liquidity_performance_security_5pct_rub"])
            )
            assert not row["owner_commercial_go"] and not row["eligible_to_submit"]


def test_not_confuse_yakutia_warranty_security_with_museum_bid_bond():
    summary = (ROOT / "B2B_MUSEUM_3_COMPLEXES_ECONOMICS_2026-10-17.md").read_text()
    assert "16 000 ₽" in summary and "45 500 ₽" in summary
    assert "не суммируется автоматически" in summary
    assert "разные стадии" not in summary or "другая стадия" in summary
    assert "227 500" not in summary
    assert "не GO" in summary
