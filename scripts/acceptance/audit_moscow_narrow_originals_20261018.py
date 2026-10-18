"""Conservative source-verified first-party Moscow B2G narrow IT search.

A broad public list search 'active' is NOT proof of detail status nor future
submission. Only two exact first-party original quote URLs are in scope.
No contracts, downloads, bidding, credentials or reverse-engineered APIs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from lxml import html as lxml_html

SOURCE_HOST = "https://zakupki.mos.ru"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TMP_DIR = "/Volumes/ArvectumSSD/Arvectum/tmp"
TERMS = (
    "сайт", "интеграция", "доработка", "автоматизация", "CRM", "1С",
    "техническая поддержка", "информационных систем",
    "программных продуктов", "62.01",
)
ORIGINALS = {
    "10321173": {
        "listed_status": "АКТИВНАЯ",
        "detail_status": "Активная",
        "title": "Услуги по установке и техническому обслуживанию комплекта средств защиты информации",
        "buyer": 'МУНИЦИПАЛЬНОЕ АВТОНОМНОЕ ОБЩЕОБРАЗОВАТЕЛЬНОЕ УЧРЕЖДЕНИЕ "НИЖНЕМУЛЛИНСКАЯ СРЕДНЯЯ ШКОЛА"',
        "buyer_inn_from_list": "5948016787",
        "end_msk": "19.10.2026 12:58:04",
        "initial_price_rub": "65092.56",
        "known_facts": (
            "Проведение оценки эффективности реализованных в рамках системы защиты персональных данных",
            "Разработка комплекта типовой организационно-распорядительной документации",
            "Установка и настройка средств защиты информации",
            "Secret Net Studio",
            "ViPNet Client 5 for Linux",
            "Альт Образование",
            "Пермский край, м.о. Пермский, д. Петровка, ул. Школьная, д 4",
        ),
        "business_role": "SECURITY_IMPLEMENTATION_AND_SOFTWARE_LICENSES_NOT_CUSTOM_DEV",
    },
    "10314722": {
        "listed_status": "АКТИВНАЯ",
        "detail_status": "Не состоялась",
        "title": "Проведение экспертизы технического состояния объектов",
        "buyer": "Школа № 1520 имени Капцовых",
        "buyer_inn_from_list": "7703261626",
        "end_msk": "09.10.2026 18:00:00",
        "initial_price_rub": "100.00",
        "known_facts": (
            "Закупка с неизвестным объемом",
            "Максимальное значение цены контракта",
            "50 000 ₽",
            "Прием ставок закончен",
            "Не состоялась",
        ),
        "business_role": "TERMINAL_PAST_DEADLINE_NON_IT_EXPERTISE",
    },
}


def _plain_html(raw: str) -> tuple[str, object]:
    if not 10_000 <= len(raw) <= 20_000_000:
        raise ValueError("original Chrome HTML invalid size")
    root = lxml_html.fromstring(raw)
    for tag in root.xpath("//script|//style|//noscript"):
        tag.drop_tree()
    return " ".join(" ".join(root.xpath("//body//text()")).split()), root


def _observed_list(original_observation: dict) -> dict:
    if original_observation.get("state") != "PUBLIC_FIRST_PARTY_NARROW_IT_SEARCH_COMPLETED":
        raise ValueError("narrow search not complete")
    searches = original_observation.get("searches")
    if not isinstance(searches, list) or len(searches) != len(TERMS):
        raise ValueError("wrong number of original public searches")
    output = []
    source_ids: set[str] = set()
    for term, row in zip(TERMS, searches, strict=True):
        if (
            row.get("term") != term
            or row.get("exact_applied_query") is not True
            or row.get("public_status_gate") != [19000002]
            or row.get("first_page_only") is not True
        ):
            raise ValueError("public UI term/active state filter not attested")
        rawtext = row.get("html_public_visible_text", "")
        if not isinstance(rawtext, str) or len(rawtext) > 10200:
            raise ValueError("source original visible text absent or unbounded")
        links = row.get("original_detail_links")
        if not isinstance(links, list) or len(links) > 36:
            raise ValueError("source original links absent or unbounded")
        ids = []
        for link in links:
            p = urlsplit(link.get("url", ""))
            found = re.fullmatch(r"/auction/(\d{8})", p.path)
            if p.scheme != "https" or p.hostname != "zakupki.mos.ru" or found is None or p.username or p.password or p.port is not None:
                raise ValueError("non-original domain/auction link")
            number = found.group(1)
            if number not in ids:
                ids.append(number)
                source_ids.add(number)
        if not ids and "Ничего не нашлось" not in rawtext:
            raise ValueError("no original empty-result attestation")
        output.append({
            "term": term,
            "original_source_ids": ids,
            "first_page_numbered_originals": len(ids),
            "source_filter_state": "PUBLIC_LIST_FILTER_ACTIVE_NOT_DETAIL_VERIFIED",
            "original_visible_sample_first_900": rawtext.split("Сортировка: По релевантности")[-1][:900],
            "source_observed_at_utc": row["current_date_observation_utc"],
        })
    if not set(ORIGINALS).issubset(source_ids):
        raise ValueError("selected exact original detail not anchored in first-party list")
    return {
        "original_first_party_query_count": len(output),
        "source_first_page_unique_ids": len(source_ids),
        "queries": output,
    }


def check_detail(number: str, rendered_html: str, observed: datetime) -> dict:
    if number not in ORIGINALS or observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("unapproved original quote or observation time")
    expected = ORIGINALS[number]
    text, root = _plain_html(rendered_html)
    page_title = " ".join(root.xpath("string(//title)").split())
    if (
        f"Котировочная сессия {number}" not in page_title
        or f"Котировочная сессия {number}" not in text[:450]
        or expected["title"].casefold() not in text.casefold()
        or expected["buyer"].casefold() not in text.casefold()
    ):
        raise ValueError("original title or buyer evidence missing")
    if number != "10314722" and "Для участия в котировочной сессии" not in text[:1500]:
        raise ValueError("original active bid authentication gate missing")
    for phrase in expected["known_facts"]:
        if phrase.casefold() not in text.casefold():
            raise ValueError("exact original required scope phrase changed")
    # Status must come from the original detail, not search-list status, which
    # can be wrong or inconsistent for failed sessions.
    if f"Котировочная сессия {number} {expected['detail_status']}" not in text[:500]:
        raise ValueError("original detail status different")
    public_deadline = datetime.strptime(expected["end_msk"], "%d.%m.%Y %H:%M:%S").replace(
        tzinfo=ZoneInfo("Europe/Moscow")
    )
    if expected["end_msk"] not in text:
        raise ValueError("original detailed deadline time changed")
    expiry = observed.astimezone(ZoneInfo("Europe/Moscow")) >= public_deadline
    is_open = expected["detail_status"] == "Активная" and not expiry
    # Source can be contradictory: previous public filtered list stated
    # "active" while full original detail is "failed".
    discrepancy = expected["detail_status"].upper() != expected["listed_status"]
    docs = []
    for a in root.xpath("//a[@href]"):
        name = " ".join(a.itertext()).strip()
        p = urlsplit(a.get("href", ""))
        if (
            p.scheme == "https" and p.hostname == "zakupki.mos.ru"
            and p.path == "/newapi/api/FileStorage/Download"
            and re.fullmatch(r"id=\d+", p.query)
        ):
            docs.append(name[:120])
    if not docs:
        raise ValueError("original source public document names missing")
    return {
        "id": number,
        "original_url": f"{SOURCE_HOST}/auction/{number}",
        "original_rendered_html_sha256": hashlib.sha256(rendered_html.encode()).hexdigest(),
        "observed_at_utc": observed.isoformat(),
        "original_detail_current_status": expected["detail_status"],
        "first_party_search_list_claimed_status": expected["listed_status"],
        "list_and_detail_status_contradict": discrepancy,
        "original_due_at_msk": public_deadline.isoformat(),
        "original_due_has_passed": expiry,
        "source_detail_public_open_and_not_expired": is_open,
        "source_scope": expected["business_role"],
        "original_line_item_scope_proofs": list(expected["known_facts"]),
        "list_buyer_inn_unreverified_in_detail": expected["buyer_inn_from_list"],
        "source_initial_or_unit_price_rub": expected["initial_price_rub"],
        "original_visible_document_names": docs,
        "is_bespoke_programming_or_software_development": False,
        "company_authorized_to_bid": False,
        "user_owner_go": False,
        "company_reply_sent": False,
        "files_downloaded": False,
        "candidate_is_supplier_sales_ready": False,
    }


def _browser(number: str) -> str:
    if number not in ORIGINALS:
        raise ValueError("unknown first-party original")
    with tempfile.TemporaryDirectory(prefix="ta-mos-narrow-detail-", dir=TMP_DIR) as temp:
        proc = subprocess.run(
            [
                CHROME, "--headless=new", "--disable-gpu", "--disable-extensions",
                "--disable-sync", "--no-first-run", "--disable-background-networking",
                "--user-data-dir=" + temp, "--virtual-time-budget=12000",
                "--dump-dom", f"{SOURCE_HOST}/auction/{number}",
            ],
            text=True, capture_output=True, timeout=35, check=False,
        )
    if proc.returncode != 0:
        raise ValueError("original public Chrome detail unavailable")
    return proc.stdout


def collect(source_raw: dict) -> dict:
    summary = _observed_list(source_raw)
    original_details = [
        check_detail(n, _browser(n), datetime.now(UTC)) for n in ORIGINALS
    ]
    result = {
        "schema_version": "ta-b2g-moscow-narrow-terms-and-original-detail-reconciliation-v1",
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "official_source": SOURCE_HOST,
        "original_active_filter_is_not_authoritative_detail_status": True,
        **summary,
        "original_detail_pages_verified": len(original_details),
        "original_detail_reconciliations": original_details,
        "narrow_first_pages_bespoke_software_development_confirmed": 0,
        "claim_no_custom_software_bids_ever_exist": False,
        "verified_current_company_bids": 0,
        "new_corporate_b2b_lead_count": 0,
        "registrations_signatures_payments_replies": 0,
        "browser_profile_persisted": False,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-observation", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = collect(json.loads(args.source_observation.read_text("utf-8")))
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "QUERIES", result["original_first_party_query_count"],
        "UNIQUE_FIRST_PAGE", result["source_first_page_unique_ids"],
        "DETAILS", result["original_detail_pages_verified"],
        "SOFTWARE_DEV", result["narrow_first_pages_bespoke_software_development_confirmed"],
    )


if __name__ == "__main__":
    main()
