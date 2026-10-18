"""Six public original FL AI cards and independent duplicate against Workspace.

Read-only exact URLs. Never infer free-to-reply, buyer legal identity,
company eligibility, attached private technical PDF or a contract from CTA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from scripts.acceptance.audit_schlam_offer_original_oct17 import _Markup

INDEX = "https://www.fl.ru/projects/category/ai-iskusstvenniy-intellekt/"
CROSSPOST_WS = (
    "https://workspace.ru/tenders/"
    "vnedrenie-ii-sistemy-ucheta-syrya-sklada-i-proizvodstva-dlya-proizvoditelya-sellera-wb-i-ozon-19030/"
)
FL_ORIGINALS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "5525620": (
        "dorabotat-ai-poisk-i-ai-matching-promyishlennogo-oborudovaniya-",
        "SOURCE_IT_CUSTOMER_TASK_BUDGET_REVIEW",
        ("Развиваем маркетплейс промышленного оборудования", "Бюджет: 2 000 ₽"),
    ),
    "5525491": (
        "sozdat-tsentralizovannuyu-ai-platformu-",
        "SOURCE_IT_CUSTOMER_TASK_NO_PUBLIC_TZ_LINK",
        ("Создать централизованную AI платформу", "ТЗ в приложенном файле"),
    ),
    "5525426": (
        "sozdanie-ii-agentov-dlya-rabotyi-s-marketplesami",
        "SOURCE_IT_CUSTOMER_TASK_SCOPE_UNSPECIFIED",
        ("ИИ агентов для работы с маркетплесами", "Бюджет: 50 000 ₽", "ТЗ пришлем подробнее по запросу"),
    ),
    "5525297": (
        "vnedrenie-ii-sistemyi-uchta-syirya-sklada-i-proizvodstva-dlya-sellera-wb-i-ozon",
        "DUPLICATE_BUSINESS_SCOPE_WORKSPACE19030",
        ("Производитель орехов и сухофруктов", "около 200 заказов в день, 50 SKU"),
    ),
    "5524917": (
        "nastroit-lokalnyiy-ai-pomoschnik-rag-na-mom-pk",
        "PERSONAL_PC_CLIENT_LEGAL_B2B_UNVERIFIED",
        ("Настроить локальный AI-помощник (RAG) на моём ПК", "Ollama"),
    ),
    "5525421": (
        "nujno-sozdat-ii-agenta-v-kompaniyu",
        "VACANCY_NOT_SUPPLIER_TENDER",
        ("Нужно создать ИИ агента в компанию", "Ссылка на вакансию"),
    ),
}
SOURCE_MATCH = (
    "Продаём на Wildberries и Ozon (по 3 кабинета)",
    "около 200 заказов в день, 50 SKU",
    "Систему учёта с ИИ-агентами",
    "сырьё и упаковка по техкартам",
    "склад со сканером штрихкодов",
    "расчёт отгрузок на маркетплейсы",
)


class _Href(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            url = dict(attrs).get("href")
            if url:
                self.links.append(url)


def _original_url(number: str) -> str:
    return f"https://www.fl.ru/projects/{number}/{FL_ORIGINALS[number][0]}.html"


def _allowed(url: str) -> bool:
    p = urlsplit(url)
    return (
        p.scheme == "https" and not p.username and not p.password and p.port is None
        and not p.query and not p.fragment
        and (
            url in {INDEX, CROSSPOST_WS}
            or (
                p.hostname == "www.fl.ru"
                and any(url == _original_url(i) for i in FL_ORIGINALS)
            )
        )
    )


def get_original(url: str, cap: int) -> bytes:
    if not _allowed(url):
        raise ValueError("unapproved first-party exact original source")
    opener = build_opener(ProxyHandler({}))
    with opener.open(
        Request(url, headers={"User-Agent": "ArvectumTenderAgent-ReadOnlyOriginalResearch/1.0"}),
        timeout=12,
    ) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("unexpected HTTP or redirect")
        raw = response.read(cap + 1)
    if not 1000 < len(raw) <= cap:
        raise ValueError("source size out of bounds")
    return raw


def plain(raw: bytes) -> str:
    p = _Markup()
    p.feed(raw.decode("utf-8", "strict"))
    return " ".join(p.text.split())


def includes_source_phrase(whole: str, phrase: str) -> bool:
    return " ".join(phrase.casefold().split()) in " ".join(whole.casefold().split())


def list_verified_originals(raw: bytes) -> dict:
    if not 1000 < len(raw) <= 650_000:
        raise ValueError("FL index size out of bounds")
    p = _Href()
    p.feed(raw.decode("utf-8", "strict"))
    references = {urljoin(INDEX, href) for href in p.links}
    absent = [i for i in FL_ORIGINALS if _original_url(i) not in references]
    if absent:
        raise ValueError("previously observed first-party FL originals not in category index")
    return {
        "original_index_url": INDEX,
        "source_index_html_sha256": hashlib.sha256(raw).hexdigest(),
        "explicit_exact_card_urls_verified": len(FL_ORIGINALS),
    }


def audit_fl_card(number: str, raw: bytes) -> dict:
    if number not in FL_ORIGINALS or not 1000 < len(raw) <= 290_000:
        raise ValueError("unknown original FL project or body")
    text = plain(raw)
    slug, state, anchors = FL_ORIGINALS[number]
    expected_marker = "Ссылка на вакансию" if state == "VACANCY_NOT_SUPPLIER_TENDER" else "Ссылка на заказ"
    if expected_marker not in text or "Откликнуться" not in text:
        raise ValueError("original FL project type or public CTA changed")
    if not all(includes_source_phrase(text, a) for a in anchors):
        raise ValueError("original attested FL AI source obligation changed")
    refs = _Href()
    refs.feed(raw.decode("utf-8", "strict"))
    customer_links = [
        urljoin(_original_url(number), item)
        for item in refs.links
        if re.search(r"\.pdf(?:\?|$)|\.docx?(?:\?|$)", item, re.IGNORECASE)
        and not re.search(r"/about/|/security/|/cookie", item, re.IGNORECASE)
    ]
    if customer_links:
        # File metadata needs separate first-party research: NO automatic fetch.
        attachment_state = "PUBLIC_DOCUMENT_LINK_PRESENT_NOT_DOWNLOADED"
    else:
        attachment_state = "NO_PUBLIC_TZ_ATTACHMENT_HREF_IN_RETRIEVED_HTML"
    return {
        "id": number,
        "original_url": f"https://www.fl.ru/projects/{number}/{slug}.html",
        "original_source_html_sha256": hashlib.sha256(raw).hexdigest(),
        "original_source_bytes": len(raw),
        "reviewed_original_scope_fragments": list(anchors),
        "original_type": expected_marker,
        "source_classification": state,
        "fl_html_customer_tz_attachment_href_state": attachment_state,
        "is_verified_buyer_russian_llc": False,
        "is_original_free_for_all_reply_confirmed": False,
        "is_company_account_contract_accepted": False,
        "is_current_authenticated_reply_open_confirmed": False,
        "is_new_unique_b2b_customer_contract": False,
        "bid_or_reply_sent": False,
        "paid_action": False,
    }


def audit_crosspost(fl_raw: bytes, ws_raw: bytes) -> dict:
    fl = plain(fl_raw)
    ws = plain(ws_raw)
    if not all(includes_source_phrase(fl, a) and includes_source_phrase(ws, a) for a in SOURCE_MATCH):
        raise ValueError("cross-platform distinctive source anchors missing")
    return {
        "fl_original_id": "5525297",
        "workspace_original_id": "19030",
        "shared_distinct_original_scope_fragments": list(SOURCE_MATCH),
        "fl_original_html_sha256": hashlib.sha256(fl_raw).hexdigest(),
        "workspace_original_html_sha256": hashlib.sha256(ws_raw).hexdigest(),
        "deduplication_state": "HIGH_CONFIDENCE_SAME_SCOPE_CROSSPOST_NOT_NEW_INDEPENDENT_LEAD",
        "legal_buyer_inn_confirmed_same": False,
        "full_tz_pdf_original_downloaded": False,
        "independent_buyer_verification_required": True,
    }


def collect() -> dict:
    index = list_verified_originals(get_original(INDEX, 650_000))
    rows: list[dict] = []
    crosspost_fl: bytes | None = None
    for number in FL_ORIGINALS:
        raw = get_original(_original_url(number), 290_000)
        row = audit_fl_card(number, raw)
        row["observed_at_utc"] = datetime.now(UTC).isoformat()
        rows.append(row)
        if number == "5525297":
            crosspost_fl = raw
    if crosspost_fl is None:
        raise ValueError("crosspost FL original missing")
    crosspost = audit_crosspost(crosspost_fl, get_original(CROSSPOST_WS, 400_000))
    # Do not claim the original FL attachment file is available from web HTML.
    return {
        "schema_version": "ta-b2b-first-party-fl-ai-crosspost-2026-10-18-v1",
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "source_index": index,
        "reviewed_fl_original_card_count": len(rows),
        "distinct_fl_customer_it_descriptions_requiring_legal_review": 3,
        "crossposted_existing_workspace19030_count_not_new": 1,
        "vacancy_and_personal_scope_not_counted_as_b2b": 2,
        "verified_company_open_free_replies": 0,
        "verified_legal_company_eligible_contracts": 0,
        "user_company_paid_or_sent_actions": 0,
        "crosspost": crosspost,
        "cards": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    data = collect()
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "FL_ORIGINAL", data["reviewed_fl_original_card_count"],
        "NEW_IT_DESCRIPTIONS", data["distinct_fl_customer_it_descriptions_requiring_legal_review"],
        "CROSSPOST", data["crossposted_existing_workspace19030_count_not_new"],
        "LLC_READY", data["verified_legal_company_eligible_contracts"],
    )


if __name__ == "__main__":
    main()
