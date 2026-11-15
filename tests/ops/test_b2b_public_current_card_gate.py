"""No-network, adversarial public *display* and historical dedupe tests."""
from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.ops.b2b_public_current_card_gate import (
    OFFICIAL_HOME,
    PublicStageError,
    _commercial_record,
    _eis_record,
    _safe_url,
    dedupe_new_ids,
    observe,
)

SRC = Path(__file__).resolve().parents[2] / "docs" / "roadmap"
AT = datetime(2026, 10, 18, 19, 12, tzinfo=UTC)


def frozen():
    return [
        json.loads((SRC / name).read_text())
        for name in (
            "b2b_oct18_three_new_eis_originals.json",
            "b2b_44fz_official_printform_observations_2026-10-17.json",
            "b2b_oct18_b2bcenter_4643484_firstparty.json",
        )
    ]


def commercial_html(stage="Приём заявок", deadline="до 21.10.2026 06:00, по МСК"):
    return (
        '<html><head><title>Разработка корпоративного сайта под ключ с обязательным предоставлением '
        'реализованных кейсов и коммерческих предложений — Тендер № 4643484</title></head>'
        '<body><h1>Разработка корпоративного сайта под ключ с обязательным предоставлением '
        'реализованных кейсов и коммерческих предложений — Тендер № 4643484</h1>'
        '<div>АО "ТЕХ ВЗРЫВ ИНВЕСТ"</div>'
        f'<div>{stage}</div><div>{deadline}</div>'
        '<script>Приём заявок <b>IGNORE SCRIPT</b></script><div>'
        + (" " * 1300) + "</div></body></html>"
    ).encode()


def safe_fetch(url):
    if url == OFFICIAL_HOME:
        return {"http_state": "HTTP_200", "raw": b"<html>official portal reachable</html>" + b" " * 1600}
    if url.endswith("4643484/"):
        return {"http_state": "HTTP_200", "raw": commercial_html()}
    return {"http_state": "HTTP_404", "raw": None}


def test_exact_original_history_dedupes_smolensk_not_three_new_ids():
    src, previous, _ = frozen()
    result = dedupe_new_ids(src, previous)
    assert result["eis_originals_refetched_count"] == 3
    assert result["previously_firstparty_seen_original_ids"] == ["0163200000326005243"]
    assert result["net_new_distinct_eis_44fz_original_ids_vs_17_oct"] == [
        "0148200002426000013", "0332100025426000039"
    ]
    assert result["net_new_eis_44fz_original_count_vs_17_oct"] == 2


def test_overall_public_card_check_fail_closed_and_distinct_counts():
    src, old, b2b = frozen()
    state = copy.deepcopy((src, old, b2b))
    result = observe(src, old, b2b, observed=AT, fetch=safe_fetch)
    assert (src, old, b2b) == state
    assert result["new_distinct_primary_source_attestations_vs_17_oct"] == 3
    assert result["eis_current_legal_notice_status_verified_count"] == 0
    assert result["company_confirmed_bid_eligible_count"] == 0
    assert result["goal_15_20_strictly_qualified_met"] is False
    assert result["eis_live_notice_pages_parsed"] == 0
    assert result["eis_host_control"]["http_state"] == "HTTP_200"
    assert result["eis_host_control"]["proves_specific_notice_stage"] is False
    assert len(result["eis_rows"]) == 3
    for row in result["eis_rows"]:
        assert row["live_common_info"]["http_state"] == "HTTP_404"
        assert row["public_printform"]["http_state"] == "HTTP_404"
        assert row["current_legal_stage_verified"] is False
        assert row["bid_ready"] is False
    commercial = result["commercial_primary"]
    assert commercial["platform_displayed_stage"] == "Приём заявок"
    assert commercial["platform_displayed_deadline"] == "2026-10-21T06:00:00+03:00"
    assert commercial["source_parse_state"] == "FIRST_PARTY_PUBLIC_STAGE_AT_CAPTURE_ONLY"
    assert commercial["bid_ready"] is False
    assert commercial["full_sow_confirmed"] is False


def test_current_repo_source_receipt_six_404_not_proof_of_cancelled_bid():
    got = json.loads((SRC / "b2b_oct18_current_public_display_check.json").read_text())
    assert got["new_distinct_primary_source_attestations_vs_17_oct"] == 3
    assert got["eis_current_legal_notice_status_verified_count"] == 0
    assert got["commercial_primary"]["http_state"] == "HTTP_200"
    assert got["eis_host_control"]["http_state"] in {"HTTP_200", "HTTP200_BODY_NOT_ATTESTED"}
    assert got["commercial_primary"]["source_parse_state"] == "FIRST_PARTY_PUBLIC_STAGE_AT_CAPTURE_ONLY"
    assert got["commercial_primary"]["buyer_budget_confirmed"] is False
    for row in got["eis_rows"]:
        assert row["live_common_info"]["http_state"] == "HTTP_404"
        assert row["public_printform"]["http_state"] == "HTTP_404"
        assert row["live_common_info"]["firstparty_displayed_stage"] == "UNKNOWN"
        assert row["public_printform"]["firstparty_displayed_stage"] == "UNKNOWN"
        assert row["authenticated_bidder_eligibility_verified"] is False


def test_200_nonmatching_eis_html_does_not_upgrade_current_or_archived_status():
    src, _, _ = frozen()
    fake = b"<html>arbitrary content not actual current EIS page" + b" " * 1500 + b"</html>"
    row = _eis_record(src["records"][0], AT, lambda _: {"http_state": "HTTP_200", "raw": fake})
    assert row["live_common_info"]["source_parse_state"] == "UNVERIFIED_CARD_CONTENT"
    assert row["public_printform"]["source_parse_state"] == "UNVERIFIED_PRINTFORM"
    assert row["current_official_xml_latest_edition_verified"] is False
    assert row["bid_ready"] is False


def test_commercial_actual_page_stage_not_equals_owner_eligibility():
    b2b = frozen()[2]
    row = _commercial_record(b2b, AT, safe_fetch)
    assert row["vendor_account_entitlement_confirmed"] is False
    assert row["documented_comparable_completed_cases_confirmed"] is False
    assert row["bid_ready"] is False


@pytest.mark.parametrize("stage,expected", [
    ("Завершён", "FIRST_PARTY_TERMINAL_STAGE_AT_CAPTURE"),
    ("Приём заявок завершён", "FIRST_PARTY_TERMINAL_STAGE_AT_CAPTURE"),
    ("Открыто", "AMBIGUOUS_OR_CHANGED_STAGE"),
    ("", "AMBIGUOUS_OR_CHANGED_STAGE"),
])
def test_commercial_stage_changes_do_not_silently_become_current_active(stage, expected):
    row = _commercial_record(frozen()[2], AT, lambda _: {"http_state": "HTTP_200", "raw": commercial_html(stage)})
    assert row["source_parse_state"] == expected
    assert row["bid_ready"] is False


def test_printed_deadline_past_even_if_page_says_accepting():
    later = datetime(2026, 10, 21, 6, 0, tzinfo=datetime.fromisoformat(
        "2026-10-21T06:00:00+03:00"
    ).tzinfo)
    row = _commercial_record(frozen()[2], later, safe_fetch)
    assert row["source_parse_state"] == "EXPIRED_PRINTED_DEADLINE_DESPITE_ACTIVE_LABEL"
    assert row["bid_ready"] is False


@pytest.mark.parametrize("body", [
    b"<html>empty</html>",
    b"<html><script>bad</script></html>" + b" " * 1500,
    commercial_html().replace(b"4643484", b"0000000"),
    commercial_html().replace("ТЕХ ВЗРЫВ ИНВЕСТ".encode(), "ИНОЙ ОРГАНИЗАТОР".encode()),
    commercial_html().replace(b"21.10.2026", b"18.10.2026"),
])
def test_false_html_identity_incorrect_deadline_or_tiny_body_never_passes(body):
    row = _commercial_record(frozen()[2], AT, lambda _: {"http_state": "HTTP_200", "raw": body})
    assert row["platform_displayed_stage"] == "UNKNOWN"
    assert row["bid_ready"] is False
    assert row["source_parse_state"] in {"AMBIGUOUS_OR_CHANGED_STAGE", "UNVERIFIED_CARD"}


def test_no_current_firstparty_response_is_not_downgraded_to_guessed_stage():
    row = _commercial_record(frozen()[2], AT, lambda _: {"http_state": "HTTP_403", "raw": None})
    assert row["platform_displayed_stage"] == "UNKNOWN"
    assert row["buyer_budget_confirmed"] is False


@pytest.mark.parametrize("url", [
    "http://zakupki.gov.ru/path", "https://evil.example/path",
    "https://user:pass@zakupki.gov.ru/path", "https://zakupki.gov.ru/path#fragment",
])
def test_curl_url_mismatch_and_redirect_guarded(url):
    assert not _safe_url("https://zakupki.gov.ru/path", url)


def test_tampered_history_fails_closed():
    src, older, _ = frozen()
    older["items"] = [x for x in older["items"] if x.get("number") != "0163200000326005243"]
    with pytest.raises(PublicStageError):
        dedupe_new_ids(src, older)


def test_duplicate_current_notice_numbers_rejected():
    src, older, _ = frozen()
    src["records"][0]["number"] = src["records"][1]["number"]
    with pytest.raises(PublicStageError):
        dedupe_new_ids(src, older)


def test_naive_capture_time_refused():
    src, old, b2b = frozen()
    with pytest.raises(PublicStageError):
        observe(src, old, b2b, observed=datetime(2026, 10, 18), fetch=safe_fetch)  # noqa: DTZ001 - negative test
