from __future__ import annotations

import html
import logging
import os
import re
import ssl
import time
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from src.shared.network.http_client import create_urllib_context

logger = logging.getLogger(__name__)

EIS_44FZ_HOST = "zakupki.gov.ru"
EIS_44FZ_SEARCH_PATH = "/epz/order/extendedsearch/results.html"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_PAGE_SIZE = 30
MAX_PAGE_SIZE = 100
USER_AGENT = "Mozilla/5.0 (compatible; ArvectumTenderAgent/0.1; read-only)"

LAW_FLAGS = {
    "44fz": "fz44",
    "223fz": "fz223",
    "capital_repair": "ppRf615",
}


class PublicSearchStatus:
    SUCCESS = "success"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    BAD_GATEWAY = "bad_gateway"
    CAPTCHA = "captcha"
    PARSE_ERROR = "parse_error"
    EMPTY = "empty"
    NETWORK_ERROR = "network_error"
    PARSED = "parsed"
    MANUAL_OPEN_REQUIRED = "manual_open_required"
    UNSUPPORTED_LAYOUT = "unsupported_layout"
    EMPTY_RESULTS = "empty_results"
    CAPTCHA_OR_BLOCKED = "captcha_or_blocked"
    JS_HEAVY = "js_heavy"


@dataclass
class PublicTenderSearchItem:
    registry_number: str | None = None
    purchase_number: str | None = None
    title: str | None = None
    customer_name: str | None = None
    customer_inn: str | None = None
    customer_kpp: str | None = None
    publication_date: datetime | None = None
    application_deadline: datetime | None = None
    nmck_amount: Decimal | float | None = None
    law_type: str = "44fz"
    source_url: str | None = None
    card_url: str | None = None
    is_demo: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class PublicDocumentLink:
    title: str | None = None
    file_name: str | None = None
    url: str = ""
    content_type: str | None = None
    size_bytes: int | None = None
    size_text: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class PublicNoticeRevision:
    revision: int | None = None
    publication_timestamp: str | None = None
    state: str | None = None
    active: bool | None = None
    source_url: str | None = None
    title: str | None = None
    document_links: list[PublicDocumentLink] = field(default_factory=list)

    def provenance(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "publication_timestamp": self.publication_timestamp,
            "state": self.state,
            "active": self.active,
            "source_url": self.source_url,
            "title": self.title,
            "attachment_count": len(self.document_links),
        }


@dataclass
class PublicTenderDetail:
    registry_number: str | None = None
    title: str | None = None
    customer_name: str | None = None
    customer_inn: str | None = None
    customer_kpp: str | None = None
    publication_date: datetime | None = None
    application_deadline: datetime | None = None
    nmck_amount: Decimal | float | None = None
    law_type: str = "44fz"
    card_url: str | None = None
    source_url: str | None = None
    document_links: list[PublicDocumentLink] = field(default_factory=list)
    document_revisions: list[PublicNoticeRevision] = field(default_factory=list)
    active_revision: PublicNoticeRevision | None = None
    raw_html_path: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    network_status: str = PublicSearchStatus.SUCCESS
    error_message: str | None = None
    common_info_html: str | None = None
    documents_html: str | None = None


@dataclass
class PublicTenderSearchPage:
    items: list[PublicTenderSearchItem] = field(default_factory=list)
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    has_next: bool | None = None
    total: int | None = None
    source_url: str | None = None
    raw_html_path: str | None = None
    status: str = PublicSearchStatus.SUCCESS
    error: str | None = None


DEFAULT_NO_PROXY_DOMAINS = (
    "zakupki.gov.ru",
    ".zakupki.gov.ru",
    "int.zakupki.gov.ru",
    "int44.zakupki.gov.ru",
)
PUBLIC_SEARCH_NO_PROXY_DOMAINS = DEFAULT_NO_PROXY_DOMAINS


def _hostname_matches_no_proxy(hostname: str, no_proxy_domains: tuple[str, ...]) -> bool:
    hostname = hostname.lower().strip()
    for domain in no_proxy_domains:
        domain = domain.lower().strip()
        if not domain:
            continue
        if domain.startswith("."):
            if hostname.endswith(domain) or hostname == domain.lstrip("."):
                return True
        elif hostname == domain or hostname.endswith(f".{domain}"):
            return True
    return False


def _resolve_no_proxy_domains(config_domains: str | None, env_domains: str | None = None) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    default = ",".join(PUBLIC_SEARCH_NO_PROXY_DOMAINS)
    sources = [config_domains or default, env_domains or "", os.environ.get("NO_PROXY", ""), os.environ.get("no_proxy", "")]
    for raw in sources:
        for part in raw.split(","):
            part = part.strip()
            if part and part not in seen:
                seen.add(part)
                result.append(part)
    return tuple(result) if result else DEFAULT_NO_PROXY_DOMAINS


class Public44FzSearchProvider:
    def __init__(
        self,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        delay_seconds: float = 0.0,
        bypass_proxy: bool = True,
        no_proxy_domains: str | None = None,
    ):
        self._timeout = timeout_seconds
        self._delay = delay_seconds
        self._bypass_proxy = bypass_proxy
        self._no_proxy_domains = _resolve_no_proxy_domains(no_proxy_domains)

    def search(
        self,
        query: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        law_type: str = "44fz",
        status_filter: str | None = None,
    ) -> PublicTenderSearchPage:
        if page_size > MAX_PAGE_SIZE:
            page_size = MAX_PAGE_SIZE
        url = self._build_url(
            query=query,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
            law_type=law_type,
        )
        logger.info("Fetching EIS public search: %s", url)

        fetch_result = self._fetch_page(url)
        status = fetch_result.get("status")
        if status != PublicSearchStatus.SUCCESS or not fetch_result.get("html"):
            return PublicTenderSearchPage(
                page=page,
                page_size=page_size,
                source_url=url,
                status=status or PublicSearchStatus.NETWORK_ERROR,
                error=fetch_result.get("error"),
            )

        cards = parse_44fz_search_results(fetch_result["html"])
        items = [self._card_to_item(c, search_url=url) for c in cards]
        has_next = len(cards) >= page_size

        return PublicTenderSearchPage(
            items=items,
            page=page,
            page_size=page_size,
            has_next=has_next,
            source_url=url,
            status=PublicSearchStatus.SUCCESS if items else PublicSearchStatus.EMPTY,
        )

    def search_pages(
        self,
        query: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        max_pages: int = 3,
        page_size: int = DEFAULT_PAGE_SIZE,
        law_type: str = "44fz",
    ) -> list[PublicTenderSearchPage]:
        pages: list[PublicTenderSearchPage] = []
        for page_num in range(1, max_pages + 1):
            if self._delay > 0 and page_num > 1:
                time.sleep(self._delay)
            result = self.search(
                query=query,
                date_from=date_from,
                date_to=date_to,
                page=page_num,
                page_size=page_size,
                law_type=law_type,
            )
            pages.append(result)
            if result.status != PublicSearchStatus.SUCCESS:
                break
            if not result.has_next:
                break
        return pages

    def _build_url(
        self,
        query: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        law_type: str = "44fz",
    ) -> str:
        normalized_law = _normalize_law(law_type)
        flag = LAW_FLAGS.get(normalized_law, "fz44")
        if date_from is None:
            date_from = date.today() - timedelta(days=3)
        if date_to is None:
            date_to = date.today()
        params = {
            "morphology": "on",
            "sortDirection": "false",
            flag: "on",
            "publishDateFrom": date_from.strftime("%d.%m.%Y"),
            "publishDateTo": date_to.strftime("%d.%m.%Y"),
            "pageNumber": str(page),
            "recordsPerPage": str(min(max(page_size, 1), MAX_PAGE_SIZE)),
        }
        if query:
            params["searchString"] = query
        return f"https://{EIS_44FZ_HOST}{EIS_44FZ_SEARCH_PATH}?{urlencode(params)}"

    def _fetch_page(self, url: str) -> dict[str, Any]:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if not hostname.endswith(EIS_44FZ_HOST):
            return {"status": PublicSearchStatus.NETWORK_ERROR, "html": None, "error": f"Host {hostname} is not allowed"}
        if parsed.scheme not in {"http", "https"}:
            return {"status": PublicSearchStatus.NETWORK_ERROR, "html": None, "error": "Only http/https URLs"}

        request = Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
        ssl_ctx, policy_bypass = create_urllib_context(url)
        should_bypass = policy_bypass or (self._bypass_proxy and _hostname_matches_no_proxy(hostname, self._no_proxy_domains))
        if should_bypass:
            opener = build_opener(HTTPSHandler(context=ssl_ctx), ProxyHandler({}))
        else:
            opener = build_opener(HTTPSHandler(context=ssl_ctx))

        try:
            with opener.open(request, timeout=self._timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    return {"status": PublicSearchStatus.NETWORK_ERROR, "html": None, "error": "Response too large"}
                html_content = raw.decode("utf-8", errors="replace")
        except HTTPError as exc:
            code = exc.code
            if code in (502, 503):
                return {"status": PublicSearchStatus.BAD_GATEWAY, "html": None, "error": f"HTTP {code}"}
            if code == 403:
                return {"status": PublicSearchStatus.BLOCKED, "html": None, "error": f"HTTP {code} Forbidden"}
            return {"status": PublicSearchStatus.NETWORK_ERROR, "html": None, "error": f"HTTP {code}"}
        except URLError as exc:
            reason = str(exc.reason) if hasattr(exc, "reason") else str(exc)
            reason_lower = reason.lower()
            if "certificate_verify_failed" in reason_lower or "certificate verify failed" in reason_lower:
                return {"status": PublicSearchStatus.BLOCKED, "html": None, "error": "TLS verification failed"}
            if "timed out" in reason_lower or "timeout" in reason_lower:
                return {"status": PublicSearchStatus.TIMEOUT, "html": None, "error": reason}
            if "connection reset" in reason_lower:
                return {"status": PublicSearchStatus.BLOCKED, "html": None, "error": reason}
            return {"status": PublicSearchStatus.NETWORK_ERROR, "html": None, "error": reason}
        except ssl.SSLError:
            return {"status": PublicSearchStatus.BLOCKED, "html": None, "error": "TLS verification failed"}
        except Exception as exc:
            return {"status": PublicSearchStatus.NETWORK_ERROR, "html": None, "error": str(exc)}

        classification = _classify_search_html(html_content)
        if classification != "parsed":
            if classification == "captcha_or_blocked":
                return {"status": PublicSearchStatus.BLOCKED, "html": None, "error": "Captcha or blocking detected"}
            if classification == "empty_results":
                return {"status": PublicSearchStatus.SUCCESS, "html": html_content, "error": None}
            if classification == "unsupported_layout":
                return {"status": PublicSearchStatus.PARSE_ERROR, "html": None, "error": f"Unsupported layout: {classification}"}
            return {"status": PublicSearchStatus.PARSE_ERROR, "html": None, "error": f"Unclassified: {classification}"}

        return {"status": PublicSearchStatus.SUCCESS, "html": html_content, "error": None}

    def fetch_detail(
        self,
        item_or_url: PublicTenderSearchItem | str | None = None,
        registry_number: str | None = None,
        card_url: str | None = None,
    ) -> PublicTenderDetail:
        item = item_or_url if isinstance(item_or_url, PublicTenderSearchItem) else None
        if isinstance(item_or_url, str) and not card_url:
            card_url = item_or_url
        resolved_registry = registry_number or (item.registry_number if item else None)
        resolved_card_url = card_url or (item.card_url if item else None) or (item.source_url if item else None)
        if not resolved_card_url and resolved_registry:
            resolved_card_url = _build_default_card_url(resolved_registry)

        detail = PublicTenderDetail(
            registry_number=resolved_registry,
            card_url=resolved_card_url,
            source_url=(item.source_url if item else None) or resolved_card_url,
            law_type=(item.law_type if item else "44fz") or "44fz",
            title=item.title if item else None,
            customer_name=item.customer_name if item else None,
            customer_inn=item.customer_inn if item else None,
            customer_kpp=item.customer_kpp if item else None,
            publication_date=item.publication_date if item else None,
            application_deadline=item.application_deadline if item else None,
            nmck_amount=item.nmck_amount if item else None,
            network_status=PublicSearchStatus.SUCCESS,
            raw={"search_item": _search_item_to_json_dict(item) if item else None},
        )
        if not resolved_card_url:
            detail.network_status = PublicSearchStatus.NETWORK_ERROR
            detail.error_message = "No card_url or registry_number available for detail fetch"
            return detail

        common_result = self._fetch_page(resolved_card_url)
        common_status = common_result.get("status") or PublicSearchStatus.NETWORK_ERROR
        detail.network_status = common_status
        if common_status != PublicSearchStatus.SUCCESS or not common_result.get("html"):
            detail.error_message = common_result.get("error")
            return detail

        common_html = common_result["html"]
        detail.common_info_html = common_html
        detail.raw["common_info_url"] = resolved_card_url
        _merge_detail_metadata(detail, _parse_detail_metadata(common_html, resolved_card_url))

        documents_url = _build_documents_url(resolved_card_url, detail.registry_number)
        detail.raw["documents_url"] = documents_url
        if documents_url:
            docs_result = self._fetch_page(documents_url)
            detail.raw["documents_fetch_status"] = docs_result.get("status")
            if docs_result.get("status") == PublicSearchStatus.SUCCESS and docs_result.get("html"):
                documents_html = docs_result["html"]
                detail.documents_html = documents_html
                links, revisions, selection = _select_current_revision_document_links(
                    documents_html, documents_url
                )
                detail.document_links = links
                detail.document_revisions = revisions
                detail.active_revision = next(
                    (item for item in revisions if item.active is True),
                    None,
                ) if selection.get("status") == "active_revision_selected" else None
                detail.raw["document_revision_selection"] = selection
                detail.raw["document_revisions"] = [item.provenance() for item in revisions]
                if selection.get("requires_review"):
                    detail.error_message = str(selection.get("reason") or "EIS revision binding requires review")
            else:
                detail.raw["documents_fetch_error"] = docs_result.get("error")

        return detail

    @staticmethod
    def _card_to_item(card: dict[str, Any], search_url: str | None = None) -> PublicTenderSearchItem:
        nmck = None
        raw_price = card.get("initial_price")
        if raw_price is not None:
            try:
                nmck = float(raw_price)
            except (ValueError, TypeError):
                nmck = None
        card_url = card.get("card_url") or card.get("source_url")
        return PublicTenderSearchItem(
            registry_number=card.get("reestr_number"),
            purchase_number=card.get("notice_number"),
            title=card.get("title"),
            customer_name=card.get("customer_name"),
            customer_inn=card.get("customer_inn"),
            customer_kpp=card.get("customer_kpp"),
            publication_date=_parse_public_datetime(card.get("publication_date")),
            application_deadline=_parse_public_datetime(card.get("deadline")),
            nmck_amount=nmck,
            law_type=card.get("law") or "44fz",
            source_url=search_url or card_url,
            card_url=card_url,
            raw={**card, "search_url": search_url},
        )

    @staticmethod
    def extract_registry_numbers(pages: list[PublicTenderSearchPage]) -> list[str]:
        seen: set[str] = set()
        numbers: list[str] = []
        for page_obj in pages:
            for item in page_obj.items:
                if item.registry_number and item.registry_number not in seen:
                    seen.add(item.registry_number)
                    numbers.append(item.registry_number)
        return numbers


def _normalize_law(law: str | None) -> str:
    normalized = (law or "44fz").strip().lower().replace("-", "").replace("_", "")
    if normalized in {"44фз", "44fz", "44"}:
        return "44fz"
    if normalized in {"223фз", "223fz", "223"}:
        return "223fz"
    if normalized in {"капремонт", "капрем", "capitalrepair", "615", "pp615", "pprf615", "615pp"}:
        return "capital_repair"
    return "44fz"


def _classify_search_html(html_content: str) -> str:
    if not html_content or not html_content.strip():
        return "empty_results"
    lower = html_content.lower()
    captcha_markers = ["captcha", "turnstile", "recaptcha"]
    if any(marker in lower for marker in captcha_markers):
        return "captcha_or_blocked"
    js_heavy_markers = [
        "your browser does not support javascript",
        "ваш браузер не поддерживает javascript",
        "включите javascript",
        "this site requires javascript",
    ]
    if any(marker in lower for marker in js_heavy_markers):
        return "captcha_or_blocked"
    entry_markers = [
        "registry-entry__header-mid__number",
        "registry-entry__body-value",
        "notice__header",
        "search-results__item",
    ]
    if any(marker in lower for marker in entry_markers):
        return "parsed"
    search_markers = [
        "результаты поиска",
        "найдено",
        "закупка",
        "номер извещения",
        "registry-entry",
    ]
    if any(marker in lower for marker in search_markers):
        return "parsed"
    if "<html" in lower and "</html>" in lower:
        return "unsupported_layout"
    return "unsupported_layout"


# ── HTML parsing (from public_44fz_parser.py) ──

PROCEDURE_CODE_LABELS = {
    "ea": "Электронный аукцион",
    "zk": "Запрос котировок",
    "ok": "Открытый конкурс",
    "eo": "Электронный конкурс",
    "ep": "Закупка у единственного поставщика",
    "zp": "Запрос предложений",
}


def parse_44fz_search_results(html_str: str) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    entries = _split_registry_entries(html_str)
    for entry_html in entries:
        card = _parse_single_entry(entry_html, html_str)
        if card:
            cards.append(card)
    if not cards:
        cards = _fallback_extract_by_number_patterns(html_str)
    return cards


def _split_registry_entries(html_str: str) -> list[str]:
    patterns = [
        r'<div[^>]*class="[^"]*\bregistry-entry\b[^"]*"[^>]*>',
        r'<div[^>]*class="[^"]*\bnotice__item\b[^"]*"[^>]*>',
        r'<div[^>]*class="[^"]*\bsearch-results__item\b[^"]*"[^>]*>',
    ]
    for pattern in patterns:
        matches = list(re.finditer(pattern, html_str, re.IGNORECASE))
        if len(matches) >= 1:
            fragments: list[str] = []
            for i, match in enumerate(matches):
                start = match.start()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(html_str)
                fragments.append(html_str[start:end])
            return fragments
    return []


def _parse_single_entry(entry_html: str, full_html: str) -> dict[str, Any] | None:
    pairs: dict[str, str] = _extract_registry_body_pairs(entry_html)
    for title_class, value_class in (
        ("data-block__title", "data-block__value"),
        ("price-block__title", "price-block__value"),
    ):
        pairs.update(_extract_label_value_pairs(entry_html, title_class, value_class))

    title = _first_matching_value(
        pairs,
        (
            "объект закупки",
            "наименование объекта закупки",
            "предмет контракта",
            "предмет договора",
        ),
    )
    if not title:
        title = _extract_between(entry_html, '<div class="registry-entry__header-mid__title">', "</div>")
    if title:
        title = _strip_html(title)
    if not title:
        title = _extract_between(entry_html, "<h2", "</h2>")
        if title:
            title = _strip_html(title)
    if not title:
        title_match = re.search(
            r'<a[^>]*class="[^"]*registry-entry__header-mid__number[^"]*"[^>]*href="([^"]*)"[^>]*>([^<]+)</a>',
            entry_html,
        )
        if title_match:
            title = _strip_html(title_match.group(2))
    if not title:
        title_match = re.search(r'"notice__header"[^>]*>\s*<span[^>]*>([^<]+)', entry_html)
        if title_match:
            title = _strip_html(title_match.group(1))
    if not title:
        return None

    notice_number = None
    num_link = re.search(
        r'class="[^"]*registry-entry__header-mid__number[^"]*"[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>.*?(\d{11,25})',
        entry_html,
        re.DOTALL,
    )
    if not num_link:
        num_link = re.search(
            r'href="([^"]*)"[^>]*class="[^"]*registry-entry__header-mid__number[^"]*"[^>]*>.*?(\d{11,25})',
            entry_html,
            re.DOTALL,
        )
    if num_link:
        notice_number = num_link.group(2).strip()
    if not notice_number:
        link_match = re.search(r'href="([^"]+)"[^>]*>\s*(\d{11,25})', entry_html)
        if link_match:
            notice_number = link_match.group(2)

    reestr_number = _extract_reestr_from_card(entry_html)

    # Search result cards may expose the authorized/placing organization rather
    # than the contracting customer. Only an explicitly customer-scoped label
    # is safe to project as ``customer_name``; placement/general organization
    # labels stay unclassified here and are resolved from common-info later.
    customer_name = _first_matching_value(
        pairs,
        (
            "заказчик",
            "наименование заказчика",
        ),
    )
    customer_inn = _first_matching_value(pairs, ("инн", "инн заказчика"))
    customer_kpp = _first_matching_value(pairs, ("кпп", "кпп заказчика"))
    if not customer_name:
        org_match = re.search(r'Заказчик[^:]*:\s*([^<]+)', entry_html, re.IGNORECASE)
        if org_match:
            customer_name = _strip_html(org_match.group(1))

    price_value = _first_matching_value(
        pairs,
        (
            "начальная цена",
            "начальная (максимальная) цена контракта",
            "максимальное значение цены контракта",
            "цена контракта",
        ),
    )
    initial_price = _extract_price(price_value)
    if initial_price is None:
        price_match = re.search(r'([\d\s\xa0,.]+(?:руб|₽|RUB))', entry_html, re.IGNORECASE)
    else:
        price_match = None
    if price_match:
        initial_price = _extract_price(price_match.group(1))

    publication_date = _extract_first_date(
        _first_matching_value(pairs, ("размещено", "дата размещения", "опубликовано"))
    )
    if not publication_date:
        pub_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", entry_html)
        if pub_match:
            publication_date = pub_match.group(1)

    deadline = _extract_first_date(
        _first_matching_value(pairs, ("окончание подачи заявок", "дата окончания срока подачи заявок", "срок подачи заявок"))
    )

    card_url = None
    href_match = re.search(r'href="(https://[^"]*(?:zakupki\.gov\.ru)[^"]*)"', entry_html)
    if href_match:
        card_url = href_match.group(1)
    if not card_url:
        href_match = re.search(r'href="([^"]*(?:view|common-info)[^"]*)"', entry_html)
        if href_match:
            card_url = urljoin("https://zakupki.gov.ru", href_match.group(1))

    procedure_status = _strip_html(
        _extract_between(entry_html, '<div class="registry-entry__header-mid__title text-normal">', "</div>")
        or _extract_between(entry_html, '<div class="registry-entry__header-mid__title">', "</div>")
    )
    procedure_type = _extract_procedure_type(card_url)

    return {
        "title": title,
        "notice_number": notice_number,
        "reestr_number": reestr_number or notice_number,
        "customer_name": customer_name,
        "customer_inn": customer_inn,
        "customer_kpp": customer_kpp,
        "initial_price": initial_price,
        "publication_date": publication_date,
        "deadline": deadline,
        "procedure_type": procedure_type,
        "status": procedure_status or None,
        "source_url": card_url,
        "card_url": card_url,
        "law": "44fz",
    }


def _extract_registry_body_pairs(entry_html: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    pattern = re.compile(
        r'<div[^>]*class="[^"]*\bregistry-entry__body-title\b[^"]*"[^>]*>(.*?)</div>\s*'
        r'<div[^>]*class="[^"]*\bregistry-entry__body-(?:value|href)\b[^"]*"[^>]*>(.*?)</div>',
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(entry_html):
        label = _strip_html(match.group(1)).strip(" :")
        value = _strip_html(match.group(2))
        if label and value and label.lower() not in pairs:
            pairs[label.lower()] = value
    return pairs


def _extract_label_value_pairs(entry_html: str, title_class: str, value_class: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    pattern = re.compile(
        rf'<div[^>]*class="[^"]*\b{re.escape(title_class)}\b[^"]*"[^>]*>(.*?)</div>\s*'
        rf'<div[^>]*class="[^"]*\b{re.escape(value_class)}\b[^"]*"[^>]*>(.*?)</div>',
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(entry_html):
        label = _strip_html(match.group(1)).strip(" :")
        value = _strip_html(match.group(2))
        if label and value and label.lower() not in pairs:
            pairs[label.lower()] = value
    return pairs


def _first_matching_value(pairs: dict[str, str], labels: tuple[str, ...]) -> str | None:
    for label in labels:
        value = pairs.get(label.lower())
        if value:
            return value
    return None


def _extract_between(html_str: str, prefix: str, suffix: str) -> str | None:
    start = html_str.find(prefix)
    if start == -1:
        return None
    start += len(prefix)
    end = html_str.find(suffix, start)
    if end == -1:
        return None
    return html_str[start:end].strip()


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"</?span[^>]*>", "", value, flags=re.IGNORECASE)
    cleaned = re.sub(r"<br\\s*/?>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned).replace("&nbsp;", " ").replace("\xa0", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _extract_price(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = text.replace("\xa0", " ").replace(" ", "").replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _extract_reestr_from_card(html_str: str) -> str | None:
    reestr = _extract_reestr_from_text(html_str)
    if reestr:
        return reestr
    href_match = re.search(r'href="([^"]*/(\d{11,25})[^"]*)"', html_str)
    if href_match:
        return href_match.group(2)
    href_match2 = re.search(r"/(\d{3,25})", html_str)
    if href_match2:
        return href_match2.group(1)
    return None


def _extract_reestr_from_text(text: str) -> str | None:
    match = re.search(r"(\d{11,25})", text)
    if match:
        return match.group(1)
    return None


def _extract_first_date(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(\d{2}\.\d{2}\.\d{4}(?:\s+\d{2}:\d{2})?)", value)
    if match:
        return match.group(1).strip()
    return _strip_html(value) or None


def _extract_procedure_type(source_url: str | None) -> str | None:
    if not source_url:
        return None
    match = re.search(r"/notice/([a-z]{2})\d+/view", source_url, re.IGNORECASE)
    if not match:
        return None
    return PROCEDURE_CODE_LABELS.get(match.group(1).lower())


def _fallback_extract_by_number_patterns(html_str: str) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    number_pattern = re.compile(r"(\d{11,25})")
    links = re.finditer(r'<a[^>]*href="([^"]*)"[^>]*>', html_str)
    seen_numbers: set[str] = set()
    for link in links:
        href = link.group(1)
        match = number_pattern.search(href)
        if match and match.group(1) not in seen_numbers:
            seen_numbers.add(match.group(1))
            card_url = href if href.startswith("http") else urljoin("https://zakupki.gov.ru", href)
            cards.append({
                "title": None,
                "notice_number": match.group(1),
                "reestr_number": match.group(1),
                "customer_name": None,
                "customer_inn": None,
                "customer_kpp": None,
                "initial_price": None,
                "publication_date": None,
                "deadline": None,
                "procedure_type": _extract_procedure_type(
                    card_url
                ),
                "status": None,
                "source_url": card_url,
                "card_url": card_url,
                "law": "44fz",
            })
    return cards


def _parse_public_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = _strip_html(value).replace("(МСК)", "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(cleaned, fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _build_default_card_url(registry_number: str) -> str:
    return f"https://{EIS_44FZ_HOST}/epz/order/notice/ea44/view/common-info.html?regNumber={registry_number}"


def _build_documents_url(card_url: str | None, registry_number: str | None) -> str | None:
    if card_url:
        if "documents.html" in card_url:
            return card_url
        if "common-info.html" in card_url:
            return card_url.replace("common-info.html", "documents.html")
        if re.search(r"/view(?:\.html)?", card_url):
            return re.sub(r"/view(?:\.html)?", "/view/documents.html", card_url, count=1)
    if registry_number:
        return f"https://{EIS_44FZ_HOST}/epz/order/notice/ea44/view/documents.html?regNumber={registry_number}"
    return None


def _merge_detail_metadata(detail: PublicTenderDetail, parsed: dict[str, Any]) -> None:
    for field_name in (
        "registry_number",
        "title",
        "customer_name",
        "customer_inn",
        "customer_kpp",
        "publication_date",
        "application_deadline",
        "nmck_amount",
        "law_type",
        "card_url",
    ):
        value = parsed.get(field_name)
        if value not in (None, "", []):
            setattr(detail, field_name, value)
    if parsed:
        detail.raw["detail_metadata"] = _json_safe_mapping(parsed)


def _extract_explicit_customer_name(html_str: str) -> str | None:
    """Extract only contracting-customer role evidence from EIS common-info.

    EIS distinguishes the organization that places a procurement from the
    contracting customer.  A centralized procurement body must therefore
    never be used as a customer fallback.  Prefer the strongest explicit
    customer surfaces and fail closed when customer requirement blocks name
    more than one distinct organization.
    """

    customer_name = _extract_card_main_info_value(html_str, "Заказчик")
    if customer_name:
        return customer_name

    customer_name = _extract_section_info_value(html_str, ("Заказчик",))
    if customer_name:
        return customer_name

    requirement_pattern = re.compile(
        r"Требования\s+заказчика(?:\s|&nbsp;)*(?:&laquo;|«)(.*?)(?:&raquo;|»)",
        re.IGNORECASE | re.DOTALL,
    )
    requirement_names = {
        value
        for match in requirement_pattern.finditer(html_str)
        if (value := _strip_html(match.group(1)))
    }
    if len(requirement_names) == 1:
        return next(iter(requirement_names))
    if len(requirement_names) > 1:
        return None

    # Some EIS layouts put the customer into the placement contact block as
    # text: ``Заказчик: Наименование: <org> ...``.  This is still explicit
    # customer-role evidence, unlike the surrounding placement organization.
    additional = _extract_section_info_value(html_str, ("Дополнительная информация",))
    if additional:
        match = re.search(
            r"(?:^|\s)Заказчик\s*:\s*Наименование\s*:\s*(.+?)"
            r"(?=\s+(?:Место\s+нахождения(?:\s+и\s+почтовый\s+адрес)?|"
            r"Почтовый\s+адрес|Адрес\s+электронной\s+почты|"
            r"Номер\s+контактного\s+телефона|Ответственное\s+должностное\s+лицо)\s*:|$)",
            additional,
            re.IGNORECASE,
        )
        if match:
            value = _strip_html(match.group(1))
            if value:
                return value
    return None


def _parse_detail_metadata(html_str: str, card_url: str | None) -> dict[str, Any]:
    title = _extract_card_main_info_value(html_str, "Объект закупки")
    customer_name = _extract_explicit_customer_name(html_str)
    publication_date = _parse_public_datetime(_extract_card_main_info_value(html_str, "Размещено"))
    application_deadline = _parse_public_datetime(_extract_card_main_info_value(html_str, "Окончание подачи заявок"))
    nmck_text = _extract_card_main_info_value(html_str, "Начальная цена")
    nmck_amount = _extract_price(nmck_text)
    customer_inn, customer_kpp = _extract_inn_kpp(html_str)
    registry_number = _extract_registry_from_url_or_html(card_url, html_str)
    return {
        "registry_number": registry_number,
        "title": title,
        "customer_name": customer_name,
        "customer_inn": customer_inn,
        "customer_kpp": customer_kpp,
        "publication_date": publication_date,
        "application_deadline": application_deadline,
        "nmck_amount": nmck_amount,
        "law_type": "44fz",
        "card_url": card_url,
    }


def _extract_card_main_info_value(html_str: str, label: str) -> str | None:
    pattern = re.compile(
        rf'<span[^>]*class="[^"]*\bcardMainInfo__title\b[^"]*"[^>]*>\s*{re.escape(label)}\s*</span>\s*'
        rf'<span[^>]*class="[^"]*\bcardMainInfo__content\b[^"]*"[^>]*>(.*?)</span>',
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(html_str)
    if match:
        return _strip_html(match.group(1))
    return None


def _extract_section_info_value(html_str: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        pattern = re.compile(
            rf'<span[^>]*class="[^"]*\bsection__title\b[^"]*"[^>]*>\s*{re.escape(label)}\s*</span>\s*'
            rf'<span[^>]*class="[^"]*\bsection__info\b[^"]*"[^>]*>(.*?)</span>',
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(html_str)
        if match:
            return _strip_html(match.group(1))
    return None


def _extract_inn_kpp(html_str: str) -> tuple[str | None, str | None]:
    inn_match = re.search(r'ИНН:\s*</span>\s*<span>(\d{10,12})</span>', html_str, re.IGNORECASE)
    kpp_match = re.search(r'КПП:\s*</span>\s*<span>(\d{9})</span>', html_str, re.IGNORECASE)
    return (
        inn_match.group(1) if inn_match else None,
        kpp_match.group(1) if kpp_match else None,
    )


def _extract_registry_from_url_or_html(card_url: str | None, html_str: str) -> str | None:
    if card_url:
        parsed = urlparse(card_url)
        reg_number = parse_qs(parsed.query).get("regNumber")
        if reg_number:
            return reg_number[0]
    return _extract_reestr_from_text(html_str)


def _extract_div_blocks_by_class(html_str: str, class_token: str) -> list[str]:
    """Return balanced ``div`` fragments whose class list contains ``class_token``."""

    tag_pattern = re.compile(r"<\s*(/?)\s*div\b([^>]*)>", re.IGNORECASE | re.DOTALL)
    class_pattern = re.compile(r"class\s*=\s*([\"'])(.*?)\1", re.IGNORECASE | re.DOTALL)
    depth = 0
    targets: list[tuple[int, int]] = []
    blocks: list[str] = []
    for match in tag_pattern.finditer(html_str):
        closing = bool(match.group(1))
        if not closing:
            depth += 1
            class_match = class_pattern.search(match.group(2))
            classes = class_match.group(2).split() if class_match else []
            if class_token in classes:
                targets.append((depth, match.start()))
            continue

        for index in range(len(targets) - 1, -1, -1):
            target_depth, start = targets[index]
            if target_depth == depth:
                blocks.append(html_str[start : match.end()])
                targets.pop(index)
                break
        depth = max(0, depth - 1)
    return blocks


def _extract_revision_value(block: str, label: str) -> str | None:
    pattern = re.compile(
        rf'<(?:div|span)[^>]*class="[^"]*\bsection__attrib\b[^"]*"[^>]*>\s*{re.escape(label)}\s*</(?:div|span)>\s*'
        rf'<(?:div|span)[^>]*class="[^"]*\bsection__value\b[^"]*"[^>]*>(.*?)</(?:div|span)>',
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(block)
    return _strip_html(match.group(1)) if match else None


def _extract_revision_title(block: str) -> str | None:
    match = re.search(
        r'<div[^>]*class="[^"]*\bdocName\b[^"]*"[^>]*>(.*?)</div>',
        block,
        re.IGNORECASE | re.DOTALL,
    )
    return _strip_html(match.group(1)) if match else None


def _extract_revision_number(block: str, title: str | None) -> int | None:
    match = re.search(r"[?&]versionNumber=(\d+)", block, re.IGNORECASE)
    if not match and title:
        match = re.search(r"\bв\s+ред\.\s*(\d+)\b", title, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _extract_revision_source_url(block: str, page_url: str) -> str:
    for match in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>', block, re.IGNORECASE | re.DOTALL):
        href = html.unescape(match.group(1))
        if "viewByVersionNumber" in href:
            return urljoin(page_url, href)
    return page_url


def _parse_revision_active_state(value: str | None) -> tuple[str | None, bool | None]:
    normalized = re.sub(r"\s+", " ", (value or "")).strip().lower()
    if "недействующ" in normalized:
        return "inactive", False
    if "действующ" in normalized:
        return "active", True
    return (normalized or None), None


def _dedupe_document_links(items: list[PublicDocumentLink]) -> list[PublicDocumentLink]:
    seen_urls: set[str] = set()
    result: list[PublicDocumentLink] = []
    for item in items:
        if item.url in seen_urls:
            continue
        seen_urls.add(item.url)
        result.append(item)
    return result


def _parse_notice_document_revisions(html_str: str, page_url: str) -> list[PublicNoticeRevision]:
    revisions: list[PublicNoticeRevision] = []
    for block in _extract_div_blocks_by_class(html_str, "notice-documents"):
        state_text = _extract_revision_value(block, "Редакция")
        title = _extract_revision_title(block)
        revision = _extract_revision_number(block, title)
        publication_timestamp = _extract_revision_value(block, "Размещено")
        state, active = _parse_revision_active_state(state_text)
        source_url = _extract_revision_source_url(block, page_url)
        links = _dedupe_document_links(_parse_document_links(block, page_url))
        provenance = {
            "revision": revision,
            "revision_publication_timestamp": publication_timestamp,
            "revision_state": state,
            "revision_active": active,
            "revision_source_url": source_url,
            "documents_page_url": page_url,
        }
        for link in links:
            link.raw.update(provenance)
        revisions.append(
            PublicNoticeRevision(
                revision=revision,
                publication_timestamp=publication_timestamp,
                state=state,
                active=active,
                source_url=source_url,
                title=title,
                document_links=links,
            )
        )
    return revisions


def _select_current_revision_document_links(
    html_str: str,
    page_url: str,
) -> tuple[list[PublicDocumentLink], list[PublicNoticeRevision], dict[str, Any]]:
    revisions = _parse_notice_document_revisions(html_str, page_url)
    if not revisions:
        revision_markers_exposed = (
            "inactive-redaction-toggle" in html_str
            or bool(re.search(r">\s*Редакция\s*<", html_str, re.IGNORECASE))
        )
        if revision_markers_exposed:
            return (
                [],
                [],
                {
                    "status": "revision_binding_unparsed",
                    "requires_review": True,
                    "reason": "EIS documents page exposes revision controls/state, but revision attachment blocks could not be parsed safely.",
                },
            )
        return (
            _dedupe_document_links(_parse_document_links(html_str, page_url)),
            [],
            {
                "status": "revision_state_not_exposed",
                "requires_review": False,
                "reason": "EIS documents page does not expose notice revision blocks.",
            },
        )

    unknown = [item for item in revisions if item.active is None]
    active = [item for item in revisions if item.active is True]
    if unknown or len(active) != 1:
        return (
            [],
            revisions,
            {
                "status": "ambiguous_revision_state",
                "requires_review": True,
                "reason": (
                    "Cannot bind public EIS attachments to one active notice revision: "
                    f"active={len(active)}, unknown={len(unknown)}, total={len(revisions)}."
                ),
            },
        )

    selected = active[0]
    any_links = any(item.document_links for item in revisions)
    if any_links and not selected.document_links:
        return (
            [],
            revisions,
            {
                "status": "active_revision_attachment_binding_missing",
                "requires_review": True,
                "reason": "Active EIS notice revision was identified, but its attachment binding is empty while other revisions contain attachments.",
                "active_revision": selected.provenance(),
            },
        )

    return (
        selected.document_links,
        revisions,
        {
            "status": "active_revision_selected",
            "requires_review": False,
            "reason": None,
            "active_revision": selected.provenance(),
        },
    )


def _parse_document_links(html_str: str, page_url: str) -> list[PublicDocumentLink]:
    document_links: list[PublicDocumentLink] = []
    attachment_blocks = re.finditer(
        r'<div[^>]*class="[^"]*\battachment\b[^"]*"[^>]*>(.*?)</div>\s*</div>',
        html_str,
        re.IGNORECASE | re.DOTALL,
    )
    for block_match in attachment_blocks:
        block = block_match.group(1)
        link_match = None
        for candidate in re.finditer(
            r'<a[^>]*href="([^"]+)"[^>]*(?:title="([^"]*)")?[^>]*>(.*?)</a>',
            block,
            re.IGNORECASE | re.DOTALL,
        ):
            candidate_url = urljoin(page_url, candidate.group(1))
            if "download" in candidate_url.lower():
                link_match = candidate
                break
        if not link_match:
            continue
        url = urljoin(page_url, link_match.group(1))
        anchor_tag = link_match.group(0)
        title_match = re.search(r'title="([^"]*)"', anchor_tag, re.IGNORECASE)
        file_name = _strip_html(title_match.group(1) if title_match else link_match.group(2))
        title = _strip_html(link_match.group(3))
        uid_match = re.search(r"[?&]uid=([^&]+)", url, re.IGNORECASE)
        icon_match = re.search(r'<img[^>]*alt="([^"]+)"', block, re.IGNORECASE)
        document_links.append(
            PublicDocumentLink(
                title=title or file_name or None,
                file_name=file_name or _derive_file_name_from_url(url),
                url=url,
                content_type=_guess_content_type(file_name or url, icon_match.group(1) if icon_match else None),
                size_bytes=None,
                size_text=None,
                raw={
                    "uid": uid_match.group(1) if uid_match else None,
                    "icon_alt": icon_match.group(1) if icon_match else None,
                },
            )
        )
    return document_links


def _derive_file_name_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    qs_file_name = parse_qs(parsed.query).get("fileName")
    if qs_file_name:
        return qs_file_name[0]
    match = re.search(r"/([^/?#]+)$", parsed.path)
    return match.group(1) if match else None


def _guess_content_type(name_or_url: str, icon_alt: str | None = None) -> str | None:
    lower = (name_or_url or "").lower()
    if lower.endswith(".pdf") or (icon_alt and "acrobat" in icon_alt.lower()):
        return "application/pdf"
    if lower.endswith(".docx") or (icon_alt and "word" in icon_alt.lower()):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if lower.endswith(".xlsx") or lower.endswith(".xls") or (icon_alt and "excel" in icon_alt.lower()):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if lower.endswith(".txt"):
        return "text/plain"
    if lower.endswith(".html") or lower.endswith(".htm"):
        return "text/html"
    if lower.endswith(".xml"):
        return "application/xml"
    return None


def _search_item_to_json_dict(item: PublicTenderSearchItem | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "registry_number": item.registry_number,
        "purchase_number": item.purchase_number,
        "title": item.title,
        "customer_name": item.customer_name,
        "customer_inn": item.customer_inn,
        "customer_kpp": item.customer_kpp,
        "publication_date": item.publication_date.isoformat() if item.publication_date else None,
        "application_deadline": item.application_deadline.isoformat() if item.application_deadline else None,
        "nmck_amount": float(item.nmck_amount) if item.nmck_amount is not None else None,
        "law_type": item.law_type,
        "source_url": item.source_url,
        "card_url": item.card_url,
        "is_demo": item.is_demo,
        "raw": item.raw,
    }


def _json_safe_mapping(data: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, datetime):
            safe[key] = value.isoformat()
        elif isinstance(value, Decimal):
            safe[key] = float(value)
        else:
            safe[key] = value
    return safe
