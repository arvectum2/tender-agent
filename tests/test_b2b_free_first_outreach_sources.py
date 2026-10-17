"""Original free-first-response discovery is not a successful company bid."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from scripts.acceptance.audit_free_first_outreach_20261017 import ORDERS, RULES, SOURCES

ROOT = Path(__file__).resolve().parents[1] / "docs/roadmap"
D = json.loads((ROOT / "b2b_free_first_outreach_sources_2026-10-17.json").read_text())
ROWS = {r["id"]: r for r in D["entries"]}


def test_bounded_sources_and_no_outreach_or_paid_claim():
    assert D["schema_version"] == "arvectum-b2b-free-first-outreach-original-source-20261017-v1"
    assert D["source_count_requested"] == len(SOURCES) + len(ORDERS) == 8
    assert set(ROWS) == set(SOURCES) | set(ORDERS)
    assert D["first_party_policy_count"] >= 3
    assert D["first_party_example_order_count"] == 3
    assert D["independently_proven_llc_first_bid_entitlement_count"] == 0
    assert D["authenticated_reply_success_count"] == 0
    assert D["paid_actions_or_messages_sent"] == 0
    assert D["is_published_no_reply_needed_for_customer_chat"] is False


def test_first_party_verified_sources_have_original_sha_and_exact_urls():
    for key, row in ROWS.items():
        assert row["source_url"] == (SOURCES.get(key) or ORDERS[key])[0]
        assert row["company_account_reply_tested"] is False
        assert row["contract_with_russian_llc_accepted"] is False
        assert row["message_submitted"] is False
        assert row["paid_action_executed"] is False
        if not row["verified_this_run"]:
            assert row["fetch_problem"] in ("CalledProcessError", "TimeoutExpired", "ValueError", "OSError")
            assert "source_sha256" not in row
            continue
        assert row["http_status"] == 200
        assert 1000 < row["source_bytes"] < 550000
        assert re.fullmatch("[0-9a-f]{64}", row["source_sha256"])
        assert datetime.fromisoformat(row["observed_at_utc"]).tzinfo is not None
        assert row["source_literal_requirement_excerpts"]


def test_seller_ads_and_free_to_post_do_not_prove_customer_or_llc_access():
    for name in SOURCES:
        r = ROWS[name]
        if not r["verified_this_run"]:
            continue
        assert r["advertised_or_documented_free_entry_rule"] == RULES[name][0]
        assert r["actual_final_zero_cost_for_our_llc_account"] == "UNKNOWN"
        assert r["original_customer_verification_complete"] is False
    assert "UNLIMITED_FREE" in RULES["codelance"][0]
    assert "1000_USD" in RULES["pchel"][0]
    assert "NOT_ATTESTED" in RULES["itsnew"][0]


def test_real_three_individual_sources_are_not_qualified_bids():
    for key in ORDERS:
        row = ROWS[key]
        assert row["verified_this_run"] is True
        assert row["source_type"] == "example_original_customer_order"
        assert row["original_customer_verification_complete"] is False
        assert row["source_bytes"] > 30000


def test_report_notes_original_false_freshness_and_hidden_legal_gates():
    text = (ROOT / "B2B_FREE_FIRST_OUTREACH_CHANNELS_2026-10-17.md").read_text()
    for part in ("FL.ru", "CONTRACTIS", "Pchel.net", "CodeLance", "Weblancer", "IT'S NEW",
                 "170 000 ₽", "90–150 тыс. ₽", "№147", "«Закрыт»",
                 "ООО", "не подтверждены", "100", "до $1000"):
        assert part.casefold() in text.casefold()
    assert "автоматических" not in text or "не" in text
