"""Read-only original Workspace 19006 + PREEXISTING Arvectum /schlam proposal QA.

No new site, unsolicited bid, payment, registration, signed URL, or new UI.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import ProxyHandler, Request, build_opener

if __package__ in (None, "") and __file__ != "<stdin>":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.acceptance.audit_workspace_oct17_cards import extract_public_card

_KEY = "19006"
_SLUG = "sozdanie-i-dalneyshee-razvitie-sayta-specializirovannoy-kompanii-po-rabotam-na-vode-i-trudnodostupnyh-obektah"
_WORKSPACE = f"https://workspace.ru/tenders/{_SLUG}-{_KEY}/"
_SITE = "https://arvectum.com"
_PATHS = ("/schlam/", "/schlam/market/", "/schlam/offer/",
          "/schlam/brief/", "/schlam/equipment/", "/schlam/crm/")


class _Markup(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []
        self.robots: list[str] = []
        self.parts: list[str] = []
        self.suppressed = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = dict(attrs)
        if tag in ("script", "style"):
            self.suppressed += 1
        if tag == "meta" and d.get("name", "").lower() == "robots":
            self.robots.append(d.get("content", "") or "")
        for key in ("href", "src"):
            if d.get(key):
                self.urls.append(d[key] or "")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self.suppressed = max(0, self.suppressed - 1)

    def handle_data(self, data: str) -> None:
        if not self.suppressed:
            self.parts.append(data)

    @property
    def text(self) -> str:
        return " ".join(html.unescape(" ".join(self.parts)).split())


def collect() -> dict:
    opener = build_opener(ProxyHandler({}))
    def read(url: str, cap: int = 140_000, min_bytes: int = 100) -> bytes:
        p = urlsplit(url)
        if (p.scheme != "https" or p.hostname not in ("arvectum.com", "workspace.ru")
            or p.username is not None or p.password is not None):
            raise ValueError("unapproved read-only source")
        req = Request(url, headers={"User-Agent": "ArvectumTenderAgent-SourceReadOnly/1.0"})
        with opener.open(req, timeout=11) as response:
            if response.status != 200 or response.geturl() != url:
                raise ValueError("unexpected source HTTP/redirect")
            original = response.read(cap + 1)
        if not min_bytes <= len(original) <= cap:
            raise ValueError("source length invalid")
        return original

    source = read(_WORKSPACE, 400_000)
    checked = datetime.now(UTC)
    card = extract_public_card(
        source, key=_KEY, observed=checked,
        allowed_cards={_KEY: (_SLUG, "2026-11-01", "FIT_HIGH")},
    )
    s = _Markup()
    s.feed(source.decode("utf8", "strict"))
    requirements = (
        "Нужен специалист",
        "кто наши реальные прямые и косвенные конкуренты",
        "разобраться в теме и предложить",
        "Подробное техническое задание намеренно пока не формируем.",
        "Бюджет: 130 000 - 400 000 рублей",
    )
    for phrase in requirements:
        if phrase.casefold() not in s.text.casefold():
            raise ValueError("original 19006 public requirement no longer attested")
    if card["platform_status"] != "Идет прием заявок" or card["organizer_type"] != "Юридическое лицо":
        raise ValueError("original 19006 is no longer an accepting corporate public card")

    pages = []
    links: set[str] = set()
    for path in _PATHS:
        url = _SITE + path
        data = read(url)
        parser = _Markup()
        parser.feed(data.decode("utf8", "strict"))
        if len(parser.robots) != 1 or "noindex" not in parser.robots[0].lower():
            raise ValueError("existing private demo must retain noindex")
        if path == "/schlam/offer/":
            for exact in ("89 000 ₽", "4–6 недель", "Демонстрационные материалы не являются подтверждением"):
                if exact.casefold() not in parser.text.casefold():
                    raise ValueError("preexisting offer economics/source disclaimer changed")
        pages.append({
            "url": url,
            "html_sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            "http_status": 200,
            "robots_noindex": True,
            "existing_site_unchanged": True,
        })
        for ref in parser.urls:
            target = urljoin(url, ref)
            p = urlsplit(target)
            if p.scheme == "https" and p.netloc == "arvectum.com" and p.path.startswith("/schlam/"):
                links.add(p.scheme + "://" + p.netloc + p.path)
    results = []
    for link in sorted(links):
        data = read(link, min_bytes=1)
        results.append({"url": link, "http_status": 200, "bytes": len(data)})
    return {
        "schema_version": "ta-schlam-original-19006-reuse-qa-v1",
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "original_workspace_card": {
            "url": _WORKSPACE,
            "original_html_sha256": hashlib.sha256(source).hexdigest(),
            "original_html_bytes": len(source),
            "status": card["platform_status"],
            "organizer_type": card["organizer_type"],
            "deadline_date": card["application_deadline_date"],
            "deadline_clock": "UNKNOWN",
            "source_budget_min_rub": 130_000,
            "source_budget_max_rub": 400_000,
            "original_literal_source_requirements": requirements,
        },
        "published_demo_pages": pages,
        "internal_link_checks": results,
        "existing_offer_start_price_rub": 89_000,
        "existing_offer_estimate_weeks": "4–6",
        "existing_offer_below_public_budget_min_not_auto_bad_but_owner_cost_gate": True,
        "site_repo_known": "arvectum2/arvectum-site",
        "company_paid_workspace_access_or_invitation_verified": False,
        "published_demo_not_real_customer_technical_facts": True,
        "bid_ready": False,
        "human_go": False,
        "no_new_site_ui_or_external_action": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.name != "b2b_schlam_19006_original_offer_qa_2026-10-17.json":
        parser.error("expected fixed source-only JSON filename")
    result = collect()
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("ORIGINAL_19006_SOURCE_REUSED",len(result["published_demo_pages"]),
          "noindex_pages",len(result["internal_link_checks"]),"internal_resources",
          "owner_GO",result["human_go"])


if __name__ == "__main__":
    main()
