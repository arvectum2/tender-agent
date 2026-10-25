"""Ten known exact first-party Workspace mobile-development cards; no ETP action."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.acceptance.audit_workspace_oct17_cards import extract_public_card

_MOBILE = {
    "19041": ("sozdanie-mobilnogo-prilozheniya-dlya-myasokombinata", "2026-10-31", "FIT_NEW_POSSIBLE_SAME_BUYER_19042"),
    "19010": ("dorabotka-dizayna-mobilnogo-prilozheniya", "2026-10-17", "EXCLUDE_SAME_DAY_CUTOFF_TIME_UNKNOWN"),
    "19007": ("platforma-yuridicheskoy-pomoschi", "2026-10-20", "EXCLUDE_PERSON_ORGANIZER"),
    "18998": ("prilozhenie-s-golosovym-ii-pitomcem-dlya-detskih-4g-smart-chasov-android-8-1-bez-google-servisov-server", "2026-10-31", "FIT_ALREADY_HISTORICAL_POOL"),
    "18974": ("mobilnoe-prilozhenie-dostavki", "2026-10-02", "EXCLUDE_TERMINAL"),
    "18979": ("razrabotka-b2c-logisticheskoy-erp-tms-sistemy-i-mobilnogo-prilozheniya-dostavka-iz-kitaya", "2026-10-12", "EXCLUDE_TERMINAL"),
    "18966": ("zavershenie-i-zapusk-mobilnogo-prilozheniya-pod-klyuch", "2026-10-01", "EXCLUDE_TERMINAL"),
    "18952": ("dorabotka-tehnicheskogo-zadaniya-i-razrabotka-krossplatformennogo-fitness-prilozheniya-dlya-ios-android-i-web", "2026-09-24", "EXCLUDE_TERMINAL_PERSON"),
    "18939": ("razrabotat-mvp-dlya-investorov-i-v-dalneyshem-razrabatyvat-mobilnoe-prilozhenie-cifrovoy-dvoynik-zdorovya-i-razvitiya-s-sobstvennym-profilem-na-baze-ii", "2026-12-15", "FIT_NEW_COMPLEX_AI_RND"),
    "18932": ("mvp-mobilnoe-prilozhenie-ios-android-mini-marketpleys-fermerskih-produktov", "2026-09-12", "EXCLUDE_TERMINAL_PERSON"),
}
_MAX_BYTES = 400_000


def classify_mobile_2026_snapshot(card: dict) -> str:
    """Incremental candidate state, never participation authorization."""
    if card["source_status_gate"] != "PUBLIC_CANDIDATE_ONLY":
        return "EXCLUDED_OR_UNVERIFIED"
    if card["id"] == "workspace-18998":
        return "CURRENT_PUBLIC_HISTORICAL_ALREADY_COUNTED"
    if card["id"] == "workspace-19041":
        return "NEW_CARD_BUT_POSSIBLE_SHARED_BUYER_19042"
    if card["id"] == "workspace-18939":
        return "NEW_CARD_COMPLEX_AI_REVIEW"
    raise ValueError("unknown or unexpected candidate not previously audited")


def collect() -> dict:
    opener = build_opener(ProxyHandler({}))
    items = []
    for key, (slug, _, _) in _MOBILE.items():
        url = f"https://workspace.ru/tenders/{slug}-{key}/"
        with opener.open(
            Request(url, headers={"User-Agent": "ArvectumTenderAgent-SourceResearch/1.0"}),
            timeout=12,
        ) as response:
            if response.status != 200 or response.geturl() != url:
                raise ValueError(f"original mobile public card redirect for {key}")
            raw = response.read(_MAX_BYTES + 1)
        item = extract_public_card(raw, key=key, observed=datetime.now(UTC), allowed_cards=_MOBILE)
        item["counting_disposition"] = classify_mobile_2026_snapshot(item)
        item["possible_shared_customer_project"] = key == "19041"
        item["same_day_time_unknown"] = key == "19010"
        items.append(item)
    if len(items) != 10 or len({v["id"] for v in items}) != 10:
        raise ValueError("unexpected mobile source count")
    new = [x for x in items if x["counting_disposition"].startswith("NEW_CARD")]
    old = [x for x in items if x["counting_disposition"].startswith("CURRENT_PUBLIC_HISTORICAL")]
    rejected = [x for x in items if x["counting_disposition"] == "EXCLUDED_OR_UNVERIFIED"]
    if (
        {x["id"] for x in new} != {"workspace-19041", "workspace-18939"}
        or {x["id"] for x in old} != {"workspace-18998"}
        or len(rejected) != 7
    ):
        raise ValueError("unexpected dated mobile source status")
    return {
        "schema_version": "b2b-workspace-mobile-original-oct17-v1",
        "checked_date": "2026-10-17",
        "original_platform": "workspace.ru",
        "bounded_exact_readonly_public_cards": 10,
        "new_original_distinct_card_ids": 2,
        "new_distinct_procurement_business_opportunities_confirmed": False,
        "existing_historical_distinct_card_counted_again": 0,
        "historical_still_receiving_card": "workspace-18998",
        "new_card_ids": [x["id"] for x in new],
        "excluded_or_needs_review": len(rejected),
        "actual_eligible_bids": 0,
        "qualifying_source_goal_15_20_met": False,
        "etp_action": "NONE",
        "public_original_receipts": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    options = parser.parse_args()
    if options.out.name != "b2b_workspace_mobile_original_2026-10-17.json":
        parser.error("only versioned evidence file allowed")
    result = collect()
    options.out.parent.mkdir(parents=True, exist_ok=True)
    options.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print("MOBILE_NEW_SOURCE_CARDS", result["new_original_distinct_card_ids"],
          "REVIEW_OR_EXCLUDED", result["excluded_or_needs_review"],
          "BID_READY", result["actual_eligible_bids"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
