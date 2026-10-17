"""Read-only bounded exact-card audit; no account, login, proposal, or paid files.

Never infer bid eligibility from an 'accepting applications' public label.
Only exact whitelisted public Workspace URLs. Stores source hash, not HTML.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

if __package__ in (None, "") and __file__ != "<stdin>":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.tender_research.corporate_lead_gate import triage_corporate_card

_CARDS = {
    "19043": ("obnovlenie-sayta-digital-agentstva-audit-redizayn-ili-razrabotka-novogo-korporativnogo-sayta", "2026-10-31", "FIT_HIGH"),
    "19042": ("sistema-avtomatizacii-i-ucheta-oborudovaniya-dlya-myasokombinata", "2026-10-31", "FIT_HIGH"),
    "19034": ("sozdanie-i-prodvizhenie-sayta-kliningovoy-kompanii", "2026-10-31", "FIT_MIXED_WEB_AND_MARKETING"),
    "19032": ("teh-obsluzhivanie-i-dorabotka-korporativnogo-sayta", "2026-10-21", "FIT_HIGH"),
    "19030": ("vnedrenie-ii-sistemy-ucheta-syrya-sklada-i-proizvodstva-dlya-proizvoditelya-sellera-wb-i-ozon", "2026-11-13", "FIT_HIGH"),
    "19052": ("sozdat-internet-magazin-bez-oplaty-na-sayte", "2026-10-23", "EXCLUDE_PERSONAL_ORGANIZER"),
    "19035": ("razrabotka-3-svyazannyh-saytov-dlya-prodavca-avtozapchastey-sayt-vizitka-roznichnyy-internet-magazin-i-optovyy-magazin-s-lk", "2026-10-21", "EXCLUDE_PERSONAL_ORGANIZER"),
    "19023": ("private-tender", "2026-10-20", "EXCLUDE_TERMINAL_STATUS_DUPLICATE"),
}
_MONTHS = {
    "января": "01", "февраля": "02", "марта": "03", "апреля": "04",
    "мая": "05", "июня": "06", "июля": "07", "августа": "08",
    "сентября": "09", "октября": "10", "ноября": "11", "декабря": "12",
}
_BODY_BYTES = 400_000


def _single(text: str, pattern: str, why: str) -> str:
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    if len(matches) != 1:
        raise ValueError(f"cannot uniquely attest {why} on exact original card")
    return matches[0].strip()


def _date(text: str, expected: str) -> str:
    marker = "Крайний срок приема заявок:"
    if text.count(marker) != 1:
        raise ValueError("deadline label not unique on original card")
    window = re.sub(r"<[^>]+>", " ", text.split(marker, 1)[1][:280])
    value = _single(window, r"\b(\d{1,2}\s+[А-Яа-яё]+\s+20\d\d)\b", "deadline")
    parts = value.casefold().split()
    try:
        got = f"{parts[2]}-{_MONTHS[parts[1]]}-{int(parts[0]):02d}"
    except (KeyError, IndexError, ValueError) as exc:
        raise ValueError("unparseable first-party date") from exc
    if got != expected:
        raise ValueError("first-party deadline changed relative to expected evidence")
    return got


def extract_public_card(source: bytes, *, key: str, observed: datetime) -> dict:
    """Parse only the original card's anchored status/organizer fields."""
    if key not in _CARDS or len(source) > _BODY_BYTES:
        raise ValueError("unexpected source/size")
    content = source.decode("utf-8", "strict")
    status = _single(
        content, r'class="tendercart-type__status-public[^"]*"\s*>\s*([^<]+)\s*</div>',
        "card status",
    )
    visibility = _single(
        content, r'class="reference\s+_(public|private)"\s*>',
        "public/private card visibility",
    )
    marker = "Oрганизатор"
    if content.count(marker) != 1:
        raise ValueError("original organizer label ambiguous")
    block = re.sub(r"<[^>]+>", " ", content.split(marker, 1)[1][:480])
    organizer = _single(block, r"\b(Юридическое лицо|Частное лицо)\b", "organizer type")
    deadline = _date(content, _CARDS[key][1])
    title_html = _single(content, r"<h1[^>]*>\s*(.*?)\s*</h1>", "card title")
    title = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", title_html)).split())
    if "<" in title or ">" in title or not 5 < len(title) < 400:
        raise ValueError("original card title unexpectedly contains markup")
    url = f"https://workspace.ru/tenders/{_CARDS[key][0]}-{key}/"
    if urlsplit(url).hostname != "workspace.ru":
        raise ValueError("unexpected source")
    source_evidence = {
        "source_url": url,
        "organizer_type": organizer,
        "platform_status": status,
        "source_observed_at": observed.isoformat(),
        "submission_deadline": deadline,
    }
    result = triage_corporate_card(source_evidence, checked_at=observed)
    if visibility != "public" and result.state == "PUBLIC_CANDIDATE_ONLY":
        raise ValueError("private card cannot count as public candidate")
    if _CARDS[key][2].startswith("EXCLUDE") and result.state == "PUBLIC_CANDIDATE_ONLY":
        raise ValueError("expected excluded card was unexpectedly promoted")
    if not _CARDS[key][2].startswith("EXCLUDE") and result.state != "PUBLIC_CANDIDATE_ONLY":
        raise ValueError("previously corporate original card no longer currently accepting")
    return {
        "id": "workspace-" + key,
        "source_kind": "ORIGINAL_PUBLIC_WORKSPACE_CARD",
        "source_url": url,
        "title": title,
        "checked_at": observed.isoformat(),
        "platform_status": status,
        "organizer_type": organizer,
        "visibility": visibility,
        "application_deadline_date": deadline,
        "application_deadline_time": "UNKNOWN",
        "source_http_status": 200,
        "original_source_html_size": len(source),
        "original_source_html_sha256": hashlib.sha256(source).hexdigest(),
        "competitive_fit": _CARDS[key][2],
        "source_status_gate": result.state,
        "source_status_reason": result.reason,
        "bid_ready": False,
        "agency_eligibility": "UNVERIFIED",
        "paid_pro_or_invitation_gate": "REQUIRES_OWNER_CONFIRMATION",
        "human_go": False,
        "no_external_action": True,
    }


def collect() -> dict:
    opener = build_opener(ProxyHandler({}))
    cards = []
    for key, (slug, _, _) in _CARDS.items():
        url = f"https://workspace.ru/tenders/{slug}-{key}/"
        req = Request(url, headers={"User-Agent": "ArvectumTenderAgent-SourceResearch/1.0"})
        try:
            with opener.open(req, timeout=12) as response:
                if response.status != 200 or response.geturl() != url:
                    raise ValueError(f"unexpected original source redirect/status for {key}: {response.status} {response.geturl()}")
                raw = response.read(_BODY_BYTES + 1)
        except (URLError, HTTPError) as exc:
            raise ValueError("official card public read unavailable") from exc
        observed = datetime.now(UTC)
        cards.append(extract_public_card(raw, key=key, observed=observed))
    eligible = [x for x in cards if x["source_status_gate"] == "PUBLIC_CANDIDATE_ONLY"]
    excluded = [x for x in cards if x["source_status_gate"] != "PUBLIC_CANDIDATE_ONLY"]
    if len(eligible) != 5 or len(excluded) != 3:
        raise ValueError("unexpected original card source coverage")
    return {
        "schema_version": "b2b-workspace-original-oct17-v1",
        "audit_date": "2026-10-17",
        "source": "read_only_direct_original_public_workspace_cards",
        "prior_original_verified_distinct_count": "historical_only_not_necessarily_open",
        "new_distinct_corporate_original_cards": len(eligible),
        "excluded_or_closed_cards": len(excluded),
        "current_public_source_candidates": eligible,
        "excluded_cards": excluded,
        "all_current_procurement_goal_15_20_met": False,
        "actual_bid_eligibility_verified": False,
        "paid_pro_or_invitation_checked": False,
        "no_registration_submission_or_payments": True,
        "original_platform_status_is_snapshot_not_future_guarantee": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.out and args.out.name != "b2b_workspace_original_2026-10-17.json":
        parser.error("only the versioned research source receipt path is permitted")
    try:
        result = collect()
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print("SOURCE_ATTESTED", result["new_distinct_corporate_original_cards"],
          "EXCLUDED", result["excluded_or_closed_cards"],
          "BID_READY", result["actual_bid_eligibility_verified"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
