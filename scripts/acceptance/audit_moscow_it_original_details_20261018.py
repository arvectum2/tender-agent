"""Source-pinned, read-only original Moscow quote details for 3 IT-looking goods.

Only exact public original quote URLs discovered through the site's own UI.
No application, authentication, attachment download, bidding or API guesses.
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

from lxml import html as lxml_html

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SSD_TMP = "/Volumes/ArvectumSSD/Arvectum/tmp"
SOURCE_CASES = {
    "10321203": {
        "buyer": 'АКЦИОНЕРНОЕ ОБЩЕСТВО "ГОСТИНИЧНЫЙ КОМПЛЕКС "БЕРЛИН"',
        "inn": "7727841506",
        "price_rub": "671557.00",
        "deadline_msk_day": "19.10.2026",
        "exact_products": ("Системный блок BigTech PC S5006", "SSD накопитель AMD Radeon"),
        "scope": "COMPUTERS_SSD_MONITORS_GOODS_NOT_SOFTWARE_DEVELOPMENT",
    },
    "10321182": {
        "buyer": "МОСКОВСКИЙ ГОСУДАРСТВЕННЫЙ АКАДЕМИЧЕСКИЙ ТЕАТР ОПЕРЕТТЫ",
        "inn": "7707086767",
        "price_rub": "215576.34",
        "deadline_msk_day": "19.10.2026",
        "exact_products": ("Объектив OM SYSTEM M.Zuiko", "Manfrotto MVKBFRL-LIVE"),
        "scope": "PHOTOGRAPHIC_EQUIPMENT_NOT_SOFTWARE_DEVELOPMENT",
    },
    "10321235": {
        "buyer": "Школа-интернат № 1 для обучения и реабилитации слепых",
        "inn": "7717067481",
        "price_rub": "183600.00",
        "deadline_msk_day": "19.10.2026",
        "exact_products": ("Наушники Яндекс Дропс с Алисой", "Колонка портативная COMMO STAGE"),
        "scope": "HEADPHONES_SPEAKERS_POWERBANKS_NOT_SOFTWARE_DEVELOPMENT",
    },
}


def _clean_html(rendered_html: str) -> tuple[str, object]:
    root = lxml_html.fromstring(rendered_html)
    for node in root.xpath("//script|//style|//noscript"):
        node.drop_tree()
    text = " ".join(root.xpath("//body//text()"))
    return " ".join(text.split()), root


def verify_original(number: str, rendered_html: str, observed: datetime) -> dict:
    if number not in SOURCE_CASES or observed.utcoffset() is None:
        raise ValueError("unapproved original or naive observed_at")
    if not 10_000 <= len(rendered_html) <= 20_000_000:
        raise ValueError("unexpected browser rendered HTML size")
    case = SOURCE_CASES[number]
    plain, root = _clean_html(rendered_html)
    title = " ".join(root.xpath("string(//title)").split())
    if (
        f"Котировочная сессия {number}" not in title
        or f"Котировочная сессия {number}" not in plain[:600]
        or "Активная" not in plain[:650]
        or "Для участия в котировочной сессии необходимо авторизоваться" not in plain
        or case["buyer"].casefold() not in plain.casefold()
        or case["deadline_msk_day"] not in plain
    ):
        raise ValueError("original title/current status/buyer/deadline/authorization not attested")
    for phrase in case["exact_products"]:
        if phrase.casefold() not in plain.casefold():
            raise ValueError("first-party specific line item not attested")
    # Scope is explicitly goods, with original named line items. It does not
    # assert that no software is present in a group of goods.
    originals = []
    for link in root.xpath("//a[@href]"):
        label = " ".join(link.itertext()).strip()
        href = link.get("href", "")
        p = urlsplit(href)
        if (
            p.scheme == "https"
            and p.hostname == "zakupki.mos.ru"
            and p.path == "/newapi/api/FileStorage/Download"
            and re.fullmatch(r"id=\d+", p.query)
        ):
            originals.append({"display_label": label[:115], "public_attachment_link_visible": True})
    if not originals:
        raise ValueError("no public original tender document links")
    return {
        "id": number,
        "exact_original_url": f"https://zakupki.mos.ru/auction/{number}",
        "original_rendered_html_sha256": hashlib.sha256(rendered_html.encode("utf-8")).hexdigest(),
        "observed_at_utc": observed.isoformat(),
        "source_detail_title": title,
        "listed_buyer_inn_not_reverified_inside_detail": case["inn"],
        "source_buyer_name_in_detail": case["buyer"],
        "listed_starting_price_rub": case["price_rub"],
        "source_deadline_day_msk": case["deadline_msk_day"],
        "source_scope_classification": case["scope"],
        "original_product_line_proofs": list(case["exact_products"]),
        "original_visible_document_labels": originals,
        "company_bidding_requires_authorization_in_source": True,
        "is_custom_software_development_contract": False,
        "verified_company_can_respond": False,
        "original_attached_files_downloaded": False,
    }


def audit_public_search_observation(raw: dict) -> dict:
    if raw.get("state") != "PUBLIC_FIRST_PARTY_IT_SEARCH_COMPLETED":
        raise ValueError("browser public search not complete")
    searches = raw.get("searches")
    if not isinstance(searches, list) or len(searches) != 6:
        raise ValueError("expected six first-party search terms")
    expected = (
        "программного обеспечения", "создание сайта", "информационной системы",
        "сопровождение", "разработка сайта", "программирование",
    )
    result = []
    for item, term in zip(searches, expected, strict=True):
        if (
            item.get("term") != term or item.get("exact_applied_query") is not True
            or item.get("public_status_gate") != [19000002]
            or item.get("first_page_only") is not True
        ):
            raise ValueError("one filter not attested by official resulting browser URL")
        links = item.get("original_detail_links")
        if not isinstance(links, list) or len(links) > 36:
            raise ValueError("search result source links unbounded")
        extracted = []
        seen: set[str] = set()
        for link in links:
            p = urlsplit(link.get("url", ""))
            match = re.fullmatch(r"/auction/(\d{8})", p.path)
            if (
                p.scheme != "https" or p.hostname != "zakupki.mos.ru"
                or p.username or p.password or p.port is not None
                or match is None
            ):
                raise ValueError("non-original auction URL entered result")
            number = match.group(1)
            if number not in seen:
                seen.add(number)
                extracted.append(number)
        text = item.get("html_public_visible_text", "")
        if not isinstance(text, str) or len(text) > 10200:
            raise ValueError("source snippet missing or unbounded")
        if not extracted and "Ничего не нашлось" not in text:
            raise ValueError("missing both original cards and no-match source proof")
        result.append({
            "exact_public_term": term,
            "source_first_page_only": True,
            "state_gate_active_public": True,
            "original_card_ids_with_visible_links": extracted,
            "original_card_links_with_source_confirmation": len(extracted),
            "explicit_no_results_page": not bool(extracted),
            "has_source_original_public_listing": bool(extracted),
        })
    return {"queries": result, "number_of_queries": len(result)}


def _public_browser_html(number: str) -> str:
    if number not in SOURCE_CASES:
        raise ValueError("unapproved original source")
    with tempfile.TemporaryDirectory(prefix="ta-mos-it-original-", dir=SSD_TMP) as path:
        call = [
            CHROME, "--headless=new", "--disable-gpu", "--disable-extensions",
            "--disable-sync", "--no-first-run", "--no-default-browser-check",
            "--disable-background-networking", "--user-data-dir=" + path,
            "--virtual-time-budget=13500", "--dump-dom",
            "https://zakupki.mos.ru/auction/" + number,
        ]
        r = subprocess.run(call, text=True, capture_output=True, timeout=32, check=False)
    if r.returncode != 0:
        raise ValueError("original public browser returned error")
    return r.stdout


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--source-observation", required=True, type=Path)
    cli.add_argument("--out", required=True, type=Path)
    args = cli.parse_args()
    saved = json.loads(args.source_observation.read_text("utf-8"))
    search = audit_public_search_observation(saved)
    visible_ids = {x for row in search["queries"] for x in row["original_card_ids_with_visible_links"]}
    if not set(SOURCE_CASES).issubset(visible_ids):
        raise ValueError("one inspected original missing from public search")
    detail_rows = [
        verify_original(number, _public_browser_html(number), datetime.now(UTC))
        for number in SOURCE_CASES
    ]
    output = {
        "schema_version": "ta-b2g-moscow-public-original-it-keyword-filter-2026-10-18-v1",
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "official_source": "https://zakupki.mos.ru/",
        "public_registry_real_ui_filters_applied": True,
        "public_auction_active_state_code_from_visible_page": 19000002,
        "search_result_filters": search["queries"],
        "query_count": search["number_of_queries"],
        "original_detail_pages_verified": len(detail_rows),
        "original_details": detail_rows,
        "current_it_custom_development_scope_originals_verified": 0,
        "claim_that_no_more_it_auctions_exist": False,
        "company_full_registration_or_ukep_tested": False,
        "company_able_to_bid_verified": False,
        "current_eligible_b2b_increment": 0,
        "outgoing_actions_or_payments": 0,
        "disposable_browser_profile_saved": False,
    }
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("FILTERS",len(search["queries"]),"DETAILS",len(detail_rows),"DEV_SCOPE",output["current_it_custom_development_scope_originals_verified"])


if __name__ == "__main__":
    main()
