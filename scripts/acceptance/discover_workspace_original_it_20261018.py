"""Bounded first-party original WEB/APP/CRM cards; public != LLC bidder right.

Read-only exact HTTPS GET of 3 named category indexes and up to 31
canonical original cards (10 per category, plus prior original Schlam).
No platform login, pricing cart, proposal, original HTML archive or payment.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from scripts.acceptance.audit_schlam_offer_original_oct17 import _Markup
from scripts.acceptance.audit_workspace_oct17_cards import _MONTHS, _single
from scripts.acceptance.refresh_workspace_llc_originals import original_cases
from src.tender_research.corporate_lead_gate import triage_corporate_card

INDEX_URLS = (
    ("WEB", "https://workspace.ru/tenders/web-development/"),
    ("APPS", "https://workspace.ru/tenders/apps-development/"),
    ("CRM", "https://workspace.ru/tenders/crm/"),
)
MAX_INDEX_BYTES = 250_000
MAX_CARD_BYTES = 400_000
MAX_CARDS_PER_INDEX = 10
MAX_UNIQUE_CARDS = MAX_CARDS_PER_INDEX * len(INDEX_URLS) + 1

# Exact original source literals, not a guessed skills/cost/rating model.
PRIORITY_SOURCE_ANCHORS = {
    "19012": (
        "Дизайн главной страницы сайта детских товаров",
        "Материалы: ТЗ, прототип, мудборд.",
        "Бюджет: 100 000 - 400 000 рублей",
    ),
    "19034": (
        "Платформа: WordPress.",
        "Бюджет: 100 000 - 200 000 рублей",
        "Файлы для скачивания доступны участникам с PRO-аккаунтом",
    ),
    "18939": (
        "AI-кейсах в HealthTech",
        "OCR-распознаванием медицинских документов",
        "152-ФЗ",
        "Бюджет: 250 000 - 1 000 000 рублей",
    ),
}
_CARD_RE = re.compile(r"/tenders/([a-z0-9][a-z0-9-]*)-(\d{5})/")
_ALLOWED_HOST = "workspace.ru"


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


def _canonical_card(url: str) -> tuple[str, str] | None:
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https" or parsed.hostname != _ALLOWED_HOST
            or parsed.username or parsed.password or parsed.port is not None
            or parsed.query or parsed.fragment
        ):
            return None
        match = _CARD_RE.fullmatch(parsed.path)
        return (match.group(2), match.group(1)) if match else None
    except ValueError:
        return None


def discover_exact_cards(index_data: bytes, *, index_url: str) -> list[tuple[str, str, str]]:
    if index_url not in {u for _, u in INDEX_URLS}:
        raise ValueError("unapproved original category index")
    if not 1000 < len(index_data) <= MAX_INDEX_BYTES:
        raise ValueError("invalid category index size")
    source = _Links()
    source.feed(index_data.decode("utf-8", "strict"))
    result: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for href in source.hrefs:
        u = urljoin(index_url, href)
        parsed = _canonical_card(u)
        if parsed is None:
            continue
        number, slug = parsed
        if number not in seen:
            result.append((number, slug, u))
            seen.add(number)
        if len(result) == MAX_CARDS_PER_INDEX:
            break
    if not result:
        raise ValueError("no original tenders attested on first-party category page")
    return result


def _date_from_original(text: str) -> str:
    marker = "Крайний срок приема заявок:"
    if text.count(marker) != 1:
        raise ValueError("deadline original marker missing or ambiguous")
    window = re.sub(r"<[^>]+>", " ", text.split(marker, 1)[1][:300])
    value = _single(window, r"\b(\d{1,2}\s+[А-Яа-яё]+\s+20\d\d)\b", "original due date")
    day, month, year = value.casefold().split()
    if month not in _MONTHS:
        raise ValueError("unrecognized original due-month")
    return date(int(year), int(_MONTHS[month]), int(day)).isoformat()


def evaluate_original_card(
    *, number: str, slug: str, original_url: str, body: bytes,
    observed: datetime, categories: tuple[str, ...],
) -> dict:
    if (
        observed.tzinfo is None or observed.utcoffset() is None
        or _canonical_card(original_url) != (number, slug)
        or not 500 < len(body) <= MAX_CARD_BYTES
    ):
        raise ValueError("original source identity/timestamp/size invalid")
    original = body.decode("utf-8", "strict")
    title_html = _single(original, r"<h1[^>]*>\s*(.*?)\s*</h1>", "original title")
    title = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", title_html)).split())
    if not 5 < len(title) < 400 or "<" in title or ">" in title:
        raise ValueError("original title ambiguous")
    status = _single(
        original,
        r'class="tendercart-type__status-public[^"]*"\s*>\s*([^<]+)\s*</div>',
        "original status",
    )
    visibility = _single(original, r'class="reference\s+_(public|private)"\s*>', "original visibility")
    marker = "Oрганизатор"
    if original.count(marker) != 1:
        raise ValueError("original organizer label absent/duplicated")
    block = re.sub(r"<[^>]+>", " ", original.split(marker, 1)[1][:480])
    organizer = _single(block, r"\b(Юридическое лицо|Частное лицо)\b", "buyer entity type")
    due = _date_from_original(original)
    public_status = triage_corporate_card({
        "source_url": original_url,
        "organizer_type": organizer,
        "platform_status": status,
        "source_observed_at": observed.isoformat(),
        "submission_deadline": due,
    }, checked_at=observed)
    state = public_status.state
    reason = public_status.reason
    visible = _Markup()
    visible.feed(original)
    plain_text = " ".join(visible.text.casefold().split())
    anchors = PRIORITY_SOURCE_ANCHORS.get(number)
    source_scope_status = "NOT_DEEP_REVIEWED"
    if anchors:
        source_scope_status = (
            "PRIORITY_ORIGINAL_REQUIREMENTS_ATTESTED"
            if all(" ".join(x.casefold().split()) in plain_text for x in anchors)
            else "MANDATORY_PRIORITY_SOURCE_TEXT_MISSING"
        )
        if source_scope_status != "PRIORITY_ORIGINAL_REQUIREMENTS_ATTESTED":
            state = "REVIEW_REQUIRED"
            reason = "priority_original_requirement_changed"
    if visibility != "public" and state == "PUBLIC_CANDIDATE_ONLY":
        state = "REVIEW_REQUIRED"
        reason = "non_public_original_card"
    return {
        "id": number,
        "source_url": original_url,
        "source_sha256": hashlib.sha256(body).hexdigest(),
        "original_source_bytes": len(body),
        "checked_at_utc": observed.isoformat(),
        "title": title,
        "source_categories": sorted(categories),
        "source_http_status": 200,
        "printed_status": status,
        "organizer_type": organizer,
        "visibility": visibility,
        "printed_deadline_day": due,
        "deadline_clock_time": "UNKNOWN",
        "public_source_state": state,
        "source_state_reason": reason,
        "scope_attestation_state": source_scope_status,
        "original_required_scope_fragments": list(anchors) if source_scope_status == "PRIORITY_ORIGINAL_REQUIREMENTS_ATTESTED" else [],
        "verified_legal_buyer_inn": False,
        "company_paid_or_free_reply_access_verified": False,
        "company_mandatory_portfolio_verified": False,
        "company_bidding_ready": False,
        "real_order_requirements_fully_verified": False,
        "company_owner_go": False,
        "messages_or_payment_executed": 0,
    }


def _get(url: str, *, max_bytes: int) -> bytes:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https" or parsed.hostname != _ALLOWED_HOST
        or parsed.username or parsed.password or parsed.port is not None
        or parsed.query or parsed.fragment
    ):
        raise ValueError("unapproved original read-only source")
    op = build_opener(ProxyHandler({}))
    with op.open(Request(url, headers={"User-Agent": "ArvectumTenderAgent-OriginalSourceResearch/1.0"}), timeout=12) as r:
        if r.status != 200 or r.geturl() != url:
            raise ValueError("original source not exact HTTP200")
        raw = r.read(max_bytes + 1)
    if not 500 < len(raw) <= max_bytes:
        raise ValueError("original body outside bounded envelope")
    return raw


def collect() -> dict:
    indexes: list[dict] = []
    discovered: dict[str, dict] = {}
    for category, url in INDEX_URLS:
        raw = _get(url, max_bytes=MAX_INDEX_BYTES)
        cards = discover_exact_cards(raw, index_url=url)
        indexes.append({
            "category": category,
            "url": url,
            "http_status": 200,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "listed_first_party_cards": len(cards),
        })
        for key, slug, original_url in cards:
            if key in discovered:
                if discovered[key]["url"] != original_url:
                    raise ValueError("one tender ID maps to more than one original URL")
                discovered[key]["categories"].add(category)
            else:
                discovered[key] = {"url": original_url, "slug": slug, "categories": {category}}
    # Prior live specific buyer Schlam 19006 is not on the first 10 index cards.
    for original in original_cases():
        if original["id"] != "19006":
            continue
        url = original["url"]
        key = original["id"]
        data = _canonical_card(url)
        if data is None or data[0] != key:
            raise ValueError("original Schlam identity mismatch")
        if key not in discovered:
            discovered[key] = {"url": url, "slug": data[1], "categories": {"KNOWN_PREVIOUS"}}
    if not 1 <= len(discovered) <= MAX_UNIQUE_CARDS:
        raise ValueError("unbounded category discovery")
    checked = datetime.now(UTC)
    def fetch(row: tuple[str, dict]) -> dict:
        key, record = row
        try:
            raw = _get(record["url"], max_bytes=MAX_CARD_BYTES)
            return evaluate_original_card(
                number=key, slug=record["slug"], original_url=record["url"],
                body=raw, observed=datetime.now(UTC),
                categories=tuple(record["categories"]),
            )
        except (OSError, UnicodeError, ValueError) as exc:
            return {
                "id": key, "source_url": record["url"],
                "checked_at_utc": datetime.now(UTC).isoformat(),
                "source_categories": sorted(record["categories"]),
                "public_source_state": "REVIEW_REQUIRED",
                "source_state_reason": "original_unavailable_or_unparseable",
                "source_error_type": type(exc).__name__,
                "company_bidding_ready": False,
                "company_owner_go": False,
                "messages_or_payment_executed": 0,
            }
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(fetch, sorted(discovered.items())))
    results.sort(key=lambda x: (
        0 if x["public_source_state"] == "PUBLIC_CANDIDATE_ONLY" else 1,
        x.get("printed_deadline_day", "9999-12-31"), x["id"],
    ))
    return {
        "schema_version": "ta-b2b-workspace-first-party-three-it-categories-2026-10-18-v1",
        "observed_at_utc": checked.isoformat(),
        "source_kind": "ORIGINAL_PUBLIC_WORKSPACE_CARD_DIRECT_READONLY_NO_ACCOUNT",
        "original_category_pages": indexes,
        "unique_original_cards_checked": len(results),
        "original_public_corporate_accepting_candidates": sum(
            x["public_source_state"] == "PUBLIC_CANDIDATE_ONLY" for x in results
        ),
        "actual_company_eligible_to_respond_count": 0,
        "legal_buyer_inn_confirmed_count": 0,
        "original_cards_not_currently_attested_corporate": sum(
            x["public_source_state"] != "PUBLIC_CANDIDATE_ONLY" for x in results
        ),
        "company_account_access_or_cost_verified": False,
        "owner_submission_authority": False,
        "actual_eligible_15_to_20_target_met": False,
        "external_messages_or_purchases": 0,
        "rows": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = collect()
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ORIGINALS", result["unique_original_cards_checked"],
          "PUBLIC_LEGAL_CANDIDATES", result["original_public_corporate_accepting_candidates"],
          "LLC_REPLIES_READY", result["actual_company_eligible_to_respond_count"])


if __name__ == "__main__":
    main()
