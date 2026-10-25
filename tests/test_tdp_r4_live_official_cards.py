"""Offline official-card validation; no external EIS traffic in unit/CI tests."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.acceptance.check_r4_live_eis_cards import (
    collect_live_snapshot,
    compare_deadline,
    fetch_official_card,
    official_url,
    parse_official_card,
    readable_report,
    valid_final_url,
)


def fixture_html(number: str, header: str = "Подача заявок", body: str | None = None) -> bytes:
    section = header if body is None else body
    return (
        "<html><body>Сведения закупки "
        f"<span>№ {number}</span>"
        f'<span class="cardMainInfo__state distancedText">{header}</span>'
        '<span class="section__title">Этап закупки</span>'
        f'<span class="section__info">{section}</span>'
        '<span class="section__title">Дата и время окончания срока подачи заявок</span>'
        '<span class="section__info">16.10.2026 09:00 '
        "<span class='timeZoneName'>(МСК+4)</span></span></section>"
        + "<p>Официальная карточка ЕИС</p>" * 30
        + "</body></html>"
    ).encode("utf8")


def test_official_card_identity_stage_and_local_timezone():
    n = "0151600003226000011"
    state, end = parse_official_card(fixture_html(n), n)
    assert state == "Подача заявок"
    assert end == "16.10.2026 09:00 (МСК+4)"
    assert compare_deadline(end, "2026-10-16T09:00:00+07:00") == "MATCH"
    assert compare_deadline(end, "2026-10-15T09:00:00+07:00") == "DIFF_REQUIRES_REVIEW"
    assert compare_deadline("", "2026-10-16T09:00:00+07:00") == "UNKNOWN"


def test_official_card_fails_closed_on_wrong_id_and_conflict():
    n = "0151600003226000011"
    with pytest.raises(ValueError, match="identity"):
        parse_official_card(fixture_html(n), "0372200172326000015")
    with pytest.raises(ValueError, match="inconsistent"):
        parse_official_card(fixture_html(n, body="Определение поставщика завершено"), n)
    with pytest.raises(ValueError, match="length"):
        parse_official_card(b"404 Not Found", n)


def test_official_url_and_redirect_boundaries():
    n = "0348100024426000039"
    url = official_url(n, "COMPETITIVE_OPEN_ELECTRONIC_COMPETITION")
    assert "/ok20/" in url
    assert valid_final_url(url, url)
    assert not valid_final_url(url.replace("https:", "http:"), url)
    assert not valid_final_url(url.replace(n, "0372200172326000015"), url)
    assert not valid_final_url(url.replace("zakupki.gov.ru", "example.com"), url)
    with pytest.raises(ValueError):
        official_url("bad-id", "COMPETITIVE_ELECTRONIC_AUCTION")


def test_flaky_404_retry_is_not_mistaken_for_cancelled(monkeypatch, tmp_path: Path):
    n = "0372200172326000015"
    url = official_url(n, "COMPETITIVE_ELECTRONIC_QUOTATIONS")
    calls = []

    def http(args, **kwargs):
        calls.append(args)
        out = Path(args[args.index("--output") + 1])
        if len(calls) == 1:
            out.write_text("<html>404</html>")
            return subprocess.CompletedProcess(args, 0, stdout=f"404\t0\t{url}")
        out.write_bytes(fixture_html(n))
        return subprocess.CompletedProcess(args, 0, stdout=f"200\t0\t{url}")

    monkeypatch.setattr("subprocess.run", http)
    monkeypatch.setattr("time.sleep", lambda value: None)
    target = tmp_path / "official.html"
    result = fetch_official_card(url, target)
    assert result == {"ok": True, "attempts": 2}
    assert len(calls) == 2
    assert parse_official_card(target.read_bytes(), n)[0] == "Подача заявок"


def test_twenty_http_failures_remain_unknown_not_legal_status(tmp_path: Path):
    notices = [{"registry_number": f"{i:019d}", "method": "COMPETITIVE_ELECTRONIC_AUCTION",
                "archived_submission_end": "2026-10-14T10:00:00+03:00"}
               for i in range(1, 21)]
    audit = {"competitive_notices": notices,
             "selected_original_notice_attachment_coverage": {"source_shas_attested": 96}}
    prior = {"cases": [
        {"reg_number": v["registry_number"],
         "request_url_path": "/epz/order/notice/ea20/view/common-info.html",
         "official_stage": "Подача заявок"}
        for v in notices
    ]}

    def offline_404(url, path):
        assert url.startswith("https://zakupki.gov.ru/")
        return {"ok": False, "attempts": 3, "failure": "HTTP_404"}

    result = collect_live_snapshot(audit, prior, tmp_path, fetcher=offline_404)
    assert result["official_card_attested"] == 0
    assert result["unverified_or_unavailable"] == 20
    assert result["live_xml_version_attested"] == 0 and result["human_legal_signed"] == 0
    assert all(v["source_status"] == "UNKNOWN" and not v["bid_ready"] for v in result["cases"])
    assert "Не подтверждены: **20**" in readable_report(result)


def test_private_archived_snapshot_parser_when_mounted():
    import os

    root = os.getenv("TA_PRIVATE_R4_SOURCE_ROOT")
    if not root:
        pytest.skip("Original public EIS HTML snapshot only mounted on Mac mini")
    prior_dir = Path(root) / "ai-expert-20261012" / "live-eis-cards-20261012"
    receipt = json.loads((prior_dir / "official-live-20-curl-receipt.json").read_text())
    assert len(receipt["cases"]) == 20
    for row in receipt["cases"]:
        number = row["reg_number"]
        source = prior_dir / f"{number}-official-curl.html"
        stage, deadline = parse_official_card(source.read_bytes(), number)
        assert stage == row["official_stage"]
        assert deadline == row["official_deadline_text"]
