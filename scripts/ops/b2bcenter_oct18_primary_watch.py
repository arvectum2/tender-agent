"""Read-only first-party B2B-Center category-index & detail-page source audit.

Respects the original page's *submission deadline*, NOT its static progress bar
labels ("Приём заявок" can still appear on expired listings).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from lxml import html

ROOT = Path(__file__).resolve().parents[2]
WATCH = ROOT / "docs/roadmap/b2bcenter_watchlist_oct18.json"
MAX_BYTES = 950_000
MSK = timezone(timedelta(hours=3))
INDEX = "https://www.b2b-center.ru/search/industry/{category}/"
ALLOWED_CATEGORY = {"crm-sistemy", "texpodderzhka", "razrabotka-sajtov",
                    "razrabotka-mobilnogo-prilozheniya"}
ALLOWED_SCOPE = {"MARKET_RESEARCH_RFI", "CRM_IMPLEMENTATION",
                 "LICENSE_RENEWAL_NON_DEVELOPMENT", "WEB_BRAND_PREQUALIFICATION",
                 "MOBILE_UX_TEST_AND_DESIGN", "MEDICAL_MOBILE_AND_PATIENT_IT"}
ID_RE = re.compile(r"tender-(\d{7})/\Z")
DATE_RE = re.compile(r"Подать заявку до:\s*(\d{1,2}\.\d{1,2}\.2026)\s+(\d\d:\d\d)\s*мск")
DETAIL_DEADLINE_RE = re.compile(r"^(до|с)\s+(\d{1,2}\.\d{1,2}\.2026)\s+(\d\d:\d\d), по МСК$")
PUBLIC_STAGES = {"Приём заявок", "Прием заявок", "Завершён", "Приём заявок завершён"}


class OriginalMarketError(ValueError):
    """Ambiguous source; never allow stale/unknown leads into GO list."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_watchlist(items: object) -> list[dict]:
    if not isinstance(items, list) or len(items) != 6:
        raise OriginalMarketError("fixed 6 case watchlist required")
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"id", "category", "url", "scope_category"}:
            raise OriginalMarketError("bad source allowlist record")
        number, category, url = item["id"], item["category"], item["url"]
        if (not isinstance(number, str) or not re.fullmatch(r"\d{7}", number)
                or number == "4643484" or number in seen
                or category not in ALLOWED_CATEGORY
                or item["scope_category"] not in ALLOWED_SCOPE
                or not isinstance(url, str)):
            raise OriginalMarketError("duplicate, prior case or unknown allowed URL")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.netloc != "www.b2b-center.ru"
                or not (parsed.path.startswith("/app/market-next/") or
                        parsed.path.startswith("/market/"))
                or parsed.query or parsed.fragment or not ID_RE.search(parsed.path)
                or ID_RE.search(parsed.path).group(1) != number):
            raise OriginalMarketError("external, off-platform or incorrect exact card")
        seen.add(number)
    return items


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise OriginalMarketError("unexpected redirect")


def fetch_public(url: str) -> bytes:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc != "www.b2b-center.ru"
            or parsed.query or parsed.fragment):
        raise OriginalMarketError("off-platform request")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    opener = urllib.request.build_opener(_NoRedirect)
    with opener.open(request, timeout=16) as resp:
        if resp.status != 200 or resp.geturl() != url:
            raise OriginalMarketError("non-original redirect/source")
        raw = resp.read(MAX_BYTES + 1)
        if not 1200 < len(raw) <= MAX_BYTES:
            raise OriginalMarketError("source size invalid")
        return raw


def _document(raw: bytes):
    if not isinstance(raw, bytes) or not 1200 < len(raw) <= MAX_BYTES:
        raise OriginalMarketError("source missing or over limit")
    return html.fromstring(raw)


def _text(el) -> str:
    return " ".join(el.text_content().split())


def _index_row(raw: bytes, source_url: str) -> dict:
    tree = _document(raw)
    anchors = [a for a in tree.xpath("//a[@href]")
               if a.get("href") == source_url]
    if not anchors:
        raise OriginalMarketError("exact category reference missing")
    rows = []
    for anchor in anchors:
        current = anchor
        for _ in range(10):
            current = current.getparent()
            if current is None:
                break
            text = _text(current)
            if ("Опубликовано:" in text and "Подать заявку до:" in text
                    and len(text) < 2200):
                rows.append(text)
                break
    rows = [row for row in rows if "Закупка №" in row]
    if not rows:
        raise OriginalMarketError("missing numbered original index card")
    observed = set()
    for row in rows:
        day = DATE_RE.findall(row)
        alias = re.search(r"Закупка №\s*([\d/]+)", row)
        if len(set(day)) != 1 or not day or alias is None:
            raise OriginalMarketError("ambiguous original indexed deadline/alias")
        observed.add((day[0], alias.group(1)))
    if len(observed) != 1:
        raise OriginalMarketError("conflicting original deadline/alias")
    display = rows[0]
    found = DATE_RE.findall(display)
    if len(set(found)) != 1 or not found:
        raise OriginalMarketError("ambiguous index deadline")
    dt = datetime.strptime(" ".join(found[0]), "%d.%m.%Y %H:%M").replace(tzinfo=MSK)
    alias = re.search(r"Закупка №\s*([\d/]+)", display)
    if not alias:
        raise OriginalMarketError("original index procurement ID missing")
    return {
        "index_displayed_purchase_number": alias.group(1),
        "index_published_deadline_moscow": dt.isoformat(),
        "index_budget_literal": (
            "0,00 ₽ - INDEX PLACEHOLDER NOT BUYER PRICE"
            if "Начальная цена 0,00 ₽" in display else "UNKNOWN"
        ),
    }


def _detail_row(raw: bytes, number: str) -> dict:
    tree = _document(raw)
    title = " ".join(tree.xpath("//title/text()"))
    if f"Тендер № {number}" not in title:
        raise OriginalMarketError("current detail page identity mismatched")
    for el in tree.xpath("//style|//script|//noscript|//svg"):
        el.drop_tree()
    visible = [" ".join(s.split()) for s in tree.xpath("//text()") if s.strip()]
    numbers = [v for v in visible[:85] if v == f"№ {number}"]
    status = [v for v in visible[:90] if v in PUBLIC_STAGES]
    times = [m.groups() for s in visible[:90] if (m := DETAIL_DEADLINE_RE.fullmatch(s))]
    if not numbers or len(status) != 1 or len(times) != 1:
        raise OriginalMarketError("unknown direct-card stage or identity")
    kind, day, clock = times[0]
    dt = datetime.strptime(day + " " + clock, "%d.%m.%Y %H:%M").replace(tzinfo=MSK)
    organizer_idx = visible.index("Организатор") if "Организатор" in visible[:100] else None
    organizer = visible[organizer_idx + 1] if organizer_idx is not None else "UNKNOWN"
    return {
        "original_page_title": title[:260],
        "original_displayed_organizer": organizer[:240],
        "static_progress_label": status[0],
        "header_time_qualifier": kind,
        "header_time_moscow": dt.isoformat(),
        "original_total_purchase_price_verified": False,
    }


def evaluate(item: dict, index: bytes, detail: bytes, observed: datetime) -> dict:
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise OriginalMarketError("naive time")
    category_url = INDEX.format(category=item["category"])
    raw_index = _index_row(index, item["url"])
    raw_detail = _detail_row(detail, item["id"])
    end = datetime.fromisoformat(raw_index["index_published_deadline_moscow"])
    visible = datetime.fromisoformat(raw_detail["header_time_moscow"])
    if raw_detail["header_time_qualifier"] == "до" and visible != end:
        raise OriginalMarketError("platform deadline differs between first-party pages")
    if raw_index["index_displayed_purchase_number"] != item["id"]:
        raise OriginalMarketError("INDEX_NUMBER_ALIAS_REQUIRES_REVIEW")
    if raw_detail["header_time_qualifier"] == "с" and end >= observed:
        raise OriginalMarketError("page since-stage contradicts future deadline")
    if raw_detail["header_time_qualifier"] == "до" and end > observed and raw_detail["static_progress_label"] in {"Приём заявок", "Прием заявок"}:
        stage = "PUBLIC_DEADLINE_FUTURE_AND_VISIBLE_ACCEPTING"
    else:
        stage = "NOT_PUBLICLY_ACCEPTING_AS_OF_CAPTURE"
    scope = item["scope_category"]
    if stage != "PUBLIC_DEADLINE_FUTURE_AND_VISIBLE_ACCEPTING":
        gate = "EXCLUDE_PAST_OR_NONACCEPTING_PUBLIC_DEADLINE"
    elif scope == "MARKET_RESEARCH_RFI":
        gate = "RFI_MARKET_RESEARCH_NOT_CONTRACT_AWARD"
    elif scope == "LICENSE_RENEWAL_NON_DEVELOPMENT":
        gate = "EXCLUDE_LICENSE_RESALE_NOT_SOFTWARE_DEVELOPMENT"
    else:
        gate = "TECHNICAL_FIT_AND_OWNER_ELIGIBILITY_REVIEW"
    return {
        "id": item["id"],
        "primary_platform": "B2B_CENTER",
        "exact_category_url": category_url,
        "exact_original_card_url": item["url"],
        "category_html_sha256": _sha(index),
        "detail_html_sha256": _sha(detail),
        "category_html_bytes": len(index),
        "detail_html_bytes": len(detail),
        "observed_at_utc": observed.astimezone(UTC).isoformat(),
        "original_http_status": 200,
        **raw_index, **raw_detail,
        "public_deadline_assessment": stage,
        "case_scope_classification": scope,
        "source_gate": gate,
        "prior_original_primary_id": False,
        "bidder_legal_eligibility_verified": False,
        "platform_fee_and_account_access_verified": False,
        "commercial_budget_verified": False,
        "all_customer_documents_read": False,
        "owner_bid_go": False,
        "external_actions_taken": False,
    }


def audit(watchlist: list[dict], *, fetch=fetch_public, now: datetime) -> dict:
    items = validate_watchlist(watchlist)
    indexes: dict[str, bytes | None] = {}
    for category in sorted({item["category"] for item in items}):
        try:
            indexes[category] = fetch(INDEX.format(category=category))
        except (OSError, TimeoutError, urllib.error.URLError, OriginalMarketError):
            indexes[category] = None
    rows = []
    for item in items:
        original_index = indexes[item["category"]]
        original_detail: bytes | None = None
        source_failure = None
        try:
            if original_index is None:
                raise OriginalMarketError("FIRST_PARTY_CATEGORY_UNAVAILABLE")
            original_detail = fetch(item["url"])
            entry = evaluate(item, original_index, original_detail, now)
        except (OSError, TimeoutError, urllib.error.URLError, OriginalMarketError) as exc:
            source_failure = (
                str(exc) if isinstance(exc, OriginalMarketError)
                else "FIRST_PARTY_DETAIL_TRANSPORT_UNAVAILABLE"
            )
            separately_parsed_index = {}
            if original_index:
                try:
                    separately_parsed_index = _index_row(original_index, item["url"])
                except OriginalMarketError:
                    pass
            entry = {
                "id": item["id"],
                **separately_parsed_index,
                "exact_category_url": INDEX.format(category=item["category"]),
                "exact_original_card_url": item["url"],
                "observed_at_utc": now.astimezone(UTC).isoformat(),
                "category_html_sha256": _sha(original_index) if original_index else None,
                "detail_html_sha256": _sha(original_detail) if original_detail else None,
                "category_html_bytes": len(original_index) if original_index else None,
                "detail_html_bytes": len(original_detail) if original_detail else None,
                "original_http_status": 200 if original_detail else "UNAVAILABLE",
                "source_parse_state": "UNVERIFIED_FAIL_CLOSED",
                "source_failure_code": source_failure,
                "source_gate": "SOURCE_IDENTITY_OR_STAGE_REQUIRES_REVIEW",
                "bidder_legal_eligibility_verified": False,
                "platform_fee_and_account_access_verified": False,
                "commercial_budget_verified": False,
                "all_customer_documents_read": False,
                "owner_bid_go": False,
                "external_actions_taken": False,
            }
        rows.append(entry)
    return {
        "contract_version": "b2b_center_six_original_oct18_v1",
        "observed_at_utc": now.astimezone(UTC).isoformat(),
        "source_platform": "original_public_b2b_center_exact_category_and_detail",
        "known_prior_primary_id_excluded": "4643484",
        "attempted_explicit_original_cards": len(rows),
        "original_public_http200_card_pages_checked": sum(
            r["original_http_status"] == 200 for r in rows
        ),
        "source_identity_and_stage_parsed_count": sum(
            r.get("source_parse_state") != "UNVERIFIED_FAIL_CLOSED" for r in rows
        ),
        "strictly_qualified_current_company_bid_count": 0,
        "goal_15_to_20_reached": False,
        "market_research_active_count": sum(r["source_gate"] == "RFI_MARKET_RESEARCH_NOT_CONTRACT_AWARD" for r in rows),
        "license_resale_excluded_count": sum(r["source_gate"] == "EXCLUDE_LICENSE_RESALE_NOT_SOFTWARE_DEVELOPMENT" for r in rows),
        "past_or_nonaccepting_count": sum(r["source_gate"] == "EXCLUDE_PAST_OR_NONACCEPTING_PUBLIC_DEADLINE" for r in rows),
        "source_origin_only_no_submissions_or_fees": True,
        "items": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    result = audit(json.loads(WATCH.read_text(encoding="utf8")), now=datetime.now(UTC))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print("FIRSTPARTY", len(result["items"]), "RFI", result["market_research_active_count"],
          "LICENSE", result["license_resale_excluded_count"], "PAST", result["past_or_nonaccepting_count"],
          "COMPANY_GO", result["strictly_qualified_current_company_bid_count"])


if __name__ == "__main__":
    raise SystemExit(main())
