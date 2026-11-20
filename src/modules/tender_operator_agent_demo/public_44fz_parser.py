from __future__ import annotations

import re

from src.tender_research.providers.public_44fz_search import (
    MAX_RESPONSE_BYTES,
    PublicSearchStatus,
    PublicTenderSearchItem,
    PublicTenderSearchPage,
    Public44FzSearchProvider,
    _classify_search_html,
    _extract_price,
    _extract_first_date,
    _extract_procedure_type,
    _extract_reestr_from_card,
    _extract_reestr_from_text,
    _extract_between,
    _extract_label_value_pairs,
    _extract_registry_body_pairs,
    _fallback_extract_by_number_patterns,
    _first_matching_value,
    _normalize_law,
    _parse_single_entry,
    _split_registry_entries,
    _strip_html,
    parse_44fz_search_results,
)

Public44FzSearchStatus = PublicSearchStatus
PublicTenderSearchItem = PublicTenderSearchItem
PublicTenderSearchPage = PublicTenderSearchPage
Public44FzSearchProvider = Public44FzSearchProvider
extract_reestr_number_from_44fz_card = _extract_reestr_from_card


def extract_public_search_total_count(html_content: str) -> int | None:
    if not html_content or not html_content.strip():
        return None
    csv_count_match = re.search(
        r'downloadCsv\([^\)]*?,\s*["\'](?P<count>\d+)["\']\)',
        html_content,
        re.IGNORECASE | re.DOTALL,
    )
    if csv_count_match:
        return int(csv_count_match.group("count"))
    match = re.search(
        r'<div class="search-results__total">\s*(?P<content>.*?)\s*</div>',
        html_content,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    content = _strip_html(match.group("content")).replace("\xa0", " ").strip()
    if not content:
        return None
    if "более" in content.lower():
        return None
    number_match = re.search(r'(\d[\d\s]*)', content)
    if not number_match:
        return None
    digits = number_match.group(1).replace(" ", "")
    return int(digits) if digits.isdigit() else None

def classify_public_search_response(html_content: str) -> str:
    if not html_content or not html_content.strip():
        return PublicSearchStatus.EMPTY_RESULTS
    if parse_44fz_search_results(html_content):
        return PublicSearchStatus.PARSED
    lower = html_content.lower()
    if any(
        marker in lower
        for marker in (
            "your browser does not support javascript",
            "ваш браузер не поддерживает javascript",
            "включите javascript",
        )
    ):
        return PublicSearchStatus.JS_HEAVY
    classified = _classify_search_html(html_content)
    # The current EIS layout reports a zero count, an empty registry block,
    # and a noRecords marker. Do not confuse this with an unknown layout,
    # a blocked page, or a blank transport response.
    if classified != "captcha_or_blocked" and (
        extract_public_search_total_count(html_content) == 0
        and re.search(r'<div\s+class="search-results__total">\s*0\s+записей\s*</div>', html_content, re.I)
        and re.search(r'<div\s+class="search-registry-entrys-block">\s*</div>', html_content, re.I)
        and re.search(r'<p\s+class="noRecords">\s*Поиск не дал результатов\s*</p>', html_content, re.I)
    ):
        return PublicSearchStatus.EMPTY_RESULTS
    if classified == "empty_results":
        return PublicSearchStatus.EMPTY_RESULTS
    if classified == "captcha_or_blocked":
        return PublicSearchStatus.CAPTCHA_OR_BLOCKED
    return PublicSearchStatus.UNSUPPORTED_LAYOUT

# Backward-compatible fetcher (uses shared provider under the hood)
_default_provider: Public44FzSearchProvider | None = None


def _get_provider() -> Public44FzSearchProvider:
    global _default_provider
    if _default_provider is None:
        _default_provider = Public44FzSearchProvider(bypass_proxy=True)
    return _default_provider


def fetch_public_44fz_search_page(url: str) -> dict:
    provider = _get_provider()
    result = provider._fetch_page(url)
    status = result.get("status")
    if status == PublicSearchStatus.SUCCESS:
        html_content = result.get("html")
        classification = classify_public_search_response(html_content or "")
        return {
            "status": classification,
            "html": html_content if classification == PublicSearchStatus.PARSED else None,
            # A blank HTTP body can be labelled EMPTY_RESULTS by the legacy parser.
            # Only an actual zero count on a nonblank result page is coverage evidence.
            "explicit_zero_count": bool(html_content and extract_public_search_total_count(html_content) == 0
                                        and classification in {PublicSearchStatus.PARSED, PublicSearchStatus.EMPTY_RESULTS}),
            "error": None,
        }
    return {
        "status": status or PublicSearchStatus.NETWORK_ERROR,
        "html": None,
        "error": result.get("error"),
    }
