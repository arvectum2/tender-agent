"""Saved EIS snapshots are historical: never promote old decisions to live GO."""
from __future__ import annotations

import copy
from types import SimpleNamespace

from fastapi.responses import FileResponse, Response

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.operator_eis_archive_freshness import (
    EIS_ARCHIVE_REVIEW_MESSAGE,
    needs_live_eis_revision_review,
    projected_historical_eis_report,
    projected_historical_eis_run,
    review_annotated_html,
)


def _archived():
    return {
        "procurement_source": "zakupki_gov_ru_getdocs_ip",
        "procurement_id": "0162300005826000156",
        "status": "completed",
        "notice_revision_selected": None,  # historical APR-06 metadata
    }


def _report():
    return {
        "run_id": "historical-1",
        "report_title": "Исходный отчёт",
        "generated_at": "2026-10-09T10:00:00+03:00",
        "recommendation": "participate_conditionally",
        "recommendation_label": "участвовать условно",
        "executive_summary": ["Исторический результат"],
        "manual_checks": [],
        "sections": [],
        "report_markdown": "Сохранённый текст исходного отчёта",
        "decision_core": {"unknowns": [], "status": "GO"},
    }


def test_archived_eis_is_not_a_live_notice_attestation():
    data = _archived()
    assert needs_live_eis_revision_review(data)
    data["notice_revision_selected"] = {"version": 5, "current_live_eis_verified": False}
    assert needs_live_eis_revision_review(data)
    data["notice_revision_requires_review"] = True
    assert needs_live_eis_revision_review(data)
    data.pop("notice_revision_requires_review")
    data["notice_revision_selected"]["current_live_eis_verified"] = True
    assert not needs_live_eis_revision_review(data)
    assert not needs_live_eis_revision_review({"procurement_source": "manual_upload"})


def test_live_attestation_never_crosses_procurement_identity() -> None:
    data = _archived()
    data["notice_revision_selected"] = {
        "version": 5,
        "purchase_number": "0895100000126000897",
        "current_live_eis_verified": True,
    }
    assert needs_live_eis_revision_review(data)
    data["notice_revision_selected"]["purchase_number"] = data["procurement_id"]
    assert not needs_live_eis_revision_review(data)
    data["notice_revision_selected"]["purchase_number"] = 123
    assert needs_live_eis_revision_review(data)


def test_report_projection_masks_historical_go_without_rewriting_source():
    report = _report()
    original = copy.deepcopy(report)
    projected = projected_historical_eis_report(_archived(), report)
    assert projected["recommendation"] == "manual_review_required"
    assert projected["recommendation_label"] != original["recommendation_label"]
    assert EIS_ARCHIVE_REVIEW_MESSAGE in projected["manual_checks"]
    assert projected["report_markdown"].startswith(EIS_ARCHIVE_REVIEW_MESSAGE)
    assert projected["decision_core"]["current_eis_revision_status"] == "UNKNOWN"
    assert projected["decision_core"]["historical_decision_not_authoritative"] is True
    assert projected["decision_core"]["unknowns"][0]["code"] == "EIS_CURRENT_NOTICE_REVISION_UNVERIFIED"
    assert report == original  # source report is unchanged
    assert projected_historical_eis_report(_archived(), projected)["manual_checks"].count(
        EIS_ARCHIVE_REVIEW_MESSAGE
    ) == 1
    assert projected_historical_eis_report({"procurement_source": "manual_upload"}, report) is report


def test_html_annotation_preserves_original_and_is_idempotent():
    source = '<!doctype html><html><head><title>Report</title></head><body class="legacy"><p>participate</p></body></html>'
    flagged = review_annotated_html(_archived(), source)
    assert flagged.index('role="alert"') < flagged.index("<p>participate</p>")
    assert EIS_ARCHIVE_REVIEW_MESSAGE in flagged
    assert flagged.count('data-arvectum-eis-archive-review="required"') == 1
    assert review_annotated_html(_archived(), flagged) == flagged
    assert review_annotated_html({"procurement_source": "manual_upload"}, source) == source


def test_legacy_saved_api_projects_review_without_mutating_json(monkeypatch):
    data, source = _archived(), _report()
    before = copy.deepcopy(source)
    monkeypatch.setattr(legacy, "_load_metadata", lambda _rid: data)
    monkeypatch.setattr(legacy, "_load_report_json", lambda _rid: source)
    response = legacy.get_uploaded_demo_report("historical-1")
    assert response.recommendation.value == "manual_review_required"
    assert EIS_ARCHIVE_REVIEW_MESSAGE in response.manual_checks
    assert response.decision_core["historical_decision_not_authoritative"] is True
    assert source == before


def test_legacy_html_route_and_download_annotate_without_file_rewrite(monkeypatch, tmp_path):
    path = tmp_path / "report.html"
    source = "<html><body><p>old and unverified recommendation</p></body></html>"
    path.write_text(source)
    monkeypatch.setattr(legacy, "_report_html_path", lambda _rid: path)
    monkeypatch.setattr(legacy, "_ensure_procurement_blocked_report_html", lambda _rid: None)
    monkeypatch.setattr(legacy, "_load_metadata", lambda _rid: _archived())
    html_page = legacy.get_uploaded_demo_report_html("historical-1")
    assert EIS_ARCHIVE_REVIEW_MESSAGE in html_page
    response = legacy.get_uploaded_demo_report_download("historical-1")
    assert isinstance(response, Response)
    assert not isinstance(response, FileResponse)
    assert EIS_ARCHIVE_REVIEW_MESSAGE.encode() in response.body
    assert "attachment" in response.headers["Content-Disposition"]
    assert path.read_text() == source


def test_unrelated_manual_upload_keeps_file_response_and_source(monkeypatch, tmp_path):
    path = tmp_path / "report.html"
    source = "<html><body><p>local report</p></body></html>"
    path.write_text(source)
    monkeypatch.setattr(legacy, "_report_html_path", lambda _rid: path)
    monkeypatch.setattr(legacy, "_ensure_procurement_blocked_report_html", lambda _rid: None)
    monkeypatch.setattr(legacy, "_load_metadata", lambda _rid: {"procurement_source": "manual_upload"})
    response = legacy.get_uploaded_demo_report_download("test-run")
    assert isinstance(response, FileResponse)
    assert legacy.get_uploaded_demo_report_html("test-run") == source


def test_saved_run_summary_hides_stale_go_without_mutating_response():
    class FakeModel:
        def __init__(self):
            self.limitations = []
            self.warnings = []
            self.final_recommendation = SimpleNamespace(recommendation="participate_conditionally")
            self.human_in_the_loop = False
            self.external_actions = True

        def model_copy(self, update):
            other = FakeModel()
            for key, value in update.items():
                setattr(other, key, value)
            return other

    original = FakeModel()
    projected = projected_historical_eis_run(_archived(), original)
    assert projected is not original
    assert projected.final_recommendation is None
    assert EIS_ARCHIVE_REVIEW_MESSAGE in projected.limitations
    assert not projected.external_actions
    assert projected.human_in_the_loop
    assert original.final_recommendation.recommendation == "participate_conditionally"
    assert projected_historical_eis_run({"procurement_source": "manual_upload"}, original) is original

def test_stale_eis_docx_pdf_export_fails_before_render(monkeypatch):
    from fastapi import HTTPException

    from src.modules.tender_operator_agent_demo import report_export_service as exports

    monkeypatch.setattr(exports, "_load_metadata", lambda _rid: _archived())

    for exporter in (
        exports.export_demo_agent_report_docx,
        exports.export_demo_agent_report_pdf,
    ):
        try:
            exporter("historical-1")
        except HTTPException as exc:
            assert exc.status_code == 409
            assert EIS_ARCHIVE_REVIEW_MESSAGE in exc.detail
        else:
            raise AssertionError("An archived EIS report must not be exported as a current PDF/DOCX")


def test_manually_verified_eis_or_unrelated_upload_not_blocked_for_binary_export():
    from src.modules.tender_operator_agent_demo.operator_eis_archive_freshness import (
        reject_unsafe_historical_eis_binary_export,
    )

    reject_unsafe_historical_eis_binary_export({"procurement_source": "manual_upload"})
    reject_unsafe_historical_eis_binary_export(
        {
            "procurement_source": "zakupki_gov_ru_getdocs_ip",
            "notice_revision_selected": {
                "version": 5,
                "current_live_eis_verified": True,
            },
        }
    )
