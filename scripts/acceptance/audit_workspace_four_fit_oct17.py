"""Read-only original Workspace source verification; never submits or unlocks PRO."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

if __package__ in (None, "") and __file__ != "<stdin>":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.acceptance.audit_workspace_oct17_cards import _CARDS, extract_public_card

_CASES = {
    "19030": (
        "CONDITIONAL_AI_PILOT_SPEC_ATTACHMENT_GATED",
        "Производитель орехов и сухофруктов.",
        "около 200 заказов в день",
        "50 SKU",
        "Оплата за каждый этап после запуска.",
        "Подробное ТЗ во вложении.",
    ),
    "19032": (
        "CONDITIONAL_WORDPRESS_MONTHLY_SLA_AND_PORTFOLIO",
        "на WordPress",
        "мониторинг доступности сайта, SSL, домена",
        "срок реакции на сбои",
        "стоимость: за регулярное сопровождение",
    ),
    "19042": (
        "THREE_YEAR_COMMERCIAL_EXPERIENCE_GATE",
        "Коммерческий опыт разработки от 3 лет.",
        "Наличие портфолио завершённых проектов.",
        "Присвоение инвентарных номеров и использование QR-кодов.",
        "Передача исходного кода, базы данных и технической документации",
    ),
    "19043": (
        "MANDATORY_RELEVANT_PORTFOLIO_AND_DISCOVERY_GATE",
        "Наличие релевантных реализованных проектов обязательно.",
        "сохранить накопленный SEO-потенциал",
        "2 варианта реализации",
        "Предварительную стоимость работ с разбивкой",
    ),
}


def collect() -> dict:
    opener = build_opener(ProxyHandler({}))
    cases = []
    for number, (gate, *anchors) in _CASES.items():
        slug, _, _ = _CARDS[number]
        url = f"https://workspace.ru/tenders/{slug}-{number}/"
        with opener.open(
            Request(url, headers={"User-Agent": "ArvectumTenderAgent-SourceResearch/1.0"}),
            timeout=12,
        ) as response:
            if response.status != 200 or response.geturl() != url:
                raise ValueError(f"source {number} unavailable/redirected")
            original = response.read(400_001)
        checked = datetime.now(UTC)
        card = extract_public_card(original, key=number, observed=checked)
        if (card["platform_status"] != "Идет прием заявок" or
            card["organizer_type"] != "Юридическое лицо" or
            card["visibility"] != "public"):
            raise ValueError(f"original {number} cannot be treated as corporate candidate")
        stripped = " ".join(
            html.unescape(re.sub(r"<[^>]+>", " ", original.decode("utf8", "strict"))).split()
        )
        missing = [a for a in anchors if a.casefold() not in stripped.casefold()]
        if missing:
            raise ValueError(f"source {number} missing required public evidence: {missing}")
        cases.append({
            "id": number,
            "source_url": url,
            "checked_at_utc": checked.isoformat(),
            "original_html_sha256": hashlib.sha256(original).hexdigest(),
            "original_html_size": len(original),
            "original_http_status": 200,
            "original_public_status": card["platform_status"],
            "original_public_organizer_type": card["organizer_type"],
            "original_public_deadline_date": card["application_deadline_date"],
            "original_public_deadline_clock": "UNKNOWN",
            "original_public_evidence_literals": anchors,
            "conservative_qualification_gate": gate,
            "customer_legal_identity_by_inn_verified": False,
            "company_portfolio_accepted": False,
            "workspace_pro_or_invitation_for_company_verified": False,
            "hidden_spec_attachments_inspected": False,
            "submission_authorized": False,
            "owner_bid_go": False,
            "no_external_actions": True,
        })
    return {
        "schema_version": "arvectum-workspace-four-first-party-fit-20261017-v1",
        "as_of": "2026-10-17",
        "distinct_cards": len(cases),
        "platform_public_open_snapshot_count": len(cases),
        "current_paid_access_confirmed": 0,
        "company_eligibility_confirmed": 0,
        "owner_bid_go_count": 0,
        "source_status_snapshot_not_contract_availability": True,
        "cases": cases,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if args.out.name != "b2b_workspace_four_original_fit_2026-10-17.json":
        p.error("dated source-only receipt filename required")
    report = collect()
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("WORKSPACE_FOUR_SOURCE_VERIFIED", report["distinct_cards"], "BID_GO", report["owner_bid_go_count"])


if __name__ == "__main__":
    main()
