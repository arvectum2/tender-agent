"""Fail-closed official EIS registry fallback when competitive getDocsIP has no ZIP.

Some 44-FZ market-price inquiries live in /epz/pricereq/, not the
competitive notice archive. A SOAP 'no_data' is only a method-specific result.
Probe an exact registry identity before reporting missing documentation.
Never infer bid eligibility, NMCK, current status or complete attachments.
"""
from __future__ import annotations

import hashlib
import html
import re
from collections.abc import Callable
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

_PRICE_CARD_PREFIX="https://zakupki.gov.ru/epz/pricereq/card/common-info.html?reestrNumber="
_MAX_CARD_BYTES=1_600_000


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        del request, fp, code, msg, headers, newurl


def _official_identity(url: str, expected: str) -> bool:
    parsed=urlsplit(url)
    return (parsed.scheme=="https" and parsed.netloc=="zakupki.gov.ru"
            and parsed.path=="/epz/pricereq/card/common-info.html"
            and parsed.query=="reestrNumber="+expected and parsed.fragment=="")


def _download_official_card(url: str) -> tuple[bytes,str]:
    opener=build_opener(ProxyHandler({}),_NoRedirect())
    req=Request(url,headers={
        "User-Agent":"Mozilla/5.0 (compatible; ArvectumTenderAgent/1.0; read-only)",
        "Accept":"text/html",
    })
    with opener.open(req,timeout=4) as response:
        raw=response.read(_MAX_CARD_BYTES+1)
        actual=response.geturl()
        if response.status!=200 or len(raw)>_MAX_CARD_BYTES:
            raise ValueError("official registry card unavailable/oversized")
        return raw,actual


def probe_exact_eis_price_request(
    registry_number: str,
    *,
    download: Callable[[str],tuple[bytes,str]]|None=None,
) -> dict[str,str]|None:
    """Return source-attested official noncompetitive type or None.

    None is *not* a statement that the price enquiry does not exist: an
    unreachable or unsupported page remains UNKNOWN, never 'absent'.
    """
    if not re.fullmatch(r"\d{19}",registry_number):
        return None
    url=_PRICE_CARD_PREFIX+registry_number
    if not _official_identity(url,registry_number):
        return None
    try:
        raw,actual=(download or _download_official_card)(url)
        if not isinstance(raw,bytes) or not (0<len(raw)<=_MAX_CARD_BYTES):
            return None
        if not _official_identity(actual,registry_number):
            return None
        text=html.unescape(re.sub(r"<[^>]*>"," ",raw.decode("utf-8","replace")))
        text=" ".join(text.split())
        # A single number mention or an HTML navigation link alone is never
        # enough. Require exact official price inquiry *card* semantics.
        if not (
            re.search(r"№\s*"+re.escape(registry_number)+r"(?!\d)",text)
            and "Карточка запроса цен товаров, работ, услуг" in text
            and "Общая информация запроса цен" in text
            and "Проведение данной процедуры сбора информации не влечет" in text
        ):
            return None
        return {
            "procedure_type":"price_information_request",
            "authority":"eis_official",
            "procurement_id":registry_number,
            "official_source_url":url,
            "source_document_sha256":hashlib.sha256(raw).hexdigest(),
            "bid_ready":"false",
        }
    except (OSError,TimeoutError,ValueError,UnicodeError):
        return None
