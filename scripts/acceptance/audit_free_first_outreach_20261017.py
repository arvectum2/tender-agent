"""Read-only first-party free outbound channel receipts: not bidder authorization."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

SOURCES = {
    "fl": ("https://www.fl.ru/", ("для всех", "пакет откликов")),
    "pchel": ("https://pchel.net/help/projects/", ("100 заявок", "1000$", "Студии")),
    "codelance": ("https://www.codelance.ru/site/razrabotchikam", ("бесплатно", "отклик")),
    "contractis": ("https://contractis.ru/remote/zakazy-dlya-mobilnyh-razrabotchikov",
                    ("бесплатн", "PRO", "лимит")),
    "itsnew": ("https://itsnew.ru/board", ("Задания",)),
}
ORDERS = {
    "contractis_python_ai": (
        "https://contractis.ru/order/ishchu-podryadchika-na-razrabotku-po-na-python-rabota-s-ii",
        ("170 000", "Python", "Windows", "Linux"),
    ),
    "contractis_landing": (
        "https://contractis.ru/order/razrabotka-lendinga",
        ("90 000", "150 000", "строительной компании"),
    ),
    "codelance_catalog_integration": (
        "https://www.codelance.ru/orders/view?id=147",
        ("Парсинг на сайт", "XML", "JSON"),
    ),
}
RULES = {
    "fl": ("FREE_ONLY_FOR_ALL_AND_VACANCIES_CONTESTS", "UNKNOWN"),
    "pchel": ("STANDARD_STUDIO_100_PER_MONTH_UP_TO_1000_USD", "UNKNOWN"),
    "codelance": ("ADVERTISED_UNLIMITED_FREE_REPLIES", "UNKNOWN"),
    "contractis": ("FREE_MONTHLY_CAPPED_CHATS_CONTACTS_PRO_ONLY", "UNKNOWN"),
    "itsnew": ("VISIBLE_TASKS_FREE_REPLY_TERMS_NOT_ATTESTED", "UNKNOWN"),
}


def plain(raw: bytes) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", raw.decode("utf-8", "strict"))).split())


def _first_party_get(url: str, key: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="ta-free-source-") as folder:
        output_file = Path(folder) / "first_party.html"
        done = subprocess.run(["curl", "-q", "--noproxy", "*", "--silent", "--show-error",
                               "--location", "--compressed", "--connect-timeout", "5", "--max-time", "12",
                               "--output", str(output_file), "--write-out", "%{http_code} %{url_effective}", url],
                              capture_output=True, text=True, timeout=15, check=True)
        if done.stdout.strip() != f"200 {url}":
            raise ValueError(f"unexpected source code/final URL: {key}")
        return output_file.read_bytes()


def observe() -> dict:
    output = []
    for typ, table in (("platform_policy", SOURCES), ("example_original_customer_order", ORDERS)):
        for key, (url, required) in table.items():
            if not (url.startswith("https://") and
                    url.split("/")[2] in ("www.fl.ru", "pchel.net", "www.codelance.ru",
                                          "contractis.ru", "itsnew.ru")):
                raise ValueError("unexpected source host")
            try:
                raw = _first_party_get(url, key)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, OSError) as err:
                output.append({"id":key,"source_type":typ,"source_url":url,"verified_this_run":False,"fetch_problem":type(err).__name__,"company_account_reply_tested":False,"contract_with_russian_llc_accepted":False,"message_submitted":False,"paid_action_executed":False})
                print("SOURCE_UNAVAILABLE",key,type(err).__name__)
                continue
            if not 1000 < len(raw) <= 550000:
                raise ValueError(f"source bytes invalid: {key}")
            body = plain(raw)
            missing = [x for x in required if x.casefold() not in body.casefold()]
            if missing:
                raise ValueError(f"unsupported source clauses {key}: {missing}")
            row = {
                "id": key,
                "source_type": typ,
                "source_url": url,
                "verified_this_run": True,
                "observed_at_utc": datetime.now(UTC).isoformat(),
                "http_status": 200,
                "source_sha256": hashlib.sha256(raw).hexdigest(),
                "source_bytes": len(raw),
                "source_literal_requirement_excerpts": list(required),
                "company_account_reply_tested": False,
                "contract_with_russian_llc_accepted": False,
                "message_submitted": False,
                "paid_action_executed": False,
                "original_customer_verification_complete": False,
            }
            if typ == "platform_policy":
                row["advertised_or_documented_free_entry_rule"] = RULES[key][0]
                row["actual_final_zero_cost_for_our_llc_account"] = RULES[key][1]
            output.append(row)
            print("SOURCE_OK", key, len(raw), row["source_sha256"][:12])
            continue
    return {
        "schema_version": "arvectum-b2b-free-first-outreach-original-source-20261017-v1",
        "observed_date": "2026-10-17",
        "first_party_policy_count": sum(x.get("verified_this_run", False) for x in output if x["source_type"]=="platform_policy"),
        "first_party_example_order_count": sum(x.get("verified_this_run", False) for x in output if x["source_type"]=="example_original_customer_order"),
        "independently_proven_llc_first_bid_entitlement_count": 0,
        "source_count_requested": len(SOURCES)+len(ORDERS),
        "authenticated_reply_success_count": 0,
        "paid_actions_or_messages_sent": 0,
        "is_published_no_reply_needed_for_customer_chat": False,
        "entries": output,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if args.out.name != "b2b_free_first_outreach_sources_2026-10-17.json":
        p.error("date-scoped source receipt filename only")
    args.out.write_text(json.dumps(observe(), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
