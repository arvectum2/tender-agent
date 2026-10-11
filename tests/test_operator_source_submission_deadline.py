"""Demo tender submission deadlines must be sourced, never replaced with run time."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from src.modules.tender_operator_agent_demo.operator_submission_deadline import (
    parse_submission_deadline,
    submission_deadline_from_metadata,
)
from src.modules.tender_operator_agent_demo.schemas import DemoTenderCard
from src.modules.tender_operator_agent_demo.service import (
    render_tender_operator_demo_html,
)


def test_missing_metadata_never_fabricates_current_deadline():
    assert submission_deadline_from_metadata({}) is None
    assert submission_deadline_from_metadata({"deadline": "", "procurement": {}}) is None
    assert submission_deadline_from_metadata({"procurement": {"deadline": None}}) is None


@pytest.mark.parametrize(
    ("value", "expected_hour", "offset_hours"),
    [
        ("2026-10-11T20:00:00+03:00", 20, 3),
        ("2026-10-11T17:00:00Z", 17, 0),
        ("15.07.2026 12:00:00 +10:00", 12, 10),
        ("01.07.2026 10:00", 10, None),
    ],
)
def test_explicit_structured_date_formats_are_parsed(value, expected_hour, offset_hours):
    parsed = parse_submission_deadline(value)
    assert parsed is not None
    assert parsed.hour == expected_hour
    if offset_hours is not None:
        assert parsed.utcoffset() == timedelta(hours=offset_hours)
    else:
        assert parsed.utcoffset() is None


@pytest.mark.parametrize("value", [None, "", "2026-10-11", "без срока", "15.09.2026", "32.07.2026 12:00"])
def test_partial_ambiguous_or_invalid_dates_are_unknown(value):
    assert parse_submission_deadline(value) is None


def test_enriched_notice_deadline_has_priority_over_card_fallback():
    result = submission_deadline_from_metadata(
        {
            "deadline": "2026-10-11T20:00:00+03:00",
            "procurement": {"deadline": "2026-10-12T08:00:00+03:00"},
        }
    )
    assert result is not None
    assert result.day == 11


def test_structured_card_deadline_is_accepted_when_no_notice_override():
    assert submission_deadline_from_metadata(
        {"procurement": {"deadline": "15.07.2026 12:00:00 +10:00"}}
    ) == datetime(2026, 7, 15, 12, 0, tzinfo=timezone(timedelta(hours=10)))


def test_card_schema_accepts_none_and_explicit_valid_datetime():
    common = {
        "run_id": "RUN-TEST",
        "prepared_at": datetime(2026, 10, 11, 5, 0),
        "title": "Тест",
        "procedure_type": "demo",
        "customer": "Заказчик",
        "category": "Услуги",
        "procurement_code": "DEMO-1",
        "analysis_status": "needs_review",
        "document_count": 0,
        "requirement_count": 0,
        "question_count": 0,
        "final_recommendation": "manual_review_required",
        "final_recommendation_label": "Требует проверки",
        "documents": [],
    }
    model = DemoTenderCard.model_validate({**common, "submission_deadline": None})
    assert model.submission_deadline is None


def test_demo_card_ui_displays_unknown_instead_of_epoch_date():
    html = render_tender_operator_demo_html()
    assert "tender.submission_deadline" in html
    assert "Не указано" in html


def test_created_uploaded_run_has_no_made_up_deadline(client, tmp_path, monkeypatch):
    monkeypatch.setenv("AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR", str(tmp_path / "deadline_runs"))
    created = client.post(
        "/api/demo/tender-agent/runs",
        data={
            "tender_title": "Демо без срока подачи",
            "tender_category": "Услуги",
            "customer_name": "Заказчик",
        },
        files=[("files", ("notice.txt", b"Notice without application deadline.", "text/plain"))],
    )
    assert created.status_code == 200
    run_id = created.json()["run_id"]
    analyzed = client.post(f"/api/demo/tender-agent/runs/{run_id}/analyze")
    assert analyzed.status_code == 200
    tender = json.loads((tmp_path / "deadline_runs" / run_id / "output" / "tender_summary.json").read_text())
    assert tender["submission_deadline"] is None
    assert tender["prepared_at"]
