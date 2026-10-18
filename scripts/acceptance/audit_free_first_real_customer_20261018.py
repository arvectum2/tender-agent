"""Exact first-party free-first sources: distinguish service ads from real tasks.

A visible original card, even with an 'Open' label, does not prove an
available company contract, free company reply or actual client identity.
Never send replies, crawl linked domains, access accounts or buy packages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from scripts.acceptance.audit_schlam_offer_original_oct17 import _Markup

INDEXES = {
    "contractis": "https://contractis.ru/order/c/programmirovanie",
    "codelance": "https://www.codelance.ru/orders",
}
# Anchors individually verified against original full source tasks, NOT
# induced by generative labels, search summaries or accidental keyword hits.
_CODELANCE = {
    156: ("SELF_ADVERTISEMENT", "Занимаюсь разработкой и доработкой сайтов на PHP"),
    154: ("SELF_ADVERTISEMENT", "Ищу исполнителя? Нет — предлагаю помощь"),
    153: ("SELF_ADVERTISEMENT", "нарабатываю портфолио"),
    152: ("SELF_ADVERTISEMENT", "Могу разработать сайт"),
    151: ("SELF_ADVERTISEMENT", "занимаюсь разработкой сайтов на заказ"),
    150: ("SELF_ADVERTISEMENT", "СОЗДАНИЕ САЙТОВ И CRM-СИСТЕМ ПОД КЛЮЧ"),
    149: ("SELF_ADVERTISEMENT", "Сделаю Android приложение"),
    147: ("CUSTOMER_IT_REQUEST_STATUS_UNVERIFIED", "нам необходимо разместить на сайте"),
    146: ("SELF_ADVERTISEMENT", "Разработаю современный сайт или лендинг"),
    142: ("SELF_ADVERTISEMENT", "Могу разработать сайт почти любой сложности"),
    141: ("NOT_IT_CONTRACT_WORK", "Ищем исполнителей для выполнения несложных онлайн-заданий"),
    140: ("REJECT_RISK_OR_OUT_OF_SCOPE", "Ищу кодера кто делает flash usdt"),
}
_CONTRACTIS = {
    "trebuetsya-specialist-po-sozdaniyu-kartochek-tovarov-dlya-wi": (
        15, "NOT_IT_CONTRACT_WORK", "создавать и оформлять карточки товаров"
    ),
    "sait-dlya-padl-kluba-lending-s-bronirovaniem": (
        12, "CUSTOMER_IT_REQUEST_STATUS_UNVERIFIED", "Требуется разработать одностраничный сайт"
    ),
    "razrabotka-lendinga": (
        8, "CUSTOMER_IT_REQUEST_STATUS_UNVERIFIED", "Разработать одностраничный лендинг"
    ),
    "ishchu-podryadchika-na-razrabotku-po-na-python-rabota-s-ii": (
        6, "CUSTOMER_IT_REQUEST_STATUS_UNVERIFIED", "Требуется разработать программное обеспечение на Python"
    ),
    "skorrektirovat-sait-stomatologii-na-tilde-prikazu-minzdrava": (
        5, "CUSTOMER_IT_REQUEST_STATUS_UNVERIFIED", "Необходимо проверить каких пунктов не хватает"
    ),
    "nuzhen-razrabotchik-rhp-laravel-na-bolshoi-proekt-razrabotka": (
        4, "CUSTOMER_IT_REQUEST_STATUS_UNVERIFIED", "Требуется разработчик PHP с опытом работы на Laravel"
    ),
    "razrabotat-sait-dlya-kompanii-avtoservis": (
        2, "CUSTOMER_IT_REQUEST_STATUS_UNVERIFIED", "Разработать сайт для компании автосервис"
    ),
}
MAX_BYTES = 350_000


class _Refs(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            value = dict(attrs).get("href")
            if value:
                self.hrefs.append(value)


def _exact_original(url: str, provider: str) -> str | None:
    try:
        p = urlsplit(url)
        if (
            p.scheme != "https" or p.username or p.password
            or p.port is not None or p.fragment
        ):
            return None
        if provider == "codelance":
            if (
                p.hostname == "www.codelance.ru"
                and p.path == "/orders/view"
                and re.fullmatch(r"id=\d{1,4}", p.query)
            ):
                return p.query.removeprefix("id=")
        elif (
            provider == "contractis"
            and p.hostname == "contractis.ru" and not p.query
            and re.fullmatch(r"/order/[a-z0-9-]+", p.path)
            and p.path not in ("/order/create", "/order/your")
        ):
            return p.path.removeprefix("/order/")
    except ValueError:
        return None
    return None


def _first_party_get(url: str, provider: str) -> bytes:
    if _exact_original(url, provider) is None and url != INDEXES.get(provider):
        raise ValueError("unapproved source URL")
    opener = build_opener(ProxyHandler({}))
    with opener.open(
        Request(url, headers={"User-Agent": "ArvectumTenderAgent-OriginalCustomerResearch/1.0"}),
        timeout=12,
    ) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("source redirected or failed")
        raw = response.read(MAX_BYTES + 1)
    if not 1_000 <= len(raw) <= MAX_BYTES:
        raise ValueError("invalid first-party bounded source size")
    return raw


def _visible(raw: bytes) -> str:
    markup = _Markup()
    markup.feed(raw.decode("utf-8", "strict"))
    return " ".join(markup.text.split())


def discover_exact_listed(raw: bytes, provider: str) -> list[str]:
    if provider not in INDEXES or not 1000 <= len(raw) <= MAX_BYTES:
        raise ValueError("first-party index not allowed")
    refs = _Refs()
    refs.feed(raw.decode("utf-8", "strict"))
    seen: set[str] = set()
    urls: list[str] = []
    from urllib.parse import urljoin

    for href in refs.hrefs:
        link = urljoin(INDEXES[provider], href)
        identity = _exact_original(link, provider)
        if identity and identity not in seen:
            seen.add(identity)
            urls.append(link)
    expected = (
        {str(x) for x in _CODELANCE}
        if provider == "codelance" else set(_CONTRACTIS)
    )
    identities = {_exact_original(u, provider) for u in urls}
    if identities != expected or len(urls) != len(expected):
        raise ValueError("first-party original index list materially changed")
    return urls


def evaluate_original(raw: bytes, provider: str, url: str, observed: datetime) -> dict:
    identity = _exact_original(url, provider)
    if not identity or observed.utcoffset() is None or not 1000 <= len(raw) <= MAX_BYTES:
        raise ValueError("invalid original source identity")
    text = _visible(raw)
    if provider == "codelance":
        number = int(identity)
        wanted = _CODELANCE.get(number)
        if wanted is None:
            raise ValueError("unreviewed original CodeLance number")
        interpretation, anchor = wanted
        if "Открыт" not in text[:750] or "Что нужно" not in text:
            raise ValueError("original CodeLance status/brief unavailable")
        excerpt = text.split("Что нужно", 1)[1].split("Ваш отклик", 1)[0]
        # Heading is a separate source requirement; 'Open' isn't proof of a client.
        published_status = "Открыт"
        original_id = f"codelance:{number}"
    elif provider == "contractis":
        wanted = _CONTRACTIS.get(identity)
        if wanted is None:
            raise ValueError("unreviewed original CONTRACTIS slug")
        orig_num, interpretation, anchor = wanted
        if f"Заказ № {orig_num}" not in text[:1000] or "Заказчик" not in text[:1100]:
            raise ValueError("original CONTRACTIS buyer/order identity unavailable")
        if "Описание" not in text:
            raise ValueError("original CONTRACTIS task description unavailable")
        excerpt = text.split("Описание", 1)[1].split("Общее О бирже", 1)[0]
        published_status = "CURRENT_APPLICATION_STATUS_NOT_EXPLICITLY_VERIFIED"
        original_id = f"contractis:{orig_num}"
    else:
        raise ValueError("unexpected first-party source")
    if " ".join(anchor.casefold().split()) not in " ".join(excerpt.casefold().split()):
        raise ValueError("original reviewed customer/seller evidence changed")
    if interpretation == "CUSTOMER_IT_REQUEST_STATUS_UNVERIFIED":
        customer_gate = "CLIENT_REQUEST_CONTENT_ATTESTED_CURRENT_REPLY_UNVERIFIED"
    else:
        customer_gate = "EXCLUDED_FROM_CUSTOMER_LEADS"
    return {
        "original_id": original_id,
        "source_provider": provider,
        "original_url": url,
        "original_html_sha256": hashlib.sha256(raw).hexdigest(),
        "original_html_bytes": len(raw),
        "checked_at_utc": observed.isoformat(),
        "original_status_literal_or_gap": published_status,
        "source_role": interpretation,
        "role_proof_literal": anchor if interpretation != "REJECT_RISK_OR_OUT_OF_SCOPE" else "RISK_OR_OUT_OF_SCOPE_FIRST_PARTY_REVIEW",
        "customer_gate": customer_gate,
        "authenticated_current_response_enabled": False,
        "legal_company_buyer_inn_verified": False,
        "legal_company_contract_permission_verified": False,
        "free_llc_reply_entitlement_verified": False,
        "source_is_not_proof_of_future_availability": True,
        "company_offer_sent": False,
        "paid_subscription_or_registration": False,
    }


def collect() -> dict:
    indexes: list[dict] = []
    originals: list[tuple[str, str]] = []
    for provider, index in INDEXES.items():
        raw = _first_party_get(index, provider)
        urls = discover_exact_listed(raw, provider)
        indexes.append({
            "provider": provider, "original_index_url": index,
            "original_index_html_sha256": hashlib.sha256(raw).hexdigest(),
            "listed_original_card_count": len(urls),
        })
        originals.extend((provider, u) for u in urls)

    def source(pair: tuple[str, str]) -> dict:
        provider, url = pair
        try:
            raw = _first_party_get(url, provider)
            return evaluate_original(raw, provider, url, datetime.now(UTC))
        except (OSError, ValueError, UnicodeError) as exc:
            return {
                "source_provider": provider, "original_url": url,
                "original_id": f"{provider}:{_exact_original(url, provider)}",
                "source_role": "ORIGINAL_UNAVAILABLE_REVIEW_REQUIRED",
                "source_error_type": type(exc).__name__,
                "customer_gate": "EXCLUDED_FROM_CUSTOMER_LEADS",
                "legal_company_contract_permission_verified": False,
                "free_llc_reply_entitlement_verified": False,
                "company_offer_sent": False,
                "paid_subscription_or_registration": False,
            }
    with ThreadPoolExecutor(max_workers=4) as pool:
        cards = list(pool.map(source, originals))
    count = sum(
        c["customer_gate"] == "CLIENT_REQUEST_CONTENT_ATTESTED_CURRENT_REPLY_UNVERIFIED"
        for c in cards
    )
    return {
        "schema_version": "ta-b2b-free-first-source-role-originals-2026-10-18-v1",
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "first_party_indices": indexes,
        "original_listed_unique_cards": len(originals),
        "original_customer_it_scope_descriptions": count,
        "original_status_and_llc_reply_both_verified_count": 0,
        "verified_company_bidding_ready_count": 0,
        "actual_free_llc_first_reply_count": 0,
        "new_same_buyer_unique_it_contracts_not_automatically_proven": True,
        "outgoing_communications_or_paid_actions": 0,
        "rows": cards,
    }


def main() -> None:
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument("--out", type=Path, required=True)
    a = arg.parse_args()
    result = collect()
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "FIRST_PARTY_ORIGINALS", result["original_listed_unique_cards"],
        "CLIENT_SCOPE_ONLY", result["original_customer_it_scope_descriptions"],
        "LLC_READY", result["verified_company_bidding_ready_count"],
    )


if __name__ == "__main__":
    main()
