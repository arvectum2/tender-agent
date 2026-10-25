"""Conservative 4-case public original Workspace opportunity qualification."""
import json
import re
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "docs/roadmap"
R = json.loads((ROOT / "b2b_workspace_four_original_fit_2026-10-17.json").read_text())
CASES = {c["id"]: c for c in R["cases"]}


def test_four_original_verified_public_cards_are_not_bid_authorizations():
    assert R["schema_version"] == "arvectum-workspace-four-first-party-fit-20261017-v1"
    assert R["distinct_cards"] == 4 == R["platform_public_open_snapshot_count"]
    assert R["current_paid_access_confirmed"] == 0
    assert R["company_eligibility_confirmed"] == 0
    assert R["owner_bid_go_count"] == 0
    assert R["source_status_snapshot_not_contract_availability"] is True
    assert set(CASES) == {"19030", "19032", "19042", "19043"}
    for case in R["cases"]:
        assert case["original_http_status"] == 200
        assert case["original_public_status"] == "Идет прием заявок"
        assert case["original_public_organizer_type"] == "Юридическое лицо"
        assert case["original_public_deadline_clock"] == "UNKNOWN"
        assert case["original_html_size"] > 50_000
        assert re.fullmatch("[a-f0-9]{64}", case["original_html_sha256"])
        assert case["source_url"].startswith("https://workspace.ru/tenders/")
        assert case["source_url"].endswith(f"-{case['id']}/")
        assert datetime.fromisoformat(case["checked_at_utc"]).tzinfo is not None
        assert len(case["original_public_evidence_literals"]) >= 4
        assert case["customer_legal_identity_by_inn_verified"] is False
        assert case["company_portfolio_accepted"] is False
        assert case["workspace_pro_or_invitation_for_company_verified"] is False
        assert case["hidden_spec_attachments_inspected"] is False
        assert case["submission_authorized"] is False
        assert case["owner_bid_go"] is False
        assert case["no_external_actions"] is True


@pytest.mark.parametrize("id,deadline,gate,evidence", [
    ("19030", "2026-11-13", "CONDITIONAL_AI_PILOT_SPEC_ATTACHMENT_GATED",
     "Подробное ТЗ во вложении."),
    ("19032", "2026-10-21", "CONDITIONAL_WORDPRESS_MONTHLY_SLA_AND_PORTFOLIO",
     "срок реакции на сбои"),
    ("19042", "2026-10-31", "THREE_YEAR_COMMERCIAL_EXPERIENCE_GATE",
     "Коммерческий опыт разработки от 3 лет."),
    ("19043", "2026-10-31", "MANDATORY_RELEVANT_PORTFOLIO_AND_DISCOVERY_GATE",
     "Наличие релевантных реализованных проектов обязательно."),
])
def test_original_source_business_gates_exactly_bound(id, deadline, gate, evidence):
    case = CASES[id]
    assert case["original_public_deadline_date"] == deadline
    assert case["conservative_qualification_gate"] == gate
    assert evidence in case["original_public_evidence_literals"]


def test_report_retains_careful_limits_and_no_false_qualification():
    report = (ROOT / "B2B_WORKSPACE_FOUR_SOURCE_FIT_2026-10-17.md").read_text()
    assert "PUBLIC_CANDIDATE_ONLY" in report
    assert "не BID_READY" in report
    assert "0/4" in report
    assert "WordPress" in report
    assert "13.11.2026" in report
    assert "21.10.2026" in report
    assert "3 лет" in report
    assert "Наличие релевантных реализованных проектов обязательно" in report
    assert "Подробное ТЗ во вложении" in report
    assert "без согласованных ресурсов" in report
