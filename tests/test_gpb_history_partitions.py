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
