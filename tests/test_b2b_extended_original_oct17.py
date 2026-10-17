"""Original-source dated expansion: mobile Workspace vs official archived EIS."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scripts.acceptance.audit_workspace_mobile_oct17 import (
    _MOBILE,
    classify_mobile_2026_snapshot,
)
from scripts.acceptance.audit_workspace_oct17_cards import extract_public_card
from src.tender_research.corporate_lead_gate import triage_corporate_card

ROOT = Path(__file__).resolve().parents[1] / "docs/roadmap"
MOBILE = json.loads((ROOT / "b2b_workspace_mobile_original_2026-10-17.json").read_text())
EIS = json.loads((ROOT / "b2b_eis_original_more_2026-10-17.json").read_text())
OLD = json.loads((ROOT / "b2b_workspace_original_2026-10-17.json").read_text())

LICENSE_ONLY = {"0373100001026000837", "0500500009026000003"}
DEVELOPMENT_UNREVIEWED = {
    "0122200002526003753",
    "0112200000826004516",
    "0161600001326000063",
    "0304200005726000015",
    "0366200035626006502",
    "0816500000626015655",
}


def test_mobile_first_party_receipts_have_two_new_cards_not_ten():
    assert MOBILE["new_original_distinct_card_ids"] == 2
    assert set(MOBILE["new_card_ids"]) == {"workspace-19041", "workspace-18939"}
    assert MOBILE["existing_historical_distinct_card_counted_again"] == 0
    assert MOBILE["excluded_or_needs_review"] == 7
    assert MOBILE["bounded_exact_readonly_public_cards"] == 10
    assert MOBILE["new_distinct_procurement_business_opportunities_confirmed"] is False
    assert MOBILE["qualifying_source_goal_15_20_met"] is False
    assert MOBILE["actual_eligible_bids"] == 0
    assert MOBILE["etp_action"] == "NONE"
    assert len(MOBILE["public_original_receipts"]) == len(_MOBILE)
    prior_ids = {q["id"] for q in OLD["current_public_source_candidates"]}
    prior_ids.update(q["id"] for q in OLD["excluded_cards"])
    assert set(MOBILE["new_card_ids"]).isdisjoint(prior_ids)
    found = set()
    for row in MOBILE["public_original_receipts"]:
        assert row["id"] not in found
        found.add(row["id"])
        key = row["id"].removeprefix("workspace-")
        assert key in _MOBILE
        assert row["source_kind"] == "ORIGINAL_PUBLIC_WORKSPACE_CARD"
        assert row["source_url"] == f"https://workspace.ru/tenders/{_MOBILE[key][0]}-{key}/"
        assert row["application_deadline_date"] == _MOBILE[key][1]
        assert row["competitive_fit"] == _MOBILE[key][2]
        assert row["source_http_status"] == 200
        assert row["original_source_html_size"] > 35_000
        assert re.fullmatch("[0-9a-f]{64}", row["original_source_html_sha256"])
        observed = datetime.fromisoformat(row["checked_at"])
        assert observed.tzinfo is not None and observed.date().isoformat() == "2026-10-17"
        gate = triage_corporate_card({
            "source_url": row["source_url"],
            "platform_status": row["platform_status"],
            "organizer_type": row["organizer_type"],
            "source_observed_at": row["checked_at"],
            "submission_deadline": row["application_deadline_date"],
        }, checked_at=observed)
        assert gate.state == row["source_status_gate"]
        assert row["bid_ready"] is False
        assert row["human_go"] is False
        assert row["agency_eligibility"] == "UNVERIFIED"
        assert classify_mobile_2026_snapshot(row) == row["counting_disposition"]


def test_old_open_card_not_recounted_new_mobile_customer_and_same_day_gated():
    rows = {x["id"]: x for x in MOBILE["public_original_receipts"]}
    assert rows["workspace-18998"]["source_status_gate"] == "PUBLIC_CANDIDATE_ONLY"
    assert rows["workspace-18998"]["counting_disposition"] == "CURRENT_PUBLIC_HISTORICAL_ALREADY_COUNTED"
    assert rows["workspace-19041"]["possible_shared_customer_project"] is True
    assert rows["workspace-19041"]["counting_disposition"] == "NEW_CARD_BUT_POSSIBLE_SHARED_BUYER_19042"
    assert rows["workspace-19010"]["platform_status"] == "Идет прием заявок"
    assert rows["workspace-19010"]["same_day_time_unknown"] is True
    assert rows["workspace-19010"]["source_status_gate"] == "REVIEW_REQUIRED"
    assert rows["workspace-19007"]["organizer_type"] == "Частное лицо"
    assert rows["workspace-19007"]["source_status_gate"] != "PUBLIC_CANDIDATE_ONLY"


def _synthetic(status: str, buyer: str, day: int, month: str) -> bytes:
    return (
        '<h1>Test original Workspace procurement</h1>'
        f'<div class="tendercart-type__status-public">{status}</div>'
        '<span class="reference _public">Public</span>'
        f'<div>Oрганизатор <span>{buyer}</span></div>'
        f'<div>Крайний срок приема заявок: <span>{day} {month} 2026</span></div>'
    ).encode()


@pytest.mark.parametrize("number,day,month,status,buyer,valid", [
    ("19041", 31, "октября", "Идет прием заявок", "Юридическое лицо", True),
    ("19041", 16, "октября", "Идет прием заявок", "Юридическое лицо", False),
    ("19041", 31, "октября", "Прием заявок завершен", "Юридическое лицо", False),
    ("19041", 31, "октября", "Идет прием заявок", "Частное лицо", False),
    ("19010", 17, "октября", "Идет прием заявок", "Юридическое лицо", True),
])
def test_parse_original_new_allowlist_never_promotes_unverified(
    number, day, month, status, buyer, valid
):
    as_of = datetime(2026, 10, 17, 11, tzinfo=UTC)
    if valid:
        actual = extract_public_card(
            _synthetic(status, buyer, day, month),
            key=number, observed=as_of, allowed_cards=_MOBILE,
        )
        assert actual["bid_ready"] is False
        if number == "19010":
            assert actual["source_status_gate"] == "REVIEW_REQUIRED"
        else:
            assert actual["source_status_gate"] == "PUBLIC_CANDIDATE_ONLY"
    else:
        with pytest.raises(ValueError):
            extract_public_card(
                _synthetic(status, buyer, day, month),
                key=number, observed=as_of, allowed_cards=_MOBILE,
            )


def test_eis_original_competitive_archived_notice_sha_and_exact_timezones():
    assert EIS["schema_version"] == "b2b-firstparty-44fz-original-20261017-v1"
    assert EIS["read_only"] and EIS["no_original_binaries_persisted"]
    assert EIS["owner_bid_ready_count"] == 0
    assert EIS["current_legal_status_verified"] is False
    rows = EIS["records"]
    assert len(rows) == 8
    assert len({x["number"] for x in rows}) == 8
    assert {x["number"] for x in rows} == DEVELOPMENT_UNREVIEWED | LICENSE_ONLY
    for row in rows:
        assert row["source_type"] == "OFFICIAL_EIS_SOAP_GETDOCSIP_ARCHIVED_ORIGINAL"
        assert row["archival_evidence"] == "SHA_VERIFIED_NOTICE"
        assert row["competitive_status"] == "ATTESTED_COMPETITIVE"
        assert row["source_notice_type"].startswith("epNotification")
        assert row["selected_archived_version"] >= 1
        assert re.fullmatch(r"[0-9a-f]{64}", row["zip_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", row["original_xml_sha256"])
        assert row["zip_original_bytes"] > 3000
        assert row["source_name"].startswith("epNotification")
        assert row["source_name"].endswith(".xml")
        assert row["number"] in row["source_name"]
        assert "/" not in row["source_name"] and "\\" not in row["source_name"]
        assert row["archived_deadline_future_as_of_observation"] is True
        archived = datetime.fromisoformat(row["source_archived_end_dt"])
        read = datetime.fromisoformat(row["observed_at_utc"])
        assert archived.tzinfo is not None and read.tzinfo is not None
        assert archived > read
        assert float(row["source_archived_nmck_rub"]) > 100_000
        assert len(row["original_purchase_object"]) > 30
        assert row["current_live_legal_status_verified"] is False
        assert row["current_notice_latest_live_verified"] is False
        assert row["full_attached_documents_verified"] is False
        assert row["owner_qualified"] is False
        assert row["bid_ready"] is False
        assert row["etp_actions_executed"] is False
    # EIS deadline is localized in notice's region, not naive Moscow clock.
    sample = next(x for x in rows if x["number"] == "0122200002526003753")
    assert datetime.fromisoformat(sample["source_archived_end_dt"]).astimezone(
        ZoneInfo("Europe/Moscow")
    ).strftime("%Y-%m-%d %H:%M") == "2026-10-23 01:00"
    sample = next(x for x in rows if x["number"] == "0816500000626015655")
    assert datetime.fromisoformat(sample["source_archived_end_dt"]).astimezone(
        ZoneInfo("Europe/Moscow")
    ).strftime("%Y-%m-%d %H:%M") == "2026-10-30 03:30"


def test_license_resale_is_not_sold_as_new_custom_development_project():
    rows = {x["number"]: x for x in EIS["records"]}
    assert "Передача неисключительных прав" in rows["0373100001026000837"]["original_purchase_object"]
    assert "предоставлению прав" in rows["0500500009026000003"]["original_purchase_object"]
    assert all(not x["owner_qualified"] for x in rows.values())


def test_no_duplicate_with_oct17_earlier_verified_eis_or_workspace():
    earlier_original_44fz = {"0163200000326005243", "0335200014926003900"}
    assert earlier_original_44fz.isdisjoint({x["number"] for x in EIS["records"]})
    assert all(not r["bid_ready"] for r in MOBILE["public_original_receipts"])
