"""No false B2B current qualified counts from original Oct17 public snapshots."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.acceptance.audit_workspace_oct17_cards import extract_public_card
from src.tender_research.corporate_lead_gate import triage_corporate_card

DATA = json.loads((
    Path(__file__).resolve().parents[1]
    / "docs/roadmap/b2b_workspace_original_2026-10-17.json"
).read_text(encoding="utf-8"))


def _document(*, organizer: str, status: str, day: int, month: str, title="Example original page",
              visibility: str = "public") -> bytes:
    return f'''
    <h1>{title}</h1>
    <div class="tendercart-type__status tendercart-type__status_flex">
      <div class="tendercart-type__status-public">{status}</div>
      <span class="reference _{visibility}">{visibility}</span>
    </div>
    <section>Oрганизатор<div><strong>{organizer}</strong></div></section>
    <section>Крайний срок приема заявок:<div>{day} {month} 2026</div></section>
    '''.encode()


def test_new_five_originals_are_source_attested_corporate_candidates_only():
    assert DATA["schema_version"] == "b2b-workspace-original-oct17-v1"
    assert DATA["new_distinct_corporate_original_cards"] == 5
    assert DATA["excluded_or_closed_cards"] == 3
    assert DATA["all_current_procurement_goal_15_20_met"] is False
    assert DATA["actual_bid_eligibility_verified"] is False
    assert DATA["paid_pro_or_invitation_checked"] is False
    expected = {"workspace-19043", "workspace-19042", "workspace-19034",
                "workspace-19032", "workspace-19030"}
    assert {r["id"] for r in DATA["current_public_source_candidates"]} == expected
    for record in DATA["current_public_source_candidates"]:
        assert record["source_kind"] == "ORIGINAL_PUBLIC_WORKSPACE_CARD"
        assert record["source_http_status"] == 200
        assert record["organizer_type"] == "Юридическое лицо"
        assert record["platform_status"] == "Идет прием заявок"
        assert record["visibility"] == "public"
        assert record["source_status_gate"] == "PUBLIC_CANDIDATE_ONLY"
        assert record["original_source_html_size"] > 40_000
        assert len(record["original_source_html_sha256"]) == 64
        assert not record["bid_ready"] and not record["human_go"]
        assert record["agency_eligibility"] == "UNVERIFIED"
        assert "?" not in record["source_url"] and "#" not in record["source_url"]
        actual = datetime.fromisoformat(record["checked_at"])
        assert actual.tzinfo is not None
        gate = triage_corporate_card({
            "source_url": record["source_url"],
            "organizer_type": record["organizer_type"],
            "platform_status": record["platform_status"],
            "source_observed_at": record["checked_at"],
            "submission_deadline": record["application_deadline_date"],
        }, checked_at=actual)
        assert gate.state == "PUBLIC_CANDIDATE_ONLY" and not gate.bid_ready


def test_two_private_and_one_terminal_original_are_not_promoted():
    records = {r["id"]: r for r in DATA["excluded_cards"]}
    assert set(records) == {"workspace-19052", "workspace-19035", "workspace-19023"}
    assert records["workspace-19052"]["organizer_type"] == "Частное лицо"
    assert records["workspace-19035"]["organizer_type"] == "Частное лицо"
    assert records["workspace-19023"]["platform_status"] == "Завершён"
    assert records["workspace-19023"]["application_deadline_date"] == "2026-10-20"
    for record in records.values():
        assert record["source_status_gate"] != "PUBLIC_CANDIDATE_ONLY"
        assert not record["bid_ready"]
        result = triage_corporate_card({
            "source_url": record["source_url"],
            "organizer_type": record["organizer_type"],
            "platform_status": record["platform_status"],
            "source_observed_at": record["checked_at"],
            "submission_deadline": record["application_deadline_date"],
        }, checked_at=datetime.fromisoformat(record["checked_at"]))
        assert result.state == record["source_status_gate"]


def test_synthetic_known_good_extracts_exact_source_but_no_bid_ready():
    case = extract_public_card(
        _document(organizer="Юридическое лицо", status="Идет прием заявок",
                  day=31, month="октября"),
        key="19043", observed=datetime(2026, 10, 17, 12, tzinfo=UTC),
    )
    assert case["application_deadline_date"] == "2026-10-31"
    assert case["source_status_gate"] == "PUBLIC_CANDIDATE_ONLY"
    assert case["bid_ready"] is False


@pytest.mark.parametrize("change", [
    {"organizer": "Частное лицо"},
    {"status": "Завершён"},
    {"status": "Прием заявок завершен"},
    {"day": 16},
    {"month": "ноября"},
    {"visibility": "private"},
])
def test_changed_original_source_never_promotes_corporate_candidate(change):
    kwargs = {"organizer": "Юридическое лицо", "status": "Идет прием заявок",
              "day": 31, "month": "октября"}
    kwargs.update(change)
    with pytest.raises(ValueError):
        extract_public_card(_document(**kwargs), key="19043",
                            observed=datetime(2026, 10, 17, 12, tzinfo=UTC))


@pytest.mark.parametrize("change", [
    "unknown_original_card", "missing_organizer", "double_status", "oversized_page",
])
def test_ambiguous_original_raises(change):
    kwargs = {"organizer": "Юридическое лицо", "status": "Идет прием заявок",
              "day": 31, "month": "октября"}
    data = _document(**kwargs)
    if change == "unknown_original_card":
        key = "19024"
    else:
        key = "19043"
    if change == "missing_organizer":
        data = data.replace(b"O", b"Q", 1)
    elif change == "double_status":
        data += b'<div class="tendercart-type__status-public">Zavershen</div>'
    elif change == "oversized_page":
        data += b"x" * 400_100
    with pytest.raises(ValueError):
        extract_public_card(data, key=key, observed=datetime.now(UTC))


def test_old_19023_source_is_aliased_but_one_id_and_terminal():
    excluded = next(r for r in DATA["excluded_cards"] if r["id"] == "workspace-19023")
    assert excluded["source_url"] == "https://workspace.ru/tenders/private-tender-19023/"
    assert excluded["platform_status"] == "Завершён"
    assert excluded["source_status_reason"] == "terminal_platform_status"
    assert not excluded["bid_ready"]
