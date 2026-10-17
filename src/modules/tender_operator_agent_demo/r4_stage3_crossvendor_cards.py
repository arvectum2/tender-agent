"""Source-only 44-FZ identity discovery for two immutable vendor HTML feeds.

Does not read technical specifications, model answers, legal meaning, or
outcomes. Production source verification requires official EIS getDocsIP.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from lxml import html

SYNAPS = "https://synapsenet.ru/search/populyarnie-zaprosi/razrabotka-programmnogo-obespecheniya"
MOS = "https://mos-tenders.ru/aukcioni-goszakupki-konkursi/tendery-programmnogo-obespecheniya"
_NOTICE = re.compile(r"[0-9]{19}\Z")
_MOS_PATH = re.compile(
    r"^/zakupki-v-tenderah-po-44-fz/goszakupka-[0-9]+-([0-9]{19})-(?:[a-zA-Z0-9-]+)$",
)


def parse_stage3_cards(source_url: str, original_html: bytes) -> list[dict]:
    """Capture physical card rank, attached law and EIS-number candidate only."""
    if source_url not in {SYNAPS, MOS}:
        raise ValueError("Unregistered stage3 source")
    if not isinstance(original_html, bytes) or not 100 <= len(original_html) <= 8_000_000:
        raise ValueError("Missing or unbounded source HTML")
    document = html.fromstring(original_html)
    cards = (
        document.xpath(
            '//div[contains(concat(" ",normalize-space(@class)," ")," sp-tender-block ")]'
        )
        if source_url == SYNAPS
        else document.xpath(
            '//table[contains(concat(" ",normalize-space(@class)," ")," theme_header ")]/div'
        )
    )
    if not 1 <= len(cards) <= 400:
        raise ValueError("Unknown original tender result-card layout")
    rows = []
    for rank, card in enumerate(cards, 1):
        if source_url == SYNAPS:
            text = " ".join(card.text_content().split())
            anchors = card.xpath('.//a[@href]')
            notice_links = []
            for node in anchors:
                uri = urlsplit(node.get("href", ""))
                if uri.path.startswith("/zakupki/fz44/"):
                    if uri.netloc and uri.hostname != "synapsenet.ru":
                        raise ValueError("Spoofed external 44-ФЗ procurement identity")
                    match = re.match(r"^/zakupki/fz44/([0-9]{19})(?:%23|--|/|$)", uri.path)
                    if match:
                        notice_links.append(match.group(1))
            if "44-ФЗ" in text:
                if "223-ФЗ" in text or len(set(notice_links)) != 1:
                    raise ValueError("Ambiguous 44-ФЗ label and notice-number card")
                number = notice_links[0]
                law = "44-ФЗ"
            else:
                if notice_links:
                    raise ValueError("44-ФЗ identity linked to unlabeled source card")
                number, law = None, "OTHER"
        else:
            links = card.xpath('.//a[@href]')
            numbers = []
            for link in links:
                u = urlsplit(link.get("href", ""))
                if u.scheme != "https" or u.hostname != "mos-tenders.ru":
                    continue
                match = _MOS_PATH.fullmatch(u.path)
                if match:
                    numbers.append(match.group(1))
            if not numbers and not links:
                # A panel without a source-linked identity is unsupported;
                # even a visible notice number without a law-linked URL cannot
                # be silently promoted to an official EIS case.
                number, law = None, "UNVERIFIABLE"
            elif len(set(numbers)) != 1:
                raise ValueError("Mos-tenders original row has ambiguous/missing 44-ФЗ ID")
            else:
                number, law = numbers[0], "44-ФЗ"
        if number is not None and not _NOTICE.fullmatch(number):
            raise ValueError("Invalid EIS notice-number length")
        rows.append({"source_card_rank": rank, "law": law, "registry_number": number})
    return rows
