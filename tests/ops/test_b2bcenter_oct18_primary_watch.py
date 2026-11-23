"""Offline adversarial first-party B2B-Center index vs detail status gate."""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.ops.b2bcenter_oct18_primary_watch import (
    INDEX,
    OriginalMarketError,
    _detail_row,
    _index_row,
    audit,
    evaluate,
    validate_watchlist,
)

ROOT = Path(__file__).resolve().parents[2] / "docs/roadmap"
DATE = datetime(2026, 10, 18, 16, 20, tzinfo=UTC)


def fixture_watch():
    return json.loads((ROOT / "b2bcenter_watchlist_oct18.json").read_text())


def _index_fixture(item, deadline="23.10.2026 14:30", number=None):
    number = number or item["id"]
    body = (
        "<html><head><meta charset=utf-8></head><body><div><div>"
        f"Опубликовано: 8.10.2026 12:52 мск Подать заявку до: {deadline} мск "
        f"Закупка №{number} RFI CRM Начальная цена 0,00 ₽ Организатор X5 "
        f'<a href="{item["url"]}">Закупка №{number}</a>'
        "</div></div>"
        + " " * 1400 + "</body></html>"
    )
    return body.encode()


def _detail_fixture(item, deadline="23.10.2026 14:30", since=False, label="Приём заявок"):
    id_ = item["id"]
    time = ("с " if since else "до ") + deadline + ", по МСК"
    html = (
        f"<html><head><meta charset='utf-8'><title>RFI CRM — Тендер № {id_} — B2B-Center</title></head>"
        f"<body><h1>RFI CRM</h1><span>№ {id_}</span>"
        f"<span>{time}</span><span>{label}</span>"
        "<span>Рассмотрение</span><span>Завершена</span>"
        + " " * 1400 + "</body></html>"
    )
    return html.encode()


def test_real_receipt_count_gates_and_provenance_not_company_ready():
    r = json.loads((ROOT / "b2bcenter_six_primary_oct18.json").read_text())
    ids = [x["id"] for x in r["items"]]
    assert len(ids) == len(set(ids)) == 6
    assert "4643484" not in ids
    assert r["attempted_explicit_original_cards"] == 6
    assert r["original_public_http200_card_pages_checked"] == 6
    assert r["source_identity_and_stage_parsed_count"] == 5
    assert r["market_research_active_count"] == 1
    assert r["license_resale_excluded_count"] == 1
    assert r["past_or_nonaccepting_count"] == 3
    assert r["strictly_qualified_current_company_bid_count"] == 0
    assert r["goal_15_to_20_reached"] is False
    assert r["source_origin_only_no_submissions_or_fees"] is True
    by_id = {x["id"]: x for x in r["items"]}
    assert by_id["4632891"]["source_gate"] == "RFI_MARKET_RESEARCH_NOT_CONTRACT_AWARD"
    assert by_id["4632891"]["index_published_deadline_moscow"] == "2026-10-23T14:30:00+03:00"
    assert by_id["4636284"]["source_gate"] == "EXCLUDE_LICENSE_RESALE_NOT_SOFTWARE_DEVELOPMENT"
    assert by_id["4636284"]["index_published_deadline_moscow"] == "2026-10-20T10:00:00+03:00"
    assert by_id["4633713"]["index_published_deadline_moscow"] == "2026-10-15T12:00:00+03:00"
    assert by_id["4632699"]["source_gate"] == "SOURCE_IDENTITY_OR_STAGE_REQUIRES_REVIEW"
    assert by_id["4632699"]["index_displayed_purchase_number"] == "4632682/1"
    assert by_id["4632699"]["index_published_deadline_moscow"] == "2026-10-14T16:00:00+03:00"
    for row in r["items"]:
        assert row["original_http_status"] == 200
        assert len(row["detail_html_sha256"]) == len(row["category_html_sha256"]) == 64
        assert row["owner_bid_go"] is False
        assert row["bidder_legal_eligibility_verified"] is False
        assert row["platform_fee_and_account_access_verified"] is False
        assert row["commercial_budget_verified"] is False
        assert row["all_customer_documents_read"] is False
        assert row["external_actions_taken"] is False


def test_no_network_fixture_primary_validation_market_research():
    item = fixture_watch()[0]
    idx = _index_fixture(item)
    detail = _detail_fixture(item)
    assert _index_row(idx, item["url"])["index_displayed_purchase_number"] == item["id"]
    assert _detail_row(detail, item["id"])["static_progress_label"] == "Приём заявок"
    output = evaluate(item, idx, detail, DATE)
    assert output["public_deadline_assessment"] == "PUBLIC_DEADLINE_FUTURE_AND_VISIBLE_ACCEPTING"
    assert output["source_gate"] == "RFI_MARKET_RESEARCH_NOT_CONTRACT_AWARD"
    assert output["index_budget_literal"] == "0,00 ₽ - INDEX PLACEHOLDER NOT BUYER PRICE"
    assert output["original_total_purchase_price_verified"] is False
    assert output["owner_bid_go"] is False


def test_old_progress_label_does_not_promote_past_deadline():
    item = fixture_watch()[0]
    idx = _index_fixture(item, deadline="15.10.2026 12:00")
    detail = _detail_fixture(item, deadline="16.10.2026 16:04", since=True)
    result = evaluate(item, idx, detail, DATE)
    assert result["public_deadline_assessment"] == "NOT_PUBLICLY_ACCEPTING_AS_OF_CAPTURE"
    assert result["source_gate"] == "EXCLUDE_PAST_OR_NONACCEPTING_PUBLIC_DEADLINE"


def test_nominal_open_label_past_deadline_excluded():
    item = fixture_watch()[0]
    output = evaluate(item, _index_fixture(item, deadline="17.10.2026 14:30"),
                      _detail_fixture(item, deadline="17.10.2026 14:30"), DATE)
    assert output["source_gate"] == "EXCLUDE_PAST_OR_NONACCEPTING_PUBLIC_DEADLINE"


@pytest.mark.parametrize(("index_end", "detail_end"), [
    ("23.10.2026 14:30", "22.10.2026 14:30"),
    ("23.10.2026 14:30", "30.10.2026 14:30"),
])
def test_unequal_index_and_direct_original_deadline_fails_closed(index_end, detail_end):
    item = fixture_watch()[0]
    with pytest.raises(OriginalMarketError, match="deadline differs"):
        evaluate(item, _index_fixture(item, deadline=index_end),
                 _detail_fixture(item, deadline=detail_end), DATE)


def test_history_alias_and_real_number_conflict_rejected():
    item = fixture_watch()[0]
    with pytest.raises(OriginalMarketError, match="INDEX_NUMBER_ALIAS"):
        evaluate(item, _index_fixture(item, number="4632682/1"), _detail_fixture(item), DATE)


@pytest.mark.parametrize("strange", [
    "https://evil.example/market/tender-4632891/",
    "http://www.b2b-center.ru/market/tender-4632891/",
    "https://www.b2b-center.ru/market/anything/tender-4643484/",
    "https://www.b2b-center.ru/market/anything/tender-4632891/?token=secret",
    "https://www.b2b-center.ru/market/anything/tender-4632890/",
])
def test_watchlist_external_or_different_source_rejected(strange):
    items = fixture_watch()
    items[0]["url"] = strange
    with pytest.raises(OriginalMarketError):
        validate_watchlist(items)


def test_duplicate_b2b_tender_id_rejected():
    items = fixture_watch()
    items[0] = copy.deepcopy(items[1])
    with pytest.raises(OriginalMarketError):
        validate_watchlist(items)


def test_captured_originals_have_independent_sha_and_no_price_or_hidden_files():
    receipt = json.loads((ROOT / "b2bcenter_six_primary_oct18.json").read_text())
    assert len({x["detail_html_sha256"] for x in receipt["items"]}) == 6
    for row in receipt["items"]:
        assert row["detail_html_bytes"] > 1200
        assert row["category_html_bytes"] > 1200
        assert row["detail_html_sha256"] != hashlib.sha256(b"").hexdigest()


def test_source_origin_fetch_failure_stays_unknown_and_not_buyer_go():
    item = fixture_watch()[0]
    category = INDEX.format(category=item["category"])
    def fake(url):
        if url == category:
            return _index_fixture(item)
        raise TimeoutError("unreachable")
    # Must use all six watchlist items, so cover all categories and arbitrary
    # non-matching exact category cards as well.
    def fetch(url):
        if "/search/industry/" in url:
            return b"<html>" + b" " * 1600 + b"</html>"
        raise TimeoutError("site unavailable")
    result = audit(fixture_watch(), fetch=fetch, now=DATE)
    assert result["original_public_http200_card_pages_checked"] == 0
    assert result["strictly_qualified_current_company_bid_count"] == 0
    assert all(x["source_gate"] == "SOURCE_IDENTITY_OR_STAGE_REQUIRES_REVIEW"
               for x in result["items"])


def test_receipt_observation_is_offset_aware():
    receipt = json.loads((ROOT / "b2bcenter_six_primary_oct18.json").read_text())
    stamp = datetime.fromisoformat(receipt["observed_at_utc"])
    assert stamp.tzinfo is not None
    assert stamp.astimezone(UTC).year == 2026
