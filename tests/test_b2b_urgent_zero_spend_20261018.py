"""Six original demand descriptions never imply company payment or bidding rights."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.acceptance.audit_b2b_urgent_zero_spend_20261018 import (
    CASES,
    PRICING_URL,
    _source_get,
    audit_case,
    summarize,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = json.loads(
    (ROOT / "docs/roadmap/b2b_urgent_free_first_originals_2026-10-18.json")
    .read_text("utf-8")
)
NOW = datetime(2026, 10, 18, 9, 20, tzinfo=UTC)


def _synthetic(code: str, *, without: str | None = None) -> bytes:
    case = CASES[code]
    base = " ".join(case["anchors"])
    if without:
        base = base.replace(without, "[changed source]")
    if code == "CL147":
        base = "Открыт Создано 10 дней назад " + base
    if case["source"] == "CONTRACTIS":
        base = "Биржа заказов " + base + " Дата публикации: месяц назад"
    return ("<html><body>" + base + " original source " * 120 + "</body></html>").encode()


def test_exact_original_allowlist_has_three_corporate_and_three_marketplace_cards():
    assert len(CASES) == 6
    assert len({x["url"] for x in CASES.values()}) == 6
    assert set(CASES) == {"19012", "19032", "19034", "C6", "C12", "CL147"}
    assert sum(x["source"] == "WORKSPACE" for x in CASES.values()) == 3
    assert all(s["url"].startswith("https://") for s in CASES.values())
    assert PRICING_URL == "https://workspace.ru/advertising/"


@pytest.mark.parametrize("id_", ("C6", "C12", "CL147"))
def test_free_first_tasks_have_source_evidence_but_not_company_eligibility(id_):
    row = audit_case(id_, _synthetic(id_), NOW)
    assert row["company_buyer_inn_verified"] is False
    assert row["llc_arvectum_corporate_account_verified"] is False
    assert row["llc_pro_or_free_reply_rights_verified"] is False
    assert row["company_contract_ready"] is False
    assert row["company_submitted_or_paid"] is False
    assert row["owner_go"] is False
    assert row["due_clock_msk_public"] == "UNKNOWN"
    assert row["public_company_organizer_type"] == "UNKNOWN"
    assert len(row["original_html_sha256"]) == 64
    if id_ == "CL147":
        assert row["source_public_state"] == "OPEN_CARD_NOT_AUTHENTICATED_REPLY"
    else:
        assert row["source_public_state"] == (
            "SOURCE_TASK_DESCRIPTION_WITHOUT_VERIFIED_LIVE_STATUS"
        )


@pytest.mark.parametrize("id_", ("C6", "C12", "CL147"))
def test_changed_original_description_rejected(id_):
    case = CASES[id_]
    first = case["anchors"][-1]
    with pytest.raises(ValueError, match="evidence missing or changed"):
        audit_case(id_, _synthetic(id_, without=first), NOW)


def test_unknown_source_and_wrong_status_cannot_enter_verified_lead_report():
    with pytest.raises(ValueError):
        audit_case("INVALID", _synthetic("C12"), NOW)
    with pytest.raises(ValueError, match="evidence missing or changed"):
        audit_case(
            "CL147", _synthetic("CL147").replace("Открыт".encode(), "Закрыт".encode()), NOW
        )


def test_partial_or_extra_sources_do_not_create_numerical_leads():
    with pytest.raises(ValueError, match="incomplete"):
        summarize({"C6": _synthetic("C6")}, checked=NOW)


def test_saved_source_originals_validate_public_and_private_distinction():
    report = REPORT
    assert report["schema_version"] == "ta-b2b-urgent-free-first-original-2026-10-18-v1"
    assert report["source_originals_checked"] == 7
    assert report["public_workspace_corporate_tenders"] == 3
    assert report["free_first_marketplace_task_descriptions"] == 3
    assert report["actual_arvectum_llc_bid_ready_count"] == 0
    assert report["actual_llc_pro_subscription_bought"] is False
    assert report["actual_llc_free_reply_used"] is False
    assert report["messages_payment_or_registration_executed"] == 0
    assert report["actual_workspace_llc_checkout_verified"] is False
    assert report["public_design_pro_rub_1mo_if_applicable"] == 6900
    assert report["public_webdev_pro_rub_1mo_if_applicable"] == 25500
    assert len(report["pro_policy_html_sha256"]) == 64
    assert [x["source_id"] for x in report["source_cases"]] == list(CASES)
    dates = {x["source_id"]: x["due_day_public"] for x in report["source_cases"]}
    assert dates["19012"] == "2026-10-19"
    assert dates["19032"] == "2026-10-21"
    assert dates["19034"] == "2026-10-31"
    assert dates["C6"] == "UNKNOWN_NOT_SHOWN_AS_EXACT_DAY"
    for row in report["source_cases"]:
        assert row["company_contract_ready"] is False
        assert row["llc_arvectum_corporate_account_verified"] is False
        assert row["llc_pro_or_free_reply_rights_verified"] is False
        assert row["company_buyer_inn_verified"] is False
        assert row["due_clock_msk_public"] == "UNKNOWN"
        assert row["owner_go"] is False
        assert row["company_submitted_or_paid"] is False
        assert len(row["original_html_sha256"]) == 64


def test_no_script_can_guess_any_url_outside_original_allowlist():
    import inspect
    source = inspect.getsource(_source_get)
    assert "if url not in targets" in source
    assert "response.geturl() != url" in source
    assert "ProxyHandler({})" in source
    assert "MAX_BYTES + 1" in source
