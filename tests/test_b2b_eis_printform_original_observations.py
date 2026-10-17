"""Live print form source observations are NOT live 44FZ legal bidding evidence."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from src.modules.tender_operator_agent_demo.eis_archived_deadline_status import (
    archived_notice_deadline_observation,
)

ROOT = Path(__file__).resolve().parents[1] / "docs/roadmap"
RECEIPT = json.loads((ROOT / "b2b_44fz_official_printform_observations_2026-10-17.json").read_text())
ARCHIVE = json.loads((ROOT / "b2b_eis_original_more_2026-10-17.json").read_text())


def test_original_official_public_status_not_faked():
    assert RECEIPT["schema_version"] == "b2b-44fz-official-printform-observations-v1"
    assert RECEIPT["public_printform_HTTP200_count"] == 10
    assert RECEIPT["source_HTML_number_identity_checked_count"] == 6
    assert RECEIPT["public_deadline_display_compared_with_archived_original_count"] == 5
    assert RECEIPT["current_legally_open_stage_proved_count"] == 0
    assert RECEIPT["owner_legal_bid_go_count"] == 0
    assert len(RECEIPT["items"]) == 10
    assert len({r["number"] for r in RECEIPT["items"]}) == 10
    assert datetime.fromisoformat(RECEIPT["generated_receipt_at_utc"]).tzinfo is not None
    for r in RECEIPT["items"]:
        assert r["original_public_http_code"] == 200
        assert 30_000 < r["original_public_html_response_bytes"] < 200_000
        assert r["url"] == (
            "https://zakupki.gov.ru/epz/order/notice/printForm/view.html?regNumber="
            + r["number"]
        )
        assert r["current_live_public_procurement_stage"] == "UNKNOWN"
        assert r["current_live_latest_notice_revision_verified"] is False
        assert r["qualified_to_submit_as_arvectum"] is False
        assert r["etp_action_executed"] is False
        assert len(r["archived_source_XML_sha256"]) == 64
        assert r["archived_source_notice_revision"] >= 1


def test_local_printform_deadline_proven_only_when_actually_extracted():
    rows = RECEIPT["items"]
    html_checked = [r for r in rows if r["verification_level"] == "HTML_IDENTITY_AND_NUMBER"]
    http_only = [r for r in rows if r["verification_level"] == "HTTP_TLS_URL_ONLY"]
    assert len(html_checked) == 6
    assert len(http_only) == 4
    assert all(r["public_printform_deadline_local_display"] is None for r in http_only)
    assert all(r["local_deadline_vs_original_archive"] == "NOT_EXTRACTED" for r in http_only)
    compared = [r for r in html_checked if r["public_printform_deadline_local_display"]]
    assert len(compared) == 5
    for r in compared:
        source = datetime.fromisoformat(r["archived_official_XML_endDT"])
        assert source.tzinfo is not None
        assert r["public_printform_deadline_local_display"] == source.strftime("%d.%m.%Y %H:%M")
        assert r["local_deadline_vs_original_archive"] == "MATCH_LOCAL_CLOCK_NOT_LIVE_STATUS"


def test_archive_source_sha_reused_unmodified_not_guessed():
    prior = {r["number"]: r for r in ARCHIVE["records"]}
    assert len(prior) == 8
    for item in RECEIPT["items"]:
        if item["number"] not in prior:
            continue
        source = prior[item["number"]]
        assert item["archived_source_XML_sha256"] == source["original_xml_sha256"]
        assert item["archived_source_notice_revision"] == source["selected_archived_version"]
        assert item["archived_official_XML_endDT"] == source["source_archived_end_dt"]
        assert source["current_live_legal_status_verified"] is False


def test_original_printed_future_deadline_does_not_promote_bid():
    n = "0161600001326000063"
    museum = next(r for r in RECEIPT["items"] if r["number"] == n)
    original = {
        "status": "KNOWN",
        "value": museum["archived_official_XML_endDT"],
        "evidence": [
            {"file_id": "NOTICE-001", "source_ref": "eis-xml:NOTICE-001:endDT", "locator": "XML:endDT"},
        ],
    }
    for now in (datetime(2026, 10, 17, 12, tzinfo=UTC), datetime(2026, 11, 1, tzinfo=UTC)):
        result = archived_notice_deadline_observation(original, as_of=now)
        assert result["source_fact_status"] == "KNOWN"
        assert result["current_public_eis_procedure_status"] == "UNKNOWN"
        assert result["current_public_notice_revision_verified"] is False
        assert result["live_submission_eligibility_verified"] is False
        assert result["authorized_to_submit"] is False
        assert result["final_protocol_or_award_verified"] is False
        assert result["relation_to_archived_deadline"] in (
            "ARCHIVED_CUTOFF_NOT_YET_REACHED", "ARCHIVED_CUTOFF_REACHED",
        )


def test_source_report_rejects_200_as_submission_proof():
    text = (ROOT / "B2B_EIS_PUBLIC_PRINTFORM_OBSERVATIONS_2026-10-17.md").read_text()
    assert "HTTP 200" in text
    assert "стадии/последней редакции — 0/10" in text
    assert "BID_READY" not in text or "не" in text
    assert "ЭТП" in text
    assert "не являются доказательством" in text
