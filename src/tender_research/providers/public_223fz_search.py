from __future__ import annotations

import html
import re
from datetime import date
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode, urljoin

from src.tender_research.providers.public_44fz_search import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    Public44FzSearchProvider,
    PublicDocumentLink,
    PublicSearchStatus,
    PublicTenderDetail,
    PublicTenderSearchItem,
    PublicTenderSearchPage,
    _parse_public_datetime,
)

EIS_223FZ_SEARCH_PATH = "/epz/order/extendedsearch/results.html"


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()
    return cleaned or None


def _extract_label_value_pairs(fragment: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    pattern = re.compile(
        r'<[^>]*class="[^"]*(?:registry-entry__body-title|data-block__title)[^"]*"[^>]*>(.*?)</[^>]+>\s*'
        r'<[^>]*class="[^"]*(?:registry-entry__body-value|data-block__value)[^"]*"[^>]*>(.*?)</[^>]+>',
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(fragment):
        label = (_clean_text(match.group(1)) or "").lower().rstrip(":")
        value = _clean_text(match.group(2))
        if label and value:
            pairs[label] = value
    return pairs


def _first_pair(pairs: dict[str, str], labels: tuple[str, ...]) -> str | None:
    for key, value in pairs.items():
        if any(label in key for label in labels):
            return value
    return None


def _extract_number(fragment: str) -> str | None:
    patterns = (
        r"(?:реестров(?:ый|ого)\s+номер|номер\s+(?:закупки|извещения))[^0-9]{0,80}(\d{10,30})",
        r"regNumber=(\d{10,30})",
        r"purchaseNoticeInfoId=[^\"'&]*?(\d{10,30})",
    )
    for pattern in patterns:
        match = re.search(pattern, fragment, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1)
    return None


def _extract_card_url(fragment: str, registry_number: str | None) -> str | None:
    for match in re.finditer(r'href=["\']([^"\']+)["\']', fragment, re.IGNORECASE):
        href = html.unescape(match.group(1))
        lowered = href.lower()
        if "purchase" in lowered or "notice" in lowered or "regnumber=" in lowered:
            return urljoin("https://zakupki.gov.ru", href)
    if registry_number:
        return None
    return None


def _split_entries(html_str: str) -> list[str]:
    matches = list(re.finditer(r'<div[^>]*class="[^"]*\bregistry-entry\b[^"]*"[^>]*>', html_str, re.IGNORECASE))
    if not matches:
        return [html_str]
    return [
        html_str[m.start() : matches[index + 1].start() if index + 1 < len(matches) else len(html_str)]
        for index, m in enumerate(matches)
    ]


def parse_223fz_search_results(html_str: str) -> list[PublicTenderSearchItem]:
    items: list[PublicTenderSearchItem] = []
    for fragment in _split_entries(html_str):
        registry_number = _extract_number(fragment)
        if not registry_number:
            continue
        pairs = _extract_label_value_pairs(fragment)
        title = _first_pair(pairs, ("предмет договора", "объект закупки", "наименование закупки"))
        customer = _first_pair(pairs, ("заказчик",))
        publication = _first_pair(pairs, ("дата размещения", "дата публикации"))
        deadline = _first_pair(pairs, ("окончание подачи", "дата окончания подачи"))
        price_text = _first_pair(pairs, ("начальная цена", "нмц", "цена договора"))
        amount: Decimal | None = None
        if price_text:
            normalized = re.sub(r"[^0-9,.]", "", price_text).replace(" ", "").replace(",", ".")
            try:
                amount = Decimal(normalized)
            except Exception:
                amount = None
        card_url = _extract_card_url(fragment, registry_number)
        items.append(
            PublicTenderSearchItem(
                registry_number=registry_number,
                purchase_number=registry_number,
                title=title,
                customer_name=customer,
                publication_date=_parse_public_datetime(publication),
                application_deadline=_parse_public_datetime(deadline),
                nmck_amount=amount,
                law_type="223fz",
                card_url=card_url,
                source_url=card_url,
                raw={"source_regime": "223fz", "parser": "public_223fz_v1", "role_status": "explicit" if customer else "unknown"},
            )
        )
    return items


def parse_223fz_detail(html_str: str, source_url: str, registry_number: str | None = None) -> PublicTenderDetail:
    pairs = _extract_label_value_pairs(html_str)
    resolved_registry = registry_number or _extract_number(html_str)
    customer = _first_pair(pairs, ("заказчик",))
    title = _first_pair(pairs, ("предмет договора", "объект закупки", "наименование закупки"))
    publication = _first_pair(pairs, ("дата размещения", "дата публикации"))
    deadline = _first_pair(pairs, ("окончание подачи", "дата окончания подачи"))
    links: list[PublicDocumentLink] = []
    seen: set[str] = set()
    for match in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html_str, re.IGNORECASE | re.DOTALL):
        href = html.unescape(match.group(1))
        label = _clean_text(match.group(2))
        lowered = href.lower()
        if not any(marker in lowered for marker in ("download", "file", "document", "attachment")):
            continue
        url = urljoin(source_url, href)
        if url in seen:
            continue
        seen.add(url)
        links.append(PublicDocumentLink(title=label, file_name=label, url=url, raw={"source_regime": "223fz"}))
    review_reasons: list[str] = []
    if not customer:
        review_reasons.append("customer_role_not_explicit")
    revision_markers = re.findall(r"(?:редакци[яи]|верси[яи])\s*№?\s*(\d+)", _clean_text(html_str) or "", re.IGNORECASE)
    if len(set(revision_markers)) > 1:
        review_reasons.append("revision_state_ambiguous")
    detail = PublicTenderDetail(
        registry_number=resolved_registry,
        title=title,
        customer_name=customer,
        publication_date=_parse_public_datetime(publication),
        application_deadline=_parse_public_datetime(deadline),
        law_type="223fz",
        card_url=source_url,
        source_url=source_url,
        document_links=links,
        common_info_html=html_str,
        network_status=PublicSearchStatus.SUCCESS,
        raw={
            "source_regime": "223fz",
            "parser": "public_223fz_v1",
            "customer_role_status": "explicit" if customer else "unknown",
            "revision_status": "ambiguous" if "revision_state_ambiguous" in review_reasons else "unknown",
            "requires_review": bool(review_reasons),
            "review_reasons": review_reasons,
        },
    )
    if review_reasons:
        detail.error_message = "; ".join(review_reasons)
    return detail


class Public223FzSearchProvider(Public44FzSearchProvider):
    """Read-only 223-FZ adapter reusing transport only, never 44-FZ parsing/detail routes."""

    def search(
        self,
        query: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        law_type: str = "223fz",
        status_filter: str | None = None,
    ) -> PublicTenderSearchPage:
        url = self._build_223fz_url(query, date_from, date_to, page, page_size)
        fetched = self._fetch_page(url)
        if fetched.get("status") != PublicSearchStatus.SUCCESS or fetched.get("html") is None:
            return PublicTenderSearchPage(page=page, page_size=page_size, source_url=url, status=fetched.get("status") or PublicSearchStatus.NETWORK_ERROR, error=fetched.get("error"))
        items = parse_223fz_search_results(fetched["html"])
        for item in items:
            item.source_url = url
        return PublicTenderSearchPage(items=items, page=page, page_size=page_size, has_next=len(items) >= page_size, source_url=url, status=PublicSearchStatus.SUCCESS if items else PublicSearchStatus.EMPTY)

    def _build_223fz_url(self, query: str | None, date_from: date | None, date_to: date | None, page: int, page_size: int) -> str:
        params: dict[str, str] = {"fz223": "on", "pageNumber": str(page), "recordsPerPage": str(min(max(page_size, 1), MAX_PAGE_SIZE))}
        if date_from:
            params["publishDateFrom"] = date_from.strftime("%d.%m.%Y")
        if date_to:
            params["publishDateTo"] = date_to.strftime("%d.%m.%Y")
        if query:
            params["searchString"] = query
        return f"https://zakupki.gov.ru{EIS_223FZ_SEARCH_PATH}?{urlencode(params)}"

    def fetch_detail(
        self,
        item_or_url: PublicTenderSearchItem | str | None = None,
        registry_number: str | None = None,
        card_url: str | None = None,
    ) -> PublicTenderDetail:
        item = item_or_url if isinstance(item_or_url, PublicTenderSearchItem) else None
        resolved_url = card_url or (item_or_url if isinstance(item_or_url, str) else None) or (item.card_url if item else None)
        resolved_registry = registry_number or (item.registry_number if item else None)
        if not resolved_url:
            return PublicTenderDetail(registry_number=resolved_registry, law_type="223fz", network_status=PublicSearchStatus.UNSUPPORTED_LAYOUT, error_message="223-FZ detail URL unavailable; no 44-FZ fallback permitted", raw={"source_regime": "223fz", "requires_review": True, "review_reasons": ["detail_url_unavailable"]})
        fetched = self._fetch_page(resolved_url)
        if fetched.get("status") != PublicSearchStatus.SUCCESS or fetched.get("html") is None:
            return PublicTenderDetail(registry_number=resolved_registry, law_type="223fz", card_url=resolved_url, source_url=resolved_url, network_status=fetched.get("status") or PublicSearchStatus.NETWORK_ERROR, error_message=fetched.get("error"), raw={"source_regime": "223fz", "requires_review": True})
        return parse_223fz_detail(fetched["html"], resolved_url, resolved_registry)
