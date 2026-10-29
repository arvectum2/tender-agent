"""Client report is read-only, deduplicated, escaped, evidence-labeled."""

from __future__ import annotations

import re

import pytest

from scripts.market_intelligence.render_pq_client_report import (
    group,
    render,
    safe_url,
    validate,
)


def _row(cid="223fz:32616435269:lot1", *, value="<img src=x onerror=alert(1)>"):
    return {
        "id": cid,
        "review": "unreviewed",
        "data": {
            "canonical_id": cid,
            "customer": {"name": value},
            "family": "hybrid_reactive_power_source",
            "scope": "supply",
            "description": "МПУ 10 кВ + БСК 110 кВ",
            "nmck_rub": "452016000.01",
            "publication_date": "2026-10-05",
            "status": "public_notice_original_award_unverified",
            "evidence": [
                {
                    "url": "https://zakupki.gov.ru/epz/order/notice/notice223/documents.html?purchaseNoticeNumber=32616435269"
                },
                {"url": "javascript:alert(1)"},
            ],
        },
    }


def test_report_escapes_untrusted_values_and_refuses_unsafe_links():
    data = render([_row()], "2026-10-29")
    assert "452 016 000,01 ₽" in data
    assert "2026-10-29" in data
    assert "&lt;img src=x onerror=alert(1)&gt;" in data
    assert "<img src=x onerror=alert(1)>" not in data
    assert 'href="javascript:' not in data
    assert "не установлены" in data
    assert "БСК 110 кВ" in data
    assert data.count('data-year="2026"') == 1
    assert "Показано 1 из 1" in data


def test_canonical_id_duplication_fails_closed():
    row = _row()
    with pytest.raises(ValueError, match="duplicate"):
        validate([row, row])


def test_mismatched_id_fails_closed():
    row = _row()
    row["data"]["canonical_id"] = "223fz:00000000000:lot1"
    with pytest.raises(ValueError, match="mismatch"):
        validate([row])


def test_scope_is_not_equal_signed_sale():
    row = _row()
    assert group(row) == "Поставка / запрос"
    rendered = render([row], "2026-10-29")
    assert "НМЦ не равна цене договора" in rendered
    assert "фактический оборот оборудования" in rendered


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "http://zakupki.gov.ru/",
        "https://malicious.test/phishing",
        "https://evil@zakupki.gov.ru/a",
    ],
)
def test_client_html_refuses_non_public_sources(url):
    assert safe_url(url) is None


def test_existing_client_document_contains_full_live_corpus():
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "docs/market_intelligence/POWER_QUALITY_CLIENT_PREVIEW_20261024.html"
    )
    report = path.read_text(encoding="utf8")
    assert "2026-10-29" in report
    ids = re.findall(
        r'<tr data-year="[^"]+" data-group="[^"]+" data-search="[^"]*"><td>([^<]+)</td>',
        report,
    )
    assert len(ids) >= 113
    assert len(ids) == len(set(ids))
    assert "НМЦ не равна цене договора" in report
    assert "Показано" in report
