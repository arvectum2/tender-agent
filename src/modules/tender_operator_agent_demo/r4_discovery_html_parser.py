"""Strict source-only HTML procurement-card parser for pre-registered feeds.

Read only the visible law label and official notice number attached to EACH
source card. Never synthesize registry numbers or determine legal relevance.
Unexpected source-layout changes fail closed rather than silently filtering.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from lxml import html

NUMBER = re.compile(r"[0-9]{19}\Z")
_CARD_XPATH = (
    '//article[contains(concat(" ",normalize-space(@class)," ")," tender-card ")]'
)
_TAG_XPATH = (
    './/*[contains(concat(" ",normalize-space(@class)," ")," tag ")]'
)


def parse_source_cards(raw_html: bytes) -> list[dict]:
    if not isinstance(raw_html, bytes) or not 100 <= len(raw_html) <= 5_000_000:
        raise ValueError("HTML original is not a bounded source document")
    document = html.fromstring(raw_html.decode("utf-8", errors="strict"))
    cards = document.xpath(_CARD_XPATH)
    if not 1 <= len(cards) <= 500:
        raise ValueError("Unknown tender-card layout or unbounded source results")
    results: list[dict] = []
    for i, card in enumerate(cards, 1):
        labels = [
            " ".join(x.text_content().split())
            for x in card.xpath(_TAG_XPATH)
        ]
        laws = [label for label in labels if label in {"44-ФЗ", "223-ФЗ"}]
        if len(laws) != 1:
            raise ValueError("Visible tender-card law is missing or ambiguous")
        law = laws[0]
        anchors = card.xpath(".//h3/a[@href]")
        if len(anchors) != 1:
            raise ValueError("Tender-card identity anchor missing or ambiguous")
        link = anchors[0].get("href") or ""
        number = None
        if law == "44-ФЗ":
            url = urlsplit(link)
            query = parse_qs(url.query)
            nums = query.get("regNumber") or []
            if (
                url.scheme != "https"
                or url.netloc != "zakupki.gov.ru"
                or not url.path.startswith("/epz/order/notice/")
                or len(nums) != 1
                or NUMBER.fullmatch(nums[0]) is None
            ):
                raise ValueError("44-ФЗ card does not link to official 19-digit EIS notice")
            number = nums[0]
        results.append({
            "visible_rank": i,
            "registry_number": number,
            "law": law,
        })
    ids = [row["registry_number"] for row in results if row["registry_number"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate 44-ФЗ cards within a single page")
    return results
