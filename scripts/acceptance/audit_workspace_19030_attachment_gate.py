"""Public, read-only original Workspace 19030 file availability, never private download."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

if __package__ in (None, "") and __file__ != "<stdin>":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.acceptance.audit_schlam_offer_original_oct17 import _Markup
from scripts.acceptance.audit_workspace_oct17_cards import extract_public_card
from src.tender_research.corporate_lead_gate import qualify_llc_response

SLUG = "vnedrenie-ii-sistemy-ucheta-syrya-sklada-i-proizvodstva-dlya-proizvoditelya-sellera-wb-i-ozon"
ORIGINAL_URL = f"https://workspace.ru/tenders/{SLUG}-19030/"
ACCESS_NOTICE = (
    "Файлы для скачивания доступны участникам с PRO-аккаунтом и исполнителям,"
    " которых пригласил в тендер заказчик."
)
MAX_BYTES = 400_000


def _normalized(value: str) -> str:
    return " ".join(value.casefold().replace("ё", "е").split())


def evaluate_original(data: bytes, *, observed_at: datetime) -> dict:
    if observed_at.utcoffset() is None:
        raise ValueError("observation needs a timezone")
    if not 300 <= len(data) <= MAX_BYTES:
        raise ValueError("invalid source size")
    card = extract_public_card(
        data, key="19030", observed=observed_at,
        allowed_cards={"19030": (SLUG, "2026-11-13", "FIT_HIGH")},
    )
    if card["source_status_gate"] != "PUBLIC_CANDIDATE_ONLY":
        raise ValueError("source not a public corporate accepting card")
    page = data.decode("utf8", "strict")
    panels = re.findall(
        r'<div class="tendercard__title">Файлы к тендеру(.*?)'
        r'<div class="tendercard__block _border-none">',
        page,
        flags=re.DOTALL,
    )
    if len(panels) != 1:
        raise ValueError("original file panel absent/ambiguous")
    source = _Markup()
    source.feed(page)
    text = _normalized(source.text)
    if _normalized("Подробное ТЗ во вложении.") not in text:
        raise ValueError("original refers to a different specification")
    visible = _Markup()
    visible.feed(panels[0])
    if _normalized(ACCESS_NOTICE) not in _normalized(visible.text):
        raise ValueError("original attached document access wording changed")
    if len(re.findall(r'<div class="tendercard__file" title="TZ_.pdf">', panels[0])) != 1:
        raise ValueError("expected named PDF attachment listing not attested")
    if re.search(r'\bhref\s*=', panels[0], re.IGNORECASE):
        # An HTML link is only a changed public markup, never permit auto-download.
        raise ValueError("attachment panel changed; manually review before any fetch")
    sha = hashlib.sha256(data).hexdigest()
    legal = qualify_llc_response({
        "source_url": ORIGINAL_URL,
        "platform_status": card["platform_status"],
        "organizer_type": card["organizer_type"],
        "source_observed_at": observed_at.isoformat(),
        "submission_deadline": "2026-11-13",
    }, checked_at=observed_at, source_sha256=sha, source_http_status=200)
    if legal.response_authorized:
        raise ValueError("private gate unexpectedly open")
    return {
        "schema_version": "workspace-19030-first-party-attachment-gate-v1",
        "source_url": ORIGINAL_URL,
        "original_source_http": 200,
        "observed_at_utc": observed_at.astimezone(UTC).isoformat(),
        "source_html_sha256": sha,
        "source_html_bytes": len(data),
        "public_status": card["platform_status"],
        "public_organizer": card["organizer_type"],
        "printed_deadline_date": "2026-11-13",
        "printed_deadline_clock": "UNKNOWN",
        "original_attachment_listed_name": "TZ_.pdf",
        "original_access_rule": "PRO_ACCOUNT_OR_CUSTOMER_INVITATION",
        "public_unauthenticated_direct_attachment_href_in_panel": False,
        "pdf_downloaded": False,
        "pdf_bytes_verified": False,
        "detailed_tz_text_read": False,
        "company_workspace_pro_or_invitation_verified": False,
        "company_bid_eligibility_state": legal.state,
        "llc_unresolved_gates": list(legal.blockers),
        "technical_scope_complete": False,
        "pilot_quote_authorized": False,
        "owner_bid_go": False,
        "outbound_actions_or_payments": 0,
    }


def collect() -> dict:
    opener = build_opener(ProxyHandler({}))
    with opener.open(
        Request(ORIGINAL_URL, headers={"User-Agent": "ArvectumTenderAgent-SourceResearch/1.0"}),
        timeout=12,
    ) as response:
        if response.status != 200 or response.geturl() != ORIGINAL_URL:
            raise ValueError("source unavailable or redirected")
        page = response.read(MAX_BYTES + 1)
    return evaluate_original(page, observed_at=datetime.now(UTC))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = collect()
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print("19030_PUBLIC_ATTACHMENT", result["original_attachment_listed_name"],
          "PDF_READ", result["pdf_bytes_verified"],
          "ACCESS", result["original_access_rule"])


if __name__ == "__main__":
    main()
