from urllib.parse import parse_qs, urlsplit

from scripts.research.capture_gpb_history_partitions import Count, bounds, source_url


def test_month_bounds_and_exact_query():
    a,b = bounds("2024-02")
    assert a.day == 1 and b.day == 29
    q = parse_qs(urlsplit(source_url("2024-02",2)).query)
    assert q["procedure[accepted_from]"] == ["01.02.2024"]
    assert q["procedure[accepted_to]"] == ["29.02.2024"]
    assert q["procedure[section][0]"] == ["geh_group"]


def test_reported_count():
    p=Count()
    p.feed("<div>1 234 предложения</div>")
    assert p.values == {1234}


def test_explicit_auction_date_is_separate(monkeypatch):
    from scripts.research.capture_gpb_history_partitions import archive_rows

    original = "12 января 2024, 15:00 Z Дата торгов 26 января 2024, 07:00 Z"
    monkeypatch.setattr("scripts.research.capture_gpb_history_partitions.parse_list",
                        lambda raw, url: [{"deadline_raw": original}])
    r = archive_rows(b"", "test")[0]
    assert r["deadline_raw"] == "12 января 2024, 15:00 Z"
    assert r["auction_date_raw"] == "26 января 2024, 07:00 Z"
    assert r["deadline_raw_original"] == original


def test_filter_day_is_moscow_calendar_not_utc():
    from scripts.research.capture_gpb_history_partitions import deadline_calendar_date

    assert str(deadline_calendar_date("31 января 2024, 20:59 Z")) == "2024-01-31"
    assert str(deadline_calendar_date("31 января 2024, 21:00 Z")) == "2024-02-01"
