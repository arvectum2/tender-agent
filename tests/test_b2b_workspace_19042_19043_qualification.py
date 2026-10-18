"""Original-card obligations and qualification cannot auto-promote corporate bid."""
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.acceptance.audit_workspace_19042_19043_qualification import (
    ORIGINALS,
    evaluate_original,
    source_url,
)

ROOT = Path(__file__).resolve().parents[1] / "docs" / "roadmap"
REPORT = json.loads((ROOT / "b2b_workspace_19042_19043_qualification_2026-10-17.json").read_text())
WHEN = datetime(2026, 10, 17, 19, 29, tzinfo=UTC)


def fake_original(case_id, *, missing="", status="Идет прием заявок",
                  deadline="31 октября 2026", budget=None):
    spec = ORIGINALS[case_id]
    clauses = " ".join(
        x for group in ("hard_qualification", "preferred_qualification", "source_scope",
                        "requested_quote", "optional_requested", "other")
        for x in spec.get(group, ())
    )
    if missing:
        clauses = clauses.replace(missing, "")
    if budget:
        source_budget = f"{spec['budget'][0] // 1000} 000 - {spec['budget'][1] // 1000} 000 рублей"
        clauses = clauses.replace(source_budget, budget)
    return (
        "<html><h1>Разработка корпоративной системы</h1>"
        f'<div class="tendercart-type__status-public">{status}</div>'
        '<div class="reference _public"></div>'
        "Oрганизатор <span>Юридическое лицо</span>"
        f'Крайний срок приема заявок: <span>{deadline}</span>'
        f"<article>{clauses}</article></html>"
    ).encode()


def test_exact_only_two_predefined_original_sources():
    assert set(ORIGINALS) == {"19042", "19043"}
    for key in ORIGINALS:
        assert source_url(key).startswith("https://workspace.ru/tenders/")
        assert source_url(key).endswith(f"-{key}/")
    with pytest.raises(KeyError):
        source_url("99999")
    with pytest.raises(ValueError, match="unexpected"):
        evaluate_original("99999", b"", observed_at=WHEN)


@pytest.mark.parametrize("case_id", ["19042", "19043"])
def test_minimum_qualifications_are_not_inferred_from_source_presence(case_id):
    result = evaluate_original(case_id, fake_original(case_id), observed_at=WHEN)
    assert result["company_eligibility_state"] == "LLC_REVIEW_REQUIRED"
    assert result["company_mandatory_experience_proven"] is False
    assert result["company_accepted_realized_portfolio_proven"] is False
    assert result["company_account_pro_access_verified"] is False
    assert result["buyer_accepts_employee_or_partner_references"] == "UNKNOWN"
    assert result["source_deadline_hour"] == "UNKNOWN"
    assert result["budget_is_contractually_fixed"] is False
    assert result["owner_approved_price_rub"] is None
    assert (result["bid_ready"], result["owner_go"], result["external_messages_or_paid_actions"]) == (False, False, 0)


def test_19042_is_hard_three_years_and_completed_portfolio_not_erp_mandatory():
    result = evaluate_original("19042", fake_original("19042"), observed_at=WHEN)
    assert result["required_commercial_experience_years"] == 3
    assert "Коммерческий опыт разработки от 3 лет." in result["source_clause_groups"]["hard_qualification"]
    assert "Наличие портфолио завершённых проектов." in result["source_clause_groups"]["hard_qualification"]
    assert any("Желателен опыт" in q for q in result["source_clause_groups"]["preferred_qualification"])


def test_19043_two_option_phrase_is_optional_and_website_not_attested():
    result = evaluate_original("19043", fake_original("19043"), observed_at=WHEN)
    assert result["required_commercial_experience_years"] is None
    assert result["hard_qualification_clauses"] == 1
    assert result["requested_two_site_options_is_mandatory"] is False
    assert result["customer_existing_site_url_verified"] is False
    assert result["source_clause_groups"]["optional_requested"] == [
        "Если возможно, просим предложить 2 варианта реализации",
    ]


@pytest.mark.parametrize(("case_id", "group"), [
    ("19042", "hard_qualification"),
    ("19042", "preferred_qualification"),
    ("19042", "source_scope"),
    ("19042", "requested_quote"),
    ("19043", "hard_qualification"),
    ("19043", "preferred_qualification"),
    ("19043", "source_scope"),
    ("19043", "requested_quote"),
    ("19043", "optional_requested"),
])
def test_missing_required_original_semantics_fail_closed(case_id, group):
    missing = ORIGINALS[case_id][group][0]
    with pytest.raises(ValueError, match=group):
        evaluate_original(case_id, fake_original(case_id, missing=missing), observed_at=WHEN)


@pytest.mark.parametrize("case_id", ["19042", "19043"])
def test_material_budget_and_public_status_changes_fail_closed(case_id):
    with pytest.raises(ValueError, match="other"):
        evaluate_original(case_id, fake_original(case_id, budget="25 000 рублей"), observed_at=WHEN)
    with pytest.raises(ValueError):
        evaluate_original(case_id, fake_original(case_id, status="Завершён"), observed_at=WHEN)
    with pytest.raises(ValueError):
        evaluate_original(case_id, fake_original(case_id, deadline="30 октября 2026"), observed_at=WHEN)


def test_naive_timestamp_fails_closed():
    with pytest.raises(ValueError, match="timezone"):
        evaluate_original("19042", fake_original("19042"), observed_at=WHEN.replace(tzinfo=None))


def test_real_dated_source_receipt_has_no_unsupported_llc_go():
    assert REPORT["schema_version"] == "workspace-19042-19043-first-party-qualification-v1"
    assert REPORT["original_verified_cards"] == 2
    assert REPORT["company_realized_portfolio_accepted_count"] == 0
    assert REPORT["bid_ready_count"] == 0
    assert REPORT["paid_actions_or_messages_sent"] == 0
    assert {c["id"] for c in REPORT["cases"]} == {"19042", "19043"}
    for case in REPORT["cases"]:
        assert case["original_http_status"] == 200
        assert case["original_html_bytes"] > 50_000
        assert len(case["original_html_sha256"]) == 64
        assert case["source_deadline_date"] == "2026-10-31"
        assert case["source_receiving_status"] == "Идет прием заявок"
        assert case["source_organizer_type"] == "Юридическое лицо"
        assert case["company_eligibility_state"] == "LLC_REVIEW_REQUIRED"
        assert case["company_mandatory_experience_proven"] is False
        assert case["company_accepted_realized_portfolio_proven"] is False
        assert case["bid_ready"] is False and case["owner_go"] is False
        assert datetime.fromisoformat(case["observed_at_utc"]).tzinfo is not None
