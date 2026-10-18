"""First-party B2B marketplace LLC access policy, never claim authenticated rights.

Workspace digital agency legal-entity permission is distinct from a confirmed
company account; independent bids normally require category PRO, but explicitly
invited agency bids are free. Contractis START replies and CodeLance public
registration do not attest a contract-ready Russian LLC user account.

Only exact HTTPS original documents, read-only GET, and temporary PDF parsing
on ArvectumSSD; no sign-in, bidder actions, credit cards or external outreach.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from scripts.acceptance.audit_schlam_offer_original_oct17 import _Markup

ORIGINALS = {
    "workspace_terms": "https://workspace.ru/upload/terms_of_use.pdf",
    "workspace_pro_faq": "https://workspace.ru/advertising/",
    "contractis_home": "https://contractis.ru/freelance",
    "contractis_terms": "https://contractis.ru/documentation/polzovatelskoe-soglashenie",
    "contractis_rules": "https://contractis.ru/documentation/pravila-servisa",
    "contractis_offer": "https://contractis.ru/documentation/publichnaya-oferta",
    "contractis_tariffs": "https://contractis.ru/documentation/tarify",
    "codelance_developer": "https://www.codelance.ru/site/razrabotchikam",
    "codelance_signup": "https://www.codelance.ru/site/signup",
}
PDF_MAX = 350_000
HTML_MAX = 350_000
TEMP_DIR = "/Volumes/ArvectumSSD/Arvectum/tmp"

# Literal first-party contract wording; never project a site-wide price policy
# onto a particular unverified company cart.
PROOFS = {
    "workspace_terms": (
        "Редакция от 06.07.2026 г.",
        "2.4.2. Группа специалистов, объединенная в юридическое лицо",
        "4.4. При прохождении процедуры регистрации в качестве Агентства",
        "уполномоченным сотрудником юридического лица",
        "5.8.2. В случае если Агентство подходит под условия Тендера",
        "5.8.3. Чтобы иметь возможность самостоятельно откликаться на Тендеры",
        "Исполнителю необходимо приобрести платную опцию",
        "8.4.1. Агентству доступны следующие способы оплаты:",
        "по счету для оплаты платежным поручением",
    ),
    "workspace_pro_faq": (
        "Можно ли откликаться на тендеры бесплатно?",
        "Да, если Заказчик сам приглашает digital-агентство",
        "За отклик платить не потребуется.",
        "Если Исполнитель планирует откликаться на тендеры самостоятельно",
        "нужно приобрести PRO-аккаунт",
    ),
    "contractis_home": (
        "Регистрация, профиль с портфолио",
        "отклики в пределах месячного лимита бесплатны",
        "Подписка PRO снимает лимит откликов",
        "Самозанятые и ИП в каталоге выдают закрывающие документы",
    ),
    "contractis_terms": (
        "Редакция от 10 августа 2026 г.",
        "Пользователь любое лицо, зарегистрировавшееся или использующее сервис.",
        "Contractis не является стороной договоров между заказчиками и исполнителями",
        "При необходимости пользователи самостоятельно заключают договор, акт",
        "Для доступа к отдельным функциям пользователь проходит регистрацию",
    ),
    "contractis_rules": (
        "В базовом доступе исполнитель получает ограниченный лимит откликов.",
        "В стартовом доступе может быть доступно 5 тестовых откликов.",
        "В PRO-подписке исполнитель получает безлимитные отклики",
    ),
    "contractis_offer": (
        "START 0 ₽",
        "5 откликов в месяц",
        "PRO на месяц 499 ₽",
        "PRO на квартал 999 ₽",
        "При регистрации пользователь может получить 5 тестовых откликов",
        "Платные функции Contractis не являются оплатой работ исполнителей",
    ),
    "contractis_tariffs": (
        "PRO-подписка исполнителя, 1 месяц",
        "499 ₽",
        "PRO-подписка исполнителя, квартал",
        "999 ₽",
    ),
    "codelance_developer": (
        "Отклики — 0 ₽",
        "Никаких платных подписок",
        "Шаг 2. Откликнуться бесплатно",
    ),
    "codelance_signup": (
        "Регистрация на сайте",
        "Логин (необязательно)",
        "Email *",
        "Имя *",
        "Фамилия *",
        "Пароль *",
        "Зарегистрироваться",
    ),
}


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def _policy_text(name: str, raw: bytes) -> str:
    if name == "workspace_terms":
        if not raw.startswith(b"%PDF-"):
            raise ValueError("original PDF required")
        with tempfile.TemporaryDirectory(prefix="ta-b2b-workspace-terms-", dir=TEMP_DIR) as scratch:
            path = Path(scratch) / "official.pdf"
            path.write_bytes(raw)
            r = subprocess.run(
                ["pdftotext", "-layout", str(path), "-"],
                capture_output=True, text=True, timeout=20, check=True,
            )
            if r.stderr:
                raise ValueError("original PDF text extraction warning")
            return _normalized(r.stdout)
    m = _Markup()
    m.feed(raw.decode("utf-8", "strict"))
    return _normalized(m.text)


def verify_original_policy(name: str, raw: bytes) -> dict:
    if name not in ORIGINALS:
        raise ValueError("not an approved first-party legal document")
    max_bytes = PDF_MAX if name == "workspace_terms" else HTML_MAX
    if not 1500 < len(raw) <= max_bytes:
        raise ValueError("original policy outside bounded expected size")
    text = _policy_text(name, raw)
    missing = [phrase for phrase in PROOFS[name] if _normalized(phrase) not in text]
    if missing:
        raise ValueError(f"first-party source policy changed or missing anchor: {name}")
    if name == "codelance_signup":
        # This concerns only the *first public form*, not the entire later
        # registration sequence or whether company profiles can be created.
        personal_fields = ("Имя *", "Фамилия *", "Email *", "Пароль *")
        assert all(_normalized(x) in text for x in personal_fields)
    return {
        "source": name,
        "exact_url": ORIGINALS[name],
        "html_or_pdf_sha256": hashlib.sha256(raw).hexdigest(),
        "original_bytes": len(raw),
        "original_status_http": 200,
        "original_clause_fragments": list(PROOFS[name]),
        "is_authenticated_company_session": False,
    }


def qualify_provider(sources: dict[str, bytes], *, observed: datetime) -> dict:
    if set(sources) != set(ORIGINALS) or observed.utcoffset() is None:
        raise ValueError("incomplete original policy receipts or invalid UTC")
    verified = [verify_original_policy(k, sources[k]) for k in ORIGINALS]
    return {
        "schema_version": "ta-b2b-first-party-llc-platform-policy-2026-10-18-v1",
        "observed_at_utc": observed.isoformat(),
        "first_party_policies_checked": len(verified),
        "source_documents": verified,
        "workspace": {
            "legal_entity_as_agency_explicit_in_agreement": True,
            "legal_agent_must_be_authorized_representative": True,
            "default_self_initiated_tender_reply_requires_pro": True,
            "invited_agency_reply_free_by_official_faq": True,
            "published_company_invoice_payment_option": True,
            "actual_llc_agency_profile_authenticated": False,
            "specific_tender_invitation_verified": False,
            "own_company_pro_category_and_price_verified": False,
            "can_reply_to_19012_without_pro_verified": False,
            "legal_entity_category_allowed_is_not_bid_ready": True,
        },
        "contractis": {
            "free_tier_public": True,
            "published_start_free_replies_per_month": 5,
            "five_test_replies_are_conditional_not_automatic": True,
            "public_pro_month_rub": 499,
            "public_pro_quarter_rub": 999,
            "operator_party_to_customer_contract": False,
            "customer_performer_contract_direct": True,
            "explicit_verified_llc_registration_mode": False,
            "specific_company_account_free_reply_quota_verified": False,
            "actual_customer_legal_identity_verified": False,
            "actual_contract_for_arvectum_verified": False,
        },
        "codelance": {
            "public_free_developer_replies": True,
            "first_public_registration_form_fields": [
                "login optional", "email", "given name", "surname", "phone optional",
                "password", "confirm password",
            ],
            "separate_legal_entity_fields_verified_in_first_form": False,
            "explicit_verified_llc_registration_mode": False,
            "subsequent_corporate_profile_options_inspected": False,
            "actual_company_contract_and_payout_verified": False,
        },
        "current_arvectum_llc_bid_authority_across_all_three": 0,
        "registrations_bids_payments_emails_signatures_executed": 0,
        "new_distinct_b2b_it_procurement_opportunities": 0,
        "next_required_owner_evidence": [
            "existing company agent account scope without disclosing credentials",
            "authentically completed company portfolio or team contract references",
            "contracting/payout to Russian LLC on Contractis and CodeLance",
            "company invite for Workspace 19012 or authorized PRO category plus owner's budget GO",
        ],
    }


def _source_get(url: str) -> bytes:
    if url not in set(ORIGINALS.values()):
        raise ValueError("unapproved first-party legal URL")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ("workspace.ru", "contractis.ru", "www.codelance.ru")
        or parsed.username or parsed.password or parsed.port is not None
        or parsed.query or parsed.fragment
    ):
        raise ValueError("unapproved first-party legal host")
    with build_opener(ProxyHandler({})).open(
        Request(url, headers={"User-Agent": "ArvectumTenderAgent-ReadOnlyLegalPolicy/1.0"}),
        timeout=15,
    ) as resp:
        if resp.status != 200 or resp.geturl() != url:
            raise ValueError("legal document not exact HTTP200")
        cap = PDF_MAX if url.endswith(".pdf") else HTML_MAX
        data = resp.read(cap + 1)
    if not 1500 < len(data) <= cap:
        raise ValueError("original source size invalid")
    return data


def collect() -> dict:
    with ThreadPoolExecutor(max_workers=5) as executor:
        pending = {name: executor.submit(_source_get, uri) for name, uri in ORIGINALS.items()}
        bodies = {name: future.result() for name, future in pending.items()}
    return qualify_provider(bodies, observed=datetime.now(UTC))


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--out", type=Path, required=True)
    out = args.parse_args().out
    report = collect()
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "POLICIES", report["first_party_policies_checked"],
        "WORKSPACE_LLC_KIND", report["workspace"]["legal_entity_as_agency_explicit_in_agreement"],
        "CONTRACTIS_FREE_START", report["contractis"]["published_start_free_replies_per_month"],
        "ACTUAL_LLC_BIDS", report["current_arvectum_llc_bid_authority_across_all_three"],
    )


if __name__ == "__main__":
    main()
