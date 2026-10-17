"""Original Workspace 19042/19043 requirement audit; no LLC approval, messages or PRO."""
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
MAX_BYTES = 400_000
ORIGINALS = {
    "19042": {
        "slug": "sistema-avtomatizacii-i-ucheta-oborudovaniya-dlya-myasokombinata",
        "deadline": "2026-10-31",
        "budget": (300_000, 900_000),
        "hard_qualification": (
            "Коммерческий опыт разработки от 3 лет.",
            "Наличие портфолио завершённых проектов.",
            "Опыт разработки веб-приложений и баз данных.",
            "Понимание архитектуры клиент-серверных систем.",
        ),
        "preferred_qualification": (
            "Желателен опыт разработки ERP, CMMS или систем автоматизации предприятий.",
        ),
        "source_scope": (
            "Создание единой базы оборудования.",
            "Учёт местоположения, состояния и перемещения техники.",
            "Присвоение инвентарных номеров и использование QR-кодов.",
            "Учёт ремонтов, технического обслуживания и неисправностей.",
            "Разработка системы заявок и уведомлений.",
            "Разграничение прав доступа сотрудников.",
            "Формирование отчётов и аналитики.",
            "Адаптация интерфейса под ПК и смартфоны.",
            "Передача исходного кода, базы данных и технической документации заказчику.",
            "Гарантийное исправление выявленных ошибок на согласованных условиях.",
        ),
        "requested_quote": (
            "Предварительную стоимость разработки системы в рублях",
            "Ориентировочные сроки выполнения проекта.",
            "Предлагаемые этапы разработки и условия оплаты.",
            "Информацию о предоставляемой гарантии и технической поддержке.",
            "перечень работ, входящих в указанную стоимость.",
        ),
        "other": (
            "Поэтапная оплата по согласованным результатам работ.",
            "Окончательная стоимость и сроки могут быть скорректированы",
            "Бюджет: 300 000 - 900 000 рублей",
        ),
    },
    "19043": {
        "slug": "obnovlenie-sayta-digital-agentstva-audit-redizayn-ili-razrabotka-novogo-korporativnogo-sayta",
        "deadline": "2026-10-31",
        "budget": (200_000, 800_000),
        "hard_qualification": (
            "Наличие релевантных реализованных проектов обязательно.",
        ),
        "preferred_qualification": (
            "Предпочтение отдадим командам с сильной экспертизой в UX/UI",
        ),
        "source_scope": (
            "Редизайн существующего сайта с улучшением структуры",
            "Более глубокую переработку сайта",
            "Полноценную разработку нового сайта с переносом необходимых материалов",
            "Сохранить накопленный SEO-потенциал сайта",
            "Краткий анализ текущего сайта и его основных недостатков.",
            "Рекомендации по оптимальному масштабу изменений.",
            "Предлагаемые технологии и CMS с обоснованием выбора.",
            "Этапы реализации и ориентировочные сроки.",
            "Предварительную стоимость работ с разбивкой по основным этапам.",
            "Подход к переносу контента и сохранению SEO.",
            "Тестирование и запуск.",
            "Последующую техническую поддержку.",
        ),
        "requested_quote": (
            "предварительно ознакомиться с действующим сайтом",
            "Аналитику, проектирование и дизайн.",
            "Разработку и внедрение.",
            "Перенос и переработку контента.",
            "Работы по сохранению SEO.",
        ),
        "optional_requested": (
            "Если возможно, просим предложить 2 варианта реализации",
        ),
        "other": (
            "Окончательный объём работ и функциональность готовы согласовать",
            "Бюджет: 200 000 - 800 000 рублей",
        ),
    },
}


def source_url(case_id: str) -> str:
    spec = ORIGINALS[case_id]
    return f"https://workspace.ru/tenders/{spec['slug']}-{case_id}/"


def _normalize(value: str) -> str:
    return " ".join(value.casefold().replace("ё", "е").split())


def evaluate_original(case_id: str, source: bytes, *, observed_at: datetime) -> dict:
    if case_id not in ORIGINALS:
        raise ValueError("unexpected procurement card")
    if observed_at.utcoffset() is None:
        raise ValueError("observed_at must have explicit timezone")
    if not 300 <= len(source) <= MAX_BYTES:
        raise ValueError("unexpected source size")
    spec = ORIGINALS[case_id]
    original = extract_public_card(
        source, key=case_id, observed=observed_at,
        allowed_cards={case_id: (spec["slug"], spec["deadline"], "FIT_HIGH")},
    )
    if original["visibility"] != "public" or original["organizer_type"] != "Юридическое лицо":
        raise ValueError("public corporate origin not verified")
    if original["source_status_gate"] != "PUBLIC_CANDIDATE_ONLY":
        raise ValueError("source receiving status not verified")
    visible = _Markup()
    visible.feed(source.decode("utf8", "strict"))
    text = _normalize(visible.text)
    groups = {
        key: list(spec.get(key, ()))
        for key in ("hard_qualification", "preferred_qualification", "source_scope",
                    "requested_quote", "optional_requested", "other")
    }
    for group, phrases in groups.items():
        if any(_normalize(phrase) not in text for phrase in phrases):
            raise ValueError(f"original source {case_id} missing {group} quote evidence")
    minimum, maximum = spec["budget"]
    if re.search(rf"\b{minimum // 1000}\s*000\s*-\s*{maximum // 1000}\s*000\s*руб", text) is None:
        raise ValueError("original budget text changed")
    sha = hashlib.sha256(source).hexdigest()
    legal = qualify_llc_response(
        {
            "source_url": source_url(case_id),
            "organizer_type": original["organizer_type"],
            "platform_status": original["platform_status"],
            "submission_deadline": original["application_deadline_date"],
            "source_observed_at": observed_at.isoformat(),
        },
        checked_at=observed_at, source_http_status=200, source_sha256=sha,
    )
    if legal.state != "LLC_REVIEW_REQUIRED" or legal.response_authorized:
        raise ValueError("unexpected company approval state")
    return {
        "id": case_id,
        "source_url": source_url(case_id),
        "original_http_status": 200,
        "observed_at_utc": observed_at.astimezone(UTC).isoformat(),
        "original_html_sha256": sha,
        "original_html_bytes": len(source),
        "source_receiving_status": original["platform_status"],
        "source_organizer_type": original["organizer_type"],
        "source_deadline_date": spec["deadline"],
        "source_deadline_hour": "UNKNOWN",
        "source_budget_rub_min": minimum,
        "source_budget_rub_max": maximum,
        "budget_is_contractually_fixed": False,
        "source_clause_groups": groups,
        "hard_qualification_clauses": len(groups["hard_qualification"]),
        "requested_two_site_options_is_mandatory": False if case_id == "19043" else None,
        "required_commercial_experience_years": 3 if case_id == "19042" else None,
        "buyer_accepts_employee_or_partner_references": "UNKNOWN",
        "company_mandatory_experience_proven": False,
        "company_accepted_realized_portfolio_proven": False,
        "company_account_pro_access_verified": False,
        "customer_existing_site_url_verified": False if case_id == "19043" else None,
        "owner_approved_price_rub": None,
        "owner_approved_delivery_deadline": None,
        "owner_approved_warranty": None,
        "company_eligibility_state": legal.state,
        "unresolved_company_gates": list(legal.blockers),
        "bid_ready": False,
        "owner_go": False,
        "external_messages_or_paid_actions": 0,
    }


def collect() -> dict:
    opener = build_opener(ProxyHandler({}))
    cases = []
    for case_id in ("19042", "19043"):
        url = source_url(case_id)
        with opener.open(
            Request(url, headers={"User-Agent": "ArvectumTenderAgent-SourceResearch/1.0"}),
            timeout=12,
        ) as response:
            if response.status != 200 or response.geturl() != url:
                raise ValueError("original source unavailable or redirected")
            data = response.read(MAX_BYTES + 1)
        cases.append(evaluate_original(case_id, data, observed_at=datetime.now(UTC)))
    return {
        "schema_version": "workspace-19042-19043-first-party-qualification-v1",
        "as_of_utc": datetime.now(UTC).isoformat(),
        "original_verified_cards": len(cases),
        "company_realized_portfolio_accepted_count": 0,
        "company_confirmed_reply_access_count": 0,
        "bid_ready_count": 0,
        "paid_actions_or_messages_sent": 0,
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = collect()
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print("ORIGINAL", report["original_verified_cards"], "BID_READY", report["bid_ready_count"])


if __name__ == "__main__":
    main()
