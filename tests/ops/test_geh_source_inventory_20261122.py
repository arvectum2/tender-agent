"""Offline source and authority gates for the GEH procurement inventory."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JSON = ROOT / "docs/roadmap/ta_geh_source_reuse_inventory_20261122.json"
REPORT = ROOT / "docs/roadmap/TA_GEH_SOURCE_ACCESS_REUSE_MATRIX_20261122.md"


def load():
    return json.loads(JSON.read_text(encoding="utf8"))


def test_no_live_or_production_acceptance_from_inventory():
    data = load()
    assert data["scope"] == "TA-GEH-SOURCE-DISCOVERY-001"
    assert data["authority"] == "public_first_party_metadata_and_existing_repository_only"
    assert data["fresh_223fz_originals_downloaded"] == 0
    assert data["live_platform_api_verified"] is False
    assert data["real_geh_contractor_network_verified"] is False
    assert data["production_mutations"] == 0


def test_six_source_classes_are_distinct():
    sources = {entry["id"]: entry for entry in load()["sources"]}
    assert len(sources) == 6
    assert set(sources) == {
        "mosenergo_tenders", "official_eis_ri223", "etp_gpb_corporate",
        "mosenergo_results_history", "mosenergo_prequalification", "tektorg_corporate",
    }
    assert sources["mosenergo_tenders"]["role"] != sources["etp_gpb_corporate"]["role"]
    assert sources["tektorg_corporate"]["role"].startswith("possible_third_party_contractor")
    assert sources["mosenergo_results_history"]["current_live_coverage"] == "HISTORICAL_ONLY"
    assert all(source["archive_24_36m"] != "VERIFIED" for source in sources.values())


def test_historical_coverage_not_inferred_from_99_day_display():
    coverage = load()["historical_coverage"]
    assert coverage["mosenergo_landing_declares_trailing_days"] == 99
    assert coverage["actual_rows_independently_ingested"] == 0
    assert coverage["months_24_36_reconciled"] is False
    assert coverage["buyer_to_organizer_mapping_verified"] is False
    assert coverage["contractor_chain_verified"] is False
    assert coverage["do_not_conflate_platform_organizer_and_contractor"] is True


def test_candidate_soap_endpoints_are_not_authorized_or_tested():
    data = load()
    assert len(data["candidate_integration_endpoints"]) == 2
    for entry in data["candidate_integration_endpoints"]:
        assert entry["status"] == "UNTESTED_NO_AUTHORITY"
        assert entry["permissions"] == "UNKNOWN"
        assert entry["buyer_filter"] == "UNKNOWN"
        assert entry["url"].startswith("https://")
    assert "run_untested_soap" in data["forbidden"]
    assert "authenticated_etp" in data["forbidden"]


def test_sources_use_existing_code_and_reject_bidding():
    data = load()
    assert len(data["reusable_modules"]) >= 6
    assert all((ROOT / path).is_file() for path in data["reusable_modules"])
    assert data["entity_membership_verified_current"] is False
    assert {"production_write", "bid_submission", "payment", "supplier_outreach"} <= set(data["forbidden"])
    text = REPORT.read_text(encoding="utf8")
    assert "24–36" in text and "NOT accepted" in text
