"""Original Moscow supplier-portal qualification: B2G policy, not a live bid.

First-party regulator statements are not the same as authorized account access
or an original quote-session card. Bounded exact read-only HTTPS; no login,
application, registration, cart, payment or SPA endpoint guessing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from scripts.acceptance.audit_schlam_offer_original_oct17 import _Markup

OFFICIAL_PAGES = {
    "registration": (
        "https://moszakupki.mos.ru/novosti/vse-novosti/"
        "obem-zakupok-moskvy-u-regionalnykh-predprinimateley-na-portale-postavshchikov-za-polgoda-sostavil-10/"
    ),
    "commercial_supplier": (
        "https://moszakupki.mos.ru/novosti/vse-novosti/"
        "bystro-i-udobno-podpisat-kontrakt-na-portale-postavshchikov-teper-mozhno-s-pomoshchyu-qr-koda-i-prya/"
    ),
    "optional_services": "https://moszakupki.mos.ru/uslugi/rabota-s-portalom-postavshchikov/",
    "short_quote_sessions": (
        "https://tender.mos.ru/news/"
        "v-pervom-polugodii-2026-goda-stolichnye-zakazchiki-proveli-bolee-116-tysyach-kotirovochnykh-sessiy-n/"
    ),
    "supplier_portal_shell": "https://zakupki.mos.ru/",
}
REVIEWED_POLICY_CLAUSES = {
    "registration": (
        "Это бесплатно.",
        "Упрощенная регистрация через почту позволяет просматривать информацию на портале, но не дает возможности участвовать в закупках.",
        "Для юридически значимых действий (подписание оферты, контракта и других) потребуется электронная подпись.",
    ),
    "commercial_supplier": (
        "поставщиками на ресурсе могут выступать коммерческие организации, индивидуальные предприниматели, самозанятые и физические лица",
        "Пока сервисом могут воспользоваться только региональные заказчики",
        "направляет ему приглашение на подписание в виде QR-кода или прямой ссылки",
    ),
    "optional_services": (
        "Обучение работе в АИС «Портал поставщиков» (Индивидуальное), 7 000 рублей",
        "Работа с запросами в АИС «Портал поставщиков» (Период 1 месяц), от 10 000 рублей",
        "платные услуги по организационно-методическому и информационному сопровождению поставщиков",
    ),
    "short_quote_sessions": (
        "мини-аукционах продолжительностью три, шесть или 24 часа",
        "могут все предприниматели, зарегистрированные на Портале поставщиков",
    ),
}
CAP_BYTES = {"short_quote_sessions": 1_500_000, **{k: 160_000 for k in OFFICIAL_PAGES if k != "short_quote_sessions"}}


def _read_exact(source: str, url: str) -> bytes:
    if OFFICIAL_PAGES.get(source) != url:
        raise ValueError("unapproved first-party URL")
    p = urlsplit(url)
    if (
        p.scheme != "https" or p.hostname not in (
            "moszakupki.mos.ru", "tender.mos.ru", "zakupki.mos.ru"
        ) or p.username or p.password or p.port is not None
        or p.query or p.fragment
    ):
        raise ValueError("unapproved source hostname or parameters")
    opener = build_opener(ProxyHandler({}))
    with opener.open(
        Request(url, headers={"User-Agent": "ArvectumTenderAgent-ReadOnlyPolicyAudit/1.0"}),
        timeout=14,
    ) as resp:
        if resp.status != 200 or resp.geturl() != url:
            raise ValueError("official source was not exact HTTP200")
        raw = resp.read(CAP_BYTES[source] + 1)
    if not 2000 < len(raw) <= CAP_BYTES[source]:
        raise ValueError("official source size invalid")
    return raw


def _plain(html: bytes) -> str:
    parser = _Markup()
    parser.feed(html.decode("utf-8", "strict"))
    return " ".join(parser.text.split())


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def audit_policy_page(source: str, html: bytes) -> dict:
    if source not in REVIEWED_POLICY_CLAUSES or not 2000 < len(html) <= CAP_BYTES[source]:
        raise ValueError("unreviewed official policy")
    plain = _plain(html)
    facts: list[dict] = []
    for expected in REVIEWED_POLICY_CLAUSES[source]:
        if _normalized(expected) not in _normalized(plain):
            raise ValueError("reviewed original official policy phrase missing or changed")
        facts.append({
            "original_source_fragment": expected,
            "fragment_sha256": hashlib.sha256(expected.encode("utf-8")).hexdigest(),
            "source_evidence_state": "LITERAL_ORIGINAL_POLICY_ATTESTED",
        })
    return {
        "policy_kind": source,
        "exact_official_url": OFFICIAL_PAGES[source],
        "original_html_sha256": hashlib.sha256(html).hexdigest(),
        "original_html_bytes": len(html),
        "original_http_status": 200,
        "attested_clauses": facts,
        "company_session_authenticated": False,
    }


def audit_portal_spa_shell(html: bytes) -> dict:
    if not 2000 < len(html) <= CAP_BYTES["supplier_portal_shell"]:
        raise ValueError("unexpected supplier SPA size")
    raw = html.decode("utf-8", "strict")
    if (
        "You need to enable JavaScript to run this app." not in raw
        or "/lib/cadesplugin_api.js" not in raw
        or "<html" not in raw.lower()
    ):
        raise ValueError("supplier portal layout no longer verified")
    return {
        "policy_kind": "supplier_portal_shell",
        "exact_official_url": OFFICIAL_PAGES["supplier_portal_shell"],
        "original_html_sha256": hashlib.sha256(html).hexdigest(),
        "original_http_status": 200,
        "public_response_is_client_side_javascript_application": True,
        "live_quote_sessions_parsed_from_actual_original_cards": 0,
        "live_quote_session_cards_checked": False,
        "live_it_quote_session_eligibility_verified": False,
        "do_not_claim_no_real_it_auctions": True,
        "company_session_authenticated": False,
    }


def audit_official_sources(raw_by_source: dict[str, bytes]) -> dict:
    if set(raw_by_source) != set(OFFICIAL_PAGES):
        raise ValueError("missing or extra original official source")
    checked: list[dict] = []
    for name in OFFICIAL_PAGES:
        if name == "supplier_portal_shell":
            checked.append(audit_portal_spa_shell(raw_by_source[name]))
        else:
            checked.append(audit_policy_page(name, raw_by_source[name]))
    return {
        "schema_version": "ta-b2g-moscow-portal-original-registration-policy-2026-10-18-v1",
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "source_kind": "FIRST_PARTY_OFFICIAL_PLATFORM_POLICY_NOT_LIVE_TENDER",
        "official_source_count": len(checked),
        "public_company_supplier_category_allowed": True,
        "free_initial_registration_claim_attested": True,
        "email_only_registration_authorizes_bidding": False,
        "electronic_signature_for_legally_binding_actions_required": True,
        "company_ukep_current_portal_linkage_verified": False,
        "company_full_supplier_registration_completed_verified": False,
        "quoted_optional_training_rub": 7000,
        "quoted_optional_priority_support_one_month_from_rub": 10000,
        "optional_services_are_compulsory_auction_fees": False,
        "platform_auction_operational_duration_hours": [3, 6, 24],
        "buyer_channel_category": "B2G_SMALL_PURCHASES_NOT_CORPORATE_B2B",
        "verified_live_it_quote_session_count": 0,
        "verified_live_quote_session_search_performed": False,
        "no_new_qualified_corporate_b2b_leads": True,
        "company_authorized_bid_go": False,
        "registrations_money_signatures_or_bids_executed": 0,
        "sources": checked,
    }


def collect() -> dict:
    originals = {name: _read_exact(name, url) for name, url in OFFICIAL_PAGES.items()}
    return audit_official_sources(originals)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = collect()
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "OFFICIAL_SOURCES", report["official_source_count"],
        "B2G_ONLY", report["buyer_channel_category"],
        "LLC_CURRENT_ELIGIBLE", report["verified_live_it_quote_session_count"],
    )


if __name__ == "__main__":
    main()
