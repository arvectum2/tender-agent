"""First-party WordPress №19032 requirements: read-only source, no bid/PRO/GO.

This audit is intentionally scoped to one existing validated Workspace URL.
It does not attest the contractor's experience, terms or account access.
"""
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

ROOT = Path(__file__).resolve().parents[2]
SOURCE_URL = (
    "https://workspace.ru/tenders/"
    "teh-obsluzhivanie-i-dorabotka-korporativnogo-sayta-19032/"
)
SOURCE_SLUG = "teh-obsluzhivanie-i-dorabotka-korporativnogo-sayta"
SOURCE_NUMBER = "19032"
SOURCE_CUTOFF_DAY = "2026-10-21"
MAX_SOURCE_BYTES = 400_000
SCOPE_ANCHORS = {
    "recurring_maintenance": (
        "контроль технического состояния сайта: доступность, скорость, ошибки",
        "обновление WordPress, плагинов и темы",
        "проверка совместимости после обновлений",
        "мониторинг на вредоносный код, подозрительные файлы, несанкционированные изменения",
        "настройка и контроль резервного копирования",
        "мониторинг доступности сайта, SSL, домена",
        "формы, меню, ссылки, отправка писем с сайта",
        "оперативное подключение при сбоях",
        "краткий отчёт о состоянии сайта и выполненных работах раз в месяц",
        "консультации по техническим вопросам",
    ),
    "separately_ordered_changes": (
        "доработка архитектуры сайта",
        "доработка отдельных страниц (формы, блоки, вёрстка)",
        "скорость загрузки и оптимизация",
        "интеграции (возможно)",
        "доработки по SEO-части (возможно)",
        "мелкие правки по мере необходимости",
    ),
    "requested_quote_fields": (
        "краткое описание вашего опыта и примеры",
        "за регулярное сопровождение (в месяц / в час)",
        "за разовые доработки (в час / по задаче)",
        "срок реакции на сбои",
        "есть ли опыт с WordPress-сайтами корпоративного уровня",
        "постановка задач, канал связи, отчётность",
    ),
    "additional_questions": (
        "Какая у вас система оплаты и отчетность?",
    ),
}
OTHER_REQUIRED = (
    "контейнерные перевозки",
    "Бюджет: 100 000 - 400 000 рублей",
    "Чтобы участвовать в тендере войдите/зарегистрируйтесь",
)


def _normalize(text: str) -> str:
    return " ".join(text.casefold().replace("ё", "е").split())


def evaluate_original(source: bytes, *, observed_at: datetime) -> dict:
    """Return attested public requirements only; raise if material wording drifted."""
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observation timestamp must be timezone-aware")
    if len(source) > MAX_SOURCE_BYTES or len(source) < 300:
        raise ValueError("public source out of bounds")
    card = extract_public_card(
        source, key=SOURCE_NUMBER, observed=observed_at,
        allowed_cards={SOURCE_NUMBER: (SOURCE_SLUG, SOURCE_CUTOFF_DAY, "FIT_HIGH")},
    )
    if (card["source_status_gate"] != "PUBLIC_CANDIDATE_ONLY" or
        card["visibility"] != "public" or card["organizer_type"] != "Юридическое лицо"):
        raise ValueError("not currently a receiving public legal-entity card")

    markup = _Markup()
    markup.feed(source.decode("utf-8", "strict"))
    original_text = _normalize(markup.text)
    count = {}
    for section, anchors in SCOPE_ANCHORS.items():
        missing = [x for x in anchors if _normalize(x) not in original_text]
        if missing:
            raise ValueError(f"missing first-party {section} requirement anchors")
        count[section] = len(anchors)
    if any(_normalize(x) not in original_text for x in OTHER_REQUIRED):
        raise ValueError("missing first-party contract context, budget or login gate")
    if not re.search(r"\b100\s*000\s*-\s*400\s*000\s*руб", original_text):
        raise ValueError("budget range missing or changed")
    sha = hashlib.sha256(source).hexdigest()
    legal = qualify_llc_response(
        {
            "source_url": SOURCE_URL,
            "platform_status": card["platform_status"],
            "organizer_type": card["organizer_type"],
            "source_observed_at": observed_at.isoformat(),
            "submission_deadline": SOURCE_CUTOFF_DAY,
        },
        checked_at=observed_at, source_sha256=sha, source_http_status=200,
    )
    return {
        "schema_version": "ta-b2b-wordpress-original-19032-v1",
        "procurement_card_id": SOURCE_NUMBER,
        "source_url": SOURCE_URL,
        "source_observed_at_utc": observed_at.astimezone(UTC).isoformat(),
        "original_http_status": 200,
        "original_html_sha256": sha,
        "original_html_size": len(source),
        "original_public_status": card["platform_status"],
        "original_organizer_type": card["organizer_type"],
        "source_deadline_date": SOURCE_CUTOFF_DAY,
        "source_deadline_time": "UNKNOWN",
        "source_budget_rub_low": 100_000,
        "source_budget_rub_high": 400_000,
        "budget_is_monthly_recurring_fee": "UNKNOWN",
        "source_buyer_business_area": "контейнерные перевозки",
        "source_cms": "WordPress",
        "source_scope_anchor_counts": count,
        "source_scope_anchors": {key: list(value) for key, value in SCOPE_ANCHORS.items()},
        "public_page_requests_agency_or_specialist_login": True,
        "current_company_account_registered_verified": False,
        "current_company_reply_entitlement_verified": False,
        "company_wordpress_commercial_references_verified": False,
        "owner_sla_and_quote_approved": False,
        "company_eligibility_state": legal.state,
        "unresolved_llc_gates": list(legal.blockers),
        "draft_quote_not_yet_authorized": {
            "monthly_support_rub": None,
            "support_hourly_rub": None,
            "change_hourly_rub": None,
            "change_fixed_per_task_rub": None,
            "incident_response_time_hours": None,
            "service_coverage_schedule": None,
        },
        "owner_bid_go": False,
        "external_messages_sent": 0,
        "paid_actions": 0,
        "signed_bids": 0,
    }


def collect() -> dict:
    opener = build_opener(ProxyHandler({}))
    with opener.open(
        Request(SOURCE_URL, headers={"User-Agent": "ArvectumTenderAgent-SourceResearch/1.0"}),
        timeout=15,
    ) as response:
        if response.status != 200 or response.geturl() != SOURCE_URL:
            raise ValueError("original source status or exact URL changed")
        source = response.read(MAX_SOURCE_BYTES + 1)
    return evaluate_original(source, observed_at=datetime.now(UTC))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = collect()
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print("ORIGINAL_WORDPRESS_19032", result["original_html_sha256"],
          "MONTHLY_COST", result["draft_quote_not_yet_authorized"]["monthly_support_rub"],
          "LLC_READY", result["owner_bid_go"])


if __name__ == "__main__":
    main()
