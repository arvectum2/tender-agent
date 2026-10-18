"""Read-only original Workspace public-card status snapshot; never bid/submit.

Explicit known-card allowlist only. Captures HTTP and exact original HTML SHA,
with conservative fail-closed status/organizer/deadline interpretation. The
on-platform agency entitlement and current legal buyer eligibility are NEVER
inferred from public cards.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

_RE_ID = re.compile(r"-(\d{4,6})/\Z")
_RE_CANONICAL_PATH = re.compile(r"/tenders/[a-z0-9-]+-\d{4,6}/\Z")
_RE_HEADING = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.DOTALL | re.IGNORECASE)
_RE_STATUS = re.compile(r'<div[^>]*class="[^"]*tendercart-type__status-public[^"]*"[^>]*>(.*?)</div>', re.DOTALL)
_RE_FIELD = re.compile(
    r'<div\s+class="b-tender__info-item-title">([^<]+)</div>\s*'
    r'<div\s+class="b-tender__info-item-text">(.*?)</div>', re.DOTALL
)
_RE_ORG = re.compile(
    r'<div\s+class="card-info__title">Oрганизатор</div>\s*'
    r'<p\s+class="card-info__desc">(.*?)</p>', re.DOTALL
)
_TAG = re.compile(r"<[^>]+>")
_RUS_MONTH = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
_RE_DATE = re.compile(r"\A(\d{1,2})\s+([а-яё]+)\s+(\d{4})\Z")
_ALLOWED_STATUSES = {"Идет прием заявок", "Прием заявок завершен", "Завершён"}
_ALLOWED_ORGANIZERS = {"Юридическое лицо", "Частное лицо"}
_MAX_BYTES = 280000


class PublicSourceError(ValueError):
    """Refuse to trust ambiguous primary-source content."""


def _plain(value: str) -> str:
    return " ".join(html.unescape(_TAG.sub("", value)).split())


def _unique_value(pattern: re.Pattern, page: str, label: str) -> str:
    hits = [_plain(m.group(1)) for m in pattern.finditer(page)]
    if len(hits) != 1 or not hits[0]:
        raise PublicSourceError(f"ambiguous_or_missing_{label}")
    return hits[0]


def _fields(page: str) -> dict[str, str]:
    result = {}
    for m in _RE_FIELD.finditer(page):
        name, value = _plain(m.group(1)).rstrip(":"), _plain(m.group(2))
        if name in result:
            raise PublicSourceError("duplicate_public_field")
        result[name] = value
    return result


def date_from_original(text: str) -> str:
    match = _RE_DATE.fullmatch(text)
    if match is None or match.group(2) not in _RUS_MONTH:
        raise PublicSourceError("unparseable_public_deadline")
    try:
        return date(int(match.group(3)), _RUS_MONTH[match.group(2)], int(match.group(1))).isoformat()
    except ValueError as exc:
        raise PublicSourceError("invalid_public_deadline") from exc


def classify_original_page(page: bytes, *, source_url: str, observed_at: datetime) -> dict:
    url = urlsplit(source_url)
    if (url.scheme != "https" or url.netloc != "workspace.ru"
            or not _RE_CANONICAL_PATH.fullmatch(url.path) or url.query or url.fragment
            or not _RE_ID.search(url.path)):
        raise PublicSourceError("untrusted_source_url")
    if not 0 < len(page) <= _MAX_BYTES:
        raise PublicSourceError("source_body_size_out_of_bounds")
    try:
        source = page.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PublicSourceError("unreadable_source_bytes") from exc
    status = _unique_value(_RE_STATUS, source, "platform_status")
    if status not in _ALLOWED_STATUSES:
        raise PublicSourceError("unrecognized_platform_status")
    organizer = _unique_value(_RE_ORG, source, "organizer_type")
    if organizer not in _ALLOWED_ORGANIZERS:
        raise PublicSourceError("unrecognized_organizer_type")
    title = _unique_value(_RE_HEADING, source, "tender_title")
    fields = _fields(source)
    published = fields.get("Опубликован", "")
    deadline = date_from_original(fields.get("Крайний срок приема заявок", ""))
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise PublicSourceError("observation_without_timezone")
    as_of = observed_at.astimezone(ZoneInfo("Europe/Moscow")).date().isoformat()
    is_current_card = status == "Идет прием заявок" and deadline >= as_of
    is_corporate = organizer == "Юридическое лицо"
    if not is_corporate:
        gate = "EXCLUDE_PRIVATE_BUYER"
    elif status != "Идет прием заявок":
        gate = "EXCLUDE_TERMINAL_PLATFORM_STATUS"
    elif deadline < as_of:
        gate = "EXCLUDE_PAST_PRINTED_DEADLINE"
    else:
        gate = "PUBLIC_CORPORATE_CANDIDATE_ONLY"
    return {
        "id": "workspace-" + _RE_ID.search(url.path).group(1),
        "source_kind": "FIRST_PARTY_PUBLIC_WORKSPACE_CARD",
        "source_url": source_url,
        "source_http_status": 200,
        "source_html_sha256": hashlib.sha256(page).hexdigest(),
        "source_html_bytes": len(page),
        "observed_at_utc": observed_at.astimezone(UTC).isoformat(),
        "compared_date_in_moscow": as_of,
        "title_from_original": title,
        "published_original_label": published or "UNKNOWN",
        "platform_status": status,
        "organizer_type": organizer,
        "printed_deadline_date": deadline,
        "printed_deadline_exact_time": "UNKNOWN",
        "budget_original_label": fields.get("Бюджет") or "UNKNOWN",
        "source_gate": gate,
        "publicly_accepting_as_printed": is_current_card,
        "public_corporate_candidate": gate == "PUBLIC_CORPORATE_CANDIDATE_ONLY",
        "business_fit": "REVIEW_REQUIRED",
        "authenticated_legal_entity_bidder_verified": False,
        "self_selected_reply_requires_pro_or_invitation": "OWNER_ACCOUNT_CONFIRMATION_REQUIRED",
        "active_eis_etp_legal_status_verified": False,
        "commercial_go": False,
        "external_actions_taken": False,
    }


def validated_urls(data: object) -> list[str]:
    if not isinstance(data, list) or not 1 <= len(data) <= 40:
        raise PublicSourceError("source allowlist missing or excessive")
    checked = set()
    urls = []
    for item in data:
        if not isinstance(item, str):
            raise PublicSourceError("bad source URL type")
        parsed = urlsplit(item)
        if (parsed.scheme != "https" or parsed.netloc != "workspace.ru"
                or not _RE_CANONICAL_PATH.fullmatch(parsed.path)
                or parsed.query or parsed.fragment
                or item in checked):
            raise PublicSourceError("unsupported or repeated source URL")
        checked.add(item)
        urls.append(item)
    return urls


def capture(urls: list[str], *, fetch, now: datetime) -> dict:
    results = []
    for url in validated_urls(urls):
        try:
            blob = fetch(url)
            record = classify_original_page(blob, source_url=url, observed_at=now)
        except (PublicSourceError, ValueError, OSError, urllib.error.URLError) as exc:
            record = {
                "id": "workspace-" + _RE_ID.search(urlsplit(url).path).group(1),
                "source_url": url,
                "source_http_status": "UNAVAILABLE_OR_UNVERIFIED",
                "source_gate": "UNKNOWN_FAIL_CLOSED",
                "error_kind": type(exc).__name__,
                "public_corporate_candidate": False,
                "authenticated_legal_entity_bidder_verified": False,
                "commercial_go": False,
            }
        results.append(record)
    ids = [x["id"] for x in results]
    if len(ids) != len(set(ids)):
        raise PublicSourceError("duplicate tender id from original pages")
    return {
        "contract_version": "b2b_workspace_firstparty_public_originals_v1",
        "observed_at_utc": now.astimezone(UTC).isoformat(),
        "total_explicit_prior_or_new_watchlist_ids": len(ids),
        "firstparty_http200_cards_parsed": sum(x["source_http_status"] == 200 for x in results),
        "public_corporate_source_candidates": sum(x["public_corporate_candidate"] for x in results),
        "strict_owner_qualified_bid_opportunities": 0,
        "target_15_20_fully_qualified_met": False,
        "first_party_source_legal_eligibility_unknown": True,
        "commercial_external_submissions": 0,
        "paid_access_purchases": 0,
        "items": results,
    }


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise PublicSourceError("redirected_original_source_not_permitted")


def read_public(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    opener = urllib.request.build_opener(_NoRedirect)
    with opener.open(request, timeout=13) as response:
        if response.status != 200 or response.geturl() != url:
            raise PublicSourceError("non_original_or_redirected_card")
        body = response.read(_MAX_BYTES + 1)
        if len(body) > _MAX_BYTES:
            raise PublicSourceError("oversized_original_card")
        return body


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--allowlist", type=Path, required=True)
    cli.add_argument("--live", action="store_true")
    cli.add_argument("--output", type=Path)
    args = cli.parse_args()
    if not args.live:
        cli.error("Original site GET requires explicit --live; no cached synthetic card may be reported as current")
    urls = validated_urls(json.loads(args.allowlist.read_text()))
    data = capture(urls, fetch=read_public, now=datetime.now(UTC))
    if args.output:
        args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
