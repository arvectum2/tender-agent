"""Offline-only source and non-executable paper trading inventory checks."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs/roadmap/ta_ai_trading_source_reuse_inventory_20261122.json"
REPORT = ROOT / "docs/roadmap/TA_AI_TRADING_SOURCE_REUSE_PAPER_ONLY_20261122.md"


def load():
    return json.loads(DATA.read_text(encoding="utf8"))


def test_only_paper_simulation_authorized():
    d = load()
    assert d["scope"] == "TA-AI-TRADING-SOURCE-DISCOVERY-001"
    assert d["mode"] == "PAPER_SIMULATION_ONLY"
    assert d["real_bid_allowed"] is d["real_order_allowed"] is False
    assert d["supplier_messages_allowed"] is False
    assert d["account_or_paid_access_used"] is d["live_api_discovered"] is False
    assert d["production_mutations"] == 0
    assert {"real_bid", "real_order", "payment", "catalog_posting", "credential_use"} <= set(d["forbidden"])


def test_five_platforms_distinct_market_identity():
    d = load()
    by = {x["id"]: x for x in d["sources"]}
    assert len(by) == len(d["sources"]) == 5
    assert set(by) == {
        "moscow_supplier_portal", "eat_berezka", "rts_market",
        "sber_a_shop", "gpb_clickmarket",
    }
    assert len({x["source_id"] for x in by.values()}) == 5
    assert all(x["official_root"].startswith("https://") for x in by.values())
    assert all(x["api_access"] == "NOT_VERIFIED" and x["open_now_proven"] is False
               for x in by.values())
    assert by["moscow_supplier_portal"]["source_kind"] != by["eat_berezka"]["source_kind"]


def test_source_correct_economic_simulation_has_no_lookahead():
    contract = load()["evidence_contract"]
    assert contract["time_correct_replay"] is True
    assert contract["include_only_information_public_at_simulation_time"] is True
    assert contract["missing_supplier_stock_mark_UNKNOWN"] is True
    assert contract["no_backfilling_future_winning_price_into_past_decision"] is True
    assert contract["classify_independent_observed_vs_hypothetical"] is True
    required = set(contract["required_for_each_paper_case"])
    assert {"original_document_sha256", "source_publication_timestamp", "observation_timestamp",
            "requested_quantity", "unit_of_measure", "landed_purchase_cost", "delivery_cost",
            "tax", "platform_fee", "working_capital_peak", "observed_result_if_any"} <= required


def test_no_faked_financial_observations_or_automation_percent():
    stats = load()["sample_proof"]
    assert stats["original_cases_pinned_for_this_task"] == 0
    assert stats["simulated_bids_run"] == 0
    assert stats["real_observed_wins"] == 0
    assert stats["real_purchases"] == 0
    assert stats["automation_percent_measured"] is False
    assert "NOT_MEASURED" in REPORT.read_text(encoding="utf8")


def test_existing_reuse_modules_and_manual_gates():
    d = load()
    assert all((ROOT / path).is_file() for path in d["reusable_modules"])
    assert len(d["reusable_modules"]) >= 8
    assert "separate_owner_approval_for_any_live_procurement" in d["open_gates"]
    assert "offline_backtest_and_operator_review" in d["open_gates"]
    assert "etp_private_crawl" in d["forbidden"]
