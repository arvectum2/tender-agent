"""No invented exact EIS submission clock time from date-only public cards.

Synthetic-only; no DB, login, EIS request or actual procurement status changes.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.modules.daily_tender_run.profiles import load_daily_tender_profile
from src.modules.daily_tender_run.service import _parse_deadline, _screen_card


@pytest.mark.parametrize("source_date", [
    "30.11.2026",
    "2026-11-30",
    " 30.11.2026 ",
    "2026-11-30 ",
])
def test_public_eis_date_only_has_no_exact_submission_clock_time(source_date):
    # A previous parser had converted each of these to 29 Nov 21:00 UTC
    # (= 30 Nov midnight Moscow), which is NOT source-confirmed.
    assert _parse_deadline(source_date) is None


@pytest.mark.parametrize(("source", "expected"), [
    ("30.11.2026 09:00", datetime(2026, 11, 30, 6, 0, tzinfo=UTC)),
    ("30.11.2026 09:00:00", datetime(2026, 11, 30, 6, 0, tzinfo=UTC)),
    ("2026-11-30T09:00:00", datetime(2026, 11, 30, 6, 0, tzinfo=UTC)),
    ("2026-11-30T09:00:00+03:00", datetime(2026, 11, 30, 6, 0, tzinfo=UTC)),
    ("2026-11-30T06:00:00+00:00", datetime(2026, 11, 30, 6, 0, tzinfo=UTC)),
    ("30.11.2026 00:00", datetime(2026, 11, 29, 21, 0, tzinfo=UTC)),
])
def test_explicit_source_clock_time_retained_and_normalized(source, expected):
    assert _parse_deadline(source) == expected


def test_date_only_not_dropped_as_expired_midnight_and_flagged_for_manager():
    profile = load_daily_tender_profile("arvectum-it")
    card = {
        "registry_number": "0845500000526000021",
        "source": "public_eis_html_44fz",
        "source_url": (
            "https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html"
            "?regNumber=0845500000526000021"
        ),
        "title": "Выполнение работ по разработке программного обеспечения Чат-бот для MAX",
        "initial_price": 551315.0,
        "deadline": "30.11.2026",
        "status": "Подача заявок",
    }
    # EIS summary is date-only; on that calendar day it may still be open.
    # Never let the invented 00:00 MSK exclude it as expired.
    state, score, reasons = _screen_card(
        profile, card, now=datetime(2026, 11, 29, 22, 0, tzinfo=UTC),
    )
    assert state == "IN"
    assert score >= 0
    assert "deadline_unknown" in reasons
    assert "deadline_date_only_time_unverified" in reasons
    assert "application_deadline_expired" not in reasons


def test_explicit_past_deadline_is_still_screened_out():
    profile = load_daily_tender_profile("arvectum-it")
    card = {
        "title": "Разработка программного обеспечения",
        "deadline": "30.11.2026 09:00",
        "status": "Подача заявок",
    }
    state, score, reasons = _screen_card(
        profile, card, now=datetime(2026, 11, 30, 7, 0, tzinfo=UTC),
    )
    assert state == "OUT"
    assert score == 0.0
    assert reasons == ["application_deadline_expired"]


def test_iso_date_object_not_treated_as_submission_time():
    # Date-like Python value must not become a fabricated UTC timestamp.
    from datetime import date

    assert _parse_deadline(date(2026, 11, 30)) is None
