"""Pure offline source-bound costing regressions; not a bid."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.ops.b2b_prebid_cost_scenarios import CostValidationError, calculate

DATA = Path(__file__).resolve().parents[2] / "docs/roadmap"


def cases():
    return [
        json.loads((DATA / name).read_text())
        for name in (
            "b2b_prebid_cost_assumptions_2026-10-18.json",
            "b2b_oct18_three_new_eis_originals.json",
            "b2b_oct18_three_official_attachments.json",
            "b2b_oct18_b2bcenter_4643484_firstparty.json",
        )
    ]


def test_source_receipt_and_scenarios_preserve_boundary():
    items = cases()
    original = copy.deepcopy(items)
    result = calculate(*items)
    assert items == original
    assert result["contract_bid_authorized"] is False
    assert result["external_communications_count"] == 0
    assert result["source_archived_legal_currentness_confirmed"] is False
    sm, b2b = result["case_results"]
    assert sm["id"] == "0163200000326005243"
    assert sm["work_package_count"] == 12
    assert b2b["id"] == "4643484"
    assert b2b["work_package_count"] == 7
    for tier, hours in {"low": 252, "base": 592, "high": 1086}.items():
        assert sm["scenarios"][tier]["hours_total"] == hours
        assert float(sm["scenarios"][tier]["headroom_at_published_ceiling_after_assumed_tax_and_cost_rub"]) < 0
        assert b2b["scenarios"][tier]["published_budget_ceiling_rub"] is None
        assert b2b["scenarios"][tier]["headroom_at_published_ceiling_after_assumed_tax_and_cost_rub"] is None
    assert sm["scenarios"]["base"]["estimated_total_economic_cost_rub"] == "1516149.00"
    assert b2b["scenarios"]["base"]["estimated_total_economic_cost_rub"] == "704178.00"


@pytest.mark.parametrize("i,field,new", [
    (0, "source_zip_sha256", "a" * 64),
    (0, "source_tz_docx_sha256", "a" * 64),
    (0, "source_evaluation_docx_sha256", "a" * 64),
    (0, "source_contract_docx_sha256", "a" * 64),
    (0, "source_application_docx_sha256", "a" * 64),
    (0, "public_budget_ceiling_rub", "0.00"),
    (0, "source_contract_deadline", "2026-12-31"),
    (0, "source_warranty_months", 0),
    (0, "source_price_weight_percent", 70),
    (0, "owner_bid_ready", True),
    (1, "source_detail_html_sha256", "a" * 64),
    (1, "source_index_html_sha256", "a" * 64),
    (1, "public_budget_ceiling_rub", "500000"),
    (1, "original_public_deadline", "2026-11-01T06:00:00+03:00"),
    (1, "owner_bid_ready", True),
])
def test_unsubstantiated_original_claim_rejected(i, field, new):
    data = cases()
    data[0]["cases"][i][field] = new
    with pytest.raises(CostValidationError):
        calculate(*data)


@pytest.mark.parametrize("value", [-1, 1, 5000, "12", True])
def test_invalid_or_non_monotone_scenario_hours_rejected(value):
    data = cases()
    data[0]["cases"][0]["tasks"][0]["hours"]["base"] = value
    with pytest.raises(CostValidationError):
        calculate(*data)


@pytest.mark.parametrize("rate", ["0", "-100", "NaN", "Infinity", "bad", 1750])
def test_nonexplicit_or_unsafe_economic_rate_rejected(rate):
    data = cases()
    data[0]["roles"]["bitrix_engineer"]["scenario_rate_rub_per_hour"] = rate
    with pytest.raises(CostValidationError):
        calculate(*data)


def test_duplicate_work_package_and_unknown_scope_rejected():
    data = cases()
    data[0]["cases"][0]["tasks"][0]["id"] = data[0]["cases"][0]["tasks"][1]["id"]
    with pytest.raises(CostValidationError):
        calculate(*data)
    data = cases()
    data[0]["cases"][1]["tasks"][0]["source_scope"] = "source_tz"
    with pytest.raises(CostValidationError):
        calculate(*data)


def test_edited_eis_attachment_digest_rejected():
    data = cases()
    data[2]["entries"][0]["files"][2]["binary_sha256"] = "0" * 64
    with pytest.raises(CostValidationError):
        calculate(*data)


@pytest.mark.parametrize("fraction", ["1", "NaN", "0.80", 0.06])
def test_unvalidated_tax_scenario_rejected(fraction):
    data = cases()
    data[0]["assumptions_not_from_buyer"]["tax_fraction_of_collected_revenue"] = fraction
    with pytest.raises(CostValidationError):
        calculate(*data)


def test_report_is_exact_reproducible_projection():
    src = DATA / "b2b_prebid_cost_assumptions_2026-10-18.json"
    saved = json.loads((DATA / "b2b_prebid_cost_result_2026-10-18.json").read_text())
    assert saved.pop("source_assumption_input_sha256") == hashlib.sha256(src.read_bytes()).hexdigest()
    assert saved == calculate(*cases())
