"""Fail-closed classification of links to EIS market-price inquiries.

An official price-information request is distinct from an electronic
quotation procurement. This pure guard uses *source URL provenance*, never
a guessed procedure type from the nineteen-digit register number or SOAP
no_data. It cannot authorize a competitive bid or attest live card status.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit


def official_eis_price_request_source_error(
    source_url: str | None,
    reestr_number: str,
) -> str | None:
    """Return reason if the source points into the official price registry.

    None means this URL is not demonstrably from the EIS price inquiry
    registry; it does NOT attest that the record is a competitive tender.
    """
    if not source_url:
        return None
    try:
        parsed = urlsplit(source_url.strip())
        if (
            parsed.scheme.lower() != "https"
            or parsed.hostname != "zakupki.gov.ru"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
        ):
            return None
    except ValueError:
        return None

    if not re.match(r"^/epz/pricereq(?:/|$)", parsed.path, flags=re.IGNORECASE):
        return None
    query = parse_qs(parsed.query, keep_blank_values=True)
    expected_key = (
        "searchString"
        if parsed.path.lower().startswith("/epz/pricereq/search/")
        else "reestrNumber"
    )
    number = reestr_number.strip()
    if not re.fullmatch(r"[0-9]{19}", number):
        return "SOURCE_RECORD_ID_INVALID"
    if query.get(expected_key) != [number]:
        return "SOURCE_RECORD_ID_MISMATCH"
    return "MARKET_RESEARCH_PRICE_REQUEST_ONLY"
