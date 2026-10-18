"""Fresh source-pinned urgent B2B shortlist, zero spend / no bid authorization.

Read-only first-party HTTPS and exact original requirements only. A public
"accepting" label never means LLC account, contract, or free reply rights.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from scripts.acceptance.audit_schlam_offer_original_oct17 import _Markup
from scripts.acceptance.audit_workspace_design_pro_19012_20261018 import (
    verify_design_tariffs,
    verify_original_design_card,
)
from scripts.acceptance.discover_workspace_original_it_20261018 import (
    evaluate_original_card,
)

CASES = {
    "19012": {
        "url": "https://workspace.ru/tenders/novyy-dizayn-sayta-detskih-tovarov-19012/",
        "source": "WORKSPACE", "expected_day": "2026-10-19",
        "category": "DESIGN_ONLY_NOT_WEBSITE_BUILD",
        "anchors": ("Дизайн главной страницы сайта детских товаров", "Материалы: ТЗ, прототип, мудборд."),
        "preferred_zero_spend_step": "PREPARE_TRUTHFUL_DESIGN_REFERENCES_AND_OWNER_ACCESS_DECISION",
        "bidding_cost_state": "DESIGN_PRO_PUBLIC_6900_RUB_MONTH_IF_ACCOUNT_CATEGORY_MATCHES",
    },
    "19032": {
        "url": "https://workspace.ru/tenders/teh-obsluzhivanie-i-dorabotka-korporativnogo-sayta-19032/",
        "source": "WORKSPACE", "expected_day": "2026-10-21",
        "category": "WORDPRESS_MAINTENANCE_SLA",
        "anchors": ("WordPress", "мониторинг доступности сайта", "Система оплаты"),
        "preferred_zero_spend_step": "VALIDATE_REAL_WORDPRESS_PORTFOLIO_SLA_AND_PRICE_BOUNDARY",
        "bidding_cost_state": "ACTUAL_SUPPORT_PRO_CATEGORY_AND_CART_UNKNOWN",
    },
    "19034": {
        "url": "https://workspace.ru/tenders/sozdanie-i-prodvizhenie-sayta-kliningovoy-kompanii-19034/",
        "source": "WORKSPACE", "expected_day": "2026-10-31",
        "category": "WORDPRESS_SITE_WITH_GATED_TZ",
        "anchors": ("Платформа: WordPress.", "ТЗ на создание сайта"),
        "preferred_zero_spend_step": "PREPARE_REAL_WEBSITE_REFERENCES_NO_FINAL_QUOTE_WITHOUT_TZ",
        "bidding_cost_state": "WEBSITE_PRO_PUBLIC_25500_RUB_MONTH_IF_ACCOUNT_CATEGORY_MATCHES",
    },
    "C6": {
        "url": "https://contractis.ru/order/ishchu-podryadchika-na-razrabotku-po-na-python-rabota-s-ii",
        "source": "CONTRACTIS", "expected_day": None,
        "category": "PYTHON_AI_SOURCE_CODE_DELIVERY",
        "anchors": ("Заказ № 6", "Бюджет: 170 000 ₽", "Срок: 60 дней",
                    "Требуется разработать программное обеспечение на Python"),
        "preferred_zero_spend_step": "PREPARE_PYTHON_RELEVANCE_QUESTIONS_NO_CONTACT_UNTIL_GO",
        "bidding_cost_state": "OFFICIAL_FREE_REPLY_QUOTA_GENERAL_ACCOUNT_RIGHTS_UNKNOWN",
    },
    "C12": {
        "url": "https://contractis.ru/order/sait-dlya-padl-kluba-lending-s-bronirovaniem",
        "source": "CONTRACTIS", "expected_day": None,
        "category": "LANDING_WITH_ONLINE_BOOKING",
        "anchors": ("Заказ № 12", "Бюджет: 100 000 ₽", "Срок: 30 дней",
                    "функционалом онлайн-бронирования"),
        "preferred_zero_spend_step": "PREPARE_BOOKING_SCOPE_INTEGRATION_AND_MARGIN_QUESTIONS",
        "bidding_cost_state": "OFFICIAL_FREE_REPLY_QUOTA_GENERAL_ACCOUNT_RIGHTS_UNKNOWN",
    },
    "CL147": {
        "url": "https://www.codelance.ru/orders/view?id=147",
        "source": "CODELANCE", "expected_day": None,
        "category": "PRODUCT_FEED_INTEGRATION_JSON_XML",
        "anchors": ("Открыт", "Парсинг на сайт", "https://na-pol.shop/",
                    "https://av.my-step.eu/avaliable_products.json"),
        "preferred_zero_spend_step": "PREPARE_FEED_INTEGRATION_SCOPE_AND_LEGAL_CONTRACT_CHECK",
        "bidding_cost_state": "OFFICIAL_FREE_REPLY_CLAIM_ACCOUNT_RIGHTS_UNKNOWN",
    },
}

PRICING_URL = "https://workspace.ru/advertising/"
MAX_BYTES = 400_000


def _source_plain(body: bytes) -> str:
    p = _Markup()
    p.feed(body.decode("utf-8", "strict"))
    return " ".join(p.text.split())


def _source_get(url: str) -> bytes:
    targets = {v["url"] for v in CASES.values()} | {PRICING_URL}
    if url not in targets:
        raise ValueError("unapproved exact first-party original source")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "workspace.ru", "contractis.ru", "www.codelance.ru"
    } or parsed.username or parsed.password or parsed.port is not None:
        raise ValueError("unapproved original host")
    opener = build_opener(ProxyHandler({}))
    with opener.open(
        Request(url, headers={"User-Agent": "ArvectumTenderAgent-ReadOnlyFirstPartyOriginal/1.0"}),
        timeout=14,
    ) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("original source HTTP or redirect mismatch")
        raw = response.read(MAX_BYTES + 1)
    if not 2000 < len(raw) <= MAX_BYTES:
        raise ValueError("original body size outside limits")
    return raw


def audit_case(code: str, body: bytes, checked: datetime) -> dict:
    if code not in CASES or checked.utcoffset() is None:
        raise ValueError("unknown original or missing time zone")
    case = CASES[code]
    if not 2000 < len(body) <= MAX_BYTES:
        raise ValueError("source body outside limits")
    text = _source_plain(body)
    lowered = " ".join(text.casefold().split())
    if not all(" ".join(anchor.casefold().split()) in lowered for anchor in case["anchors"]):
        raise ValueError("original source scope evidence missing or changed")
    result = {
        "source_id": code, "original_url": case["url"],
        "observed_at_utc": checked.isoformat(),
        "original_html_sha256": hashlib.sha256(body).hexdigest(),
        "source_kind": case["source"],
        "source_scope": case["category"],
        "attested_source_phrases": list(case["anchors"]),
        "due_day_public": case["expected_day"] or "UNKNOWN_NOT_SHOWN_AS_EXACT_DAY",
        "due_clock_msk_public": "UNKNOWN",
        "company_buyer_inn_verified": False,
        "llc_arvectum_corporate_account_verified": False,
        "llc_pro_or_free_reply_rights_verified": False,
        "company_submitted_or_paid": False,
        "company_contract_ready": False,
        "recommended_zero_spend_step": case["preferred_zero_spend_step"],
        "cost_claim_not_company_cart": case["bidding_cost_state"],
        "owner_go": False,
    }
    if case["source"] == "WORKSPACE":
        if code == "19012":
            w = verify_original_design_card(body, checked)
            result["source_public_state"] = w["public_source_state"]
            result["budget_rub"] = [w["source_budget_floor_rub"], w["source_budget_ceiling_rub"]]
        else:
            u = urlsplit(case["url"]).path.split("/")[-2]
            slug = u.removesuffix("-" + code)
            w = evaluate_original_card(
                number=code, slug=slug, original_url=case["url"], body=body,
                observed=checked, categories=("WEB",),
            )
            result["source_public_state"] = w["public_source_state"]
        if (
            result["source_public_state"] != "PUBLIC_CANDIDATE_ONLY"
            or w["printed_deadline_day"] != case["expected_day"]
            or w.get("organizer_type", "Юридическое лицо") != "Юридическое лицо"
        ):
            raise ValueError("original source not a public current corporate candidate")
        result["public_company_organizer_type"] = "Юридическое лицо"
        result["public_status_text"] = "Идет прием заявок"
        result["deadline_has_original_clock_time"] = False
    elif case["source"] == "CODELANCE":
        if "Открыт" not in text[:500] or "Создано" not in text[:500]:
            raise ValueError("original CodeLance status or creation not attested")
        result["source_public_state"] = "OPEN_CARD_NOT_AUTHENTICATED_REPLY"
        result["original_created_relative_time"] = "RELATIVE_DISPLAY_NOT_EXACT_SOURCE_DATE"
        result["public_company_organizer_type"] = "UNKNOWN"
    else:
        if "Биржа заказов" not in text[:250] or "Дата публикации:" not in text:
            raise ValueError("original Contractis type and creation not attested")
        result["source_public_state"] = "SOURCE_TASK_DESCRIPTION_WITHOUT_VERIFIED_LIVE_STATUS"
        result["original_created_relative_time"] = "RELATIVE_ONLY"
        result["public_company_organizer_type"] = "UNKNOWN"
    return result


def summarize(sources: dict[str, bytes], *, checked: datetime) -> dict:
    if set(sources) != set(CASES) | {"PRO"}:
        raise ValueError("original source set incomplete")
    snapshot = [audit_case(id_, sources[id_], checked) for id_ in CASES]
    pro = verify_design_tariffs(sources["PRO"])
    return {
        "schema_version": "ta-b2b-urgent-free-first-original-2026-10-18-v1",
        "observed_at_utc": checked.isoformat(),
        "source_originals_checked": len(snapshot) + 1,
        "public_workspace_corporate_tenders": 3,
        "free_first_marketplace_task_descriptions": 3,
        "actual_arvectum_llc_bid_ready_count": 0,
        "actual_llc_pro_subscription_bought": False,
        "actual_llc_free_reply_used": False,
        "messages_payment_or_registration_executed": 0,
        "public_design_pro_rub_1mo_if_applicable": pro["public_design_branding_pro_1mo_rub"],
        "public_webdev_pro_rub_1mo_if_applicable": pro["public_website_development_pro_1mo_rub"],
        "actual_workspace_llc_checkout_verified": False,
        "pro_policy_html_sha256": pro["advertising_source_html_sha256"],
        "source_cases": snapshot,
        "notes": [
            "Source organizer class company does not prove original buyer INN.",
            "Source day-only deadline does not guarantee 23:59 or company authenticated right to reply.",
            "Self-published App Store apps are real LLC products, not substitute for paid customer design or WordPress contracts.",
            "Do not buy month PRO for single speculative lead without access and qualified portfolio.",
            "Contractis publicly viewed task and CodeLance OPEN label do not guarantee live buyer or Russian LLC contract.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks = {
            number: pool.submit(_source_get, spec["url"])
            for number, spec in CASES.items()
        }
        tasks["PRO"] = pool.submit(_source_get, PRICING_URL)
        bodies = {number: future.result() for number, future in tasks.items()}
    report = summarize(bodies, checked=datetime.now(UTC))
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "ORIGINALS", report["source_originals_checked"],
        "WORKSPACE", report["public_workspace_corporate_tenders"],
        "FREE_FIRST_TASKS", report["free_first_marketplace_task_descriptions"],
        "LLC_BID_READY", report["actual_arvectum_llc_bid_ready_count"],
    )


if __name__ == "__main__":
    main()
