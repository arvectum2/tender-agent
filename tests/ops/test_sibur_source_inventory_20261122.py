"""Bounded, fully offline QA for source-separated SIBUR inventory evidence."""
import json
from pathlib import Path

from src.modules.tender_connectors.sibur.archive_parser import CATEGORIES

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs/roadmap"
DATA = DOCS / "ta_sibur_source_reuse_inventory_20261122.json"
REPORT = DOCS / "TA_SIBUR_SOURCE_ACCESS_REUSE_MATRIX_20261122.md"


def load():
    return json.loads(DATA.read_text(encoding="utf8"))


def test_no_claim_to_current_live_or_authenticated_source_access():
    data = load()
    assert data["scope"] == "TA-SIBUR-SOURCE-DISCOVERY-001"
    assert data["current_live_procurements_verified"] is False
    assert data["authorized_srm_session"] is False
    assert data["new_db_mutations"] == 0
    by = {item["id"]: item for item in data["sources"]}
    assert len(by) == len(data["sources"]) == 6
    assert by["sibur_public_current"]["source_namespace"] == "sibur_public"
    assert by["sibur_public_archive"]["live_legal_status"] == "HISTORICAL_ONLY"
    assert by["sibur_srm_supplier_console"]["historical_coverage"] == "UNKNOWN"
    assert by["sibur_srm_supplier_console"]["access"] == "supplier_registration_and_qualification_required"
    assert by["sibur_logistics_7rights"]["source_namespace"] != "sibur_public"


def test_b2b_sales_never_count_as_direct_sibur_buying():
    by = {x["id"]: x for x in load()["sources"]}
    seller = by["b2b_center_sibur"]
    assert "seller_examples" in seller["role"]
    assert seller["source_namespace"] == by["b2b_center_market"]["source_namespace"]
    assert seller["source_namespace"] != by["sibur_public_current"]["source_namespace"]
    assert by["b2b_center_market"]["role"].endswith("UNKNOWN_without_original_card")
    assert all(x["live_legal_status"] != "VERIFIED_CURRENT_OPEN" for x in by.values())


def test_history_counts_and_missing_ids_reconcile():
    evidence = load()["saved_evidence"]
    original = evidence["first_party_20261114"]
    assert original["observations"] == original["unique_exact_ids"] + 1
    assert original["pages"] == 27 and original["unique_document_urls"] == 516
    archive = evidence["historic_archive_20261121"]
    assert archive["observations"] == archive["unique_ids"] + archive["repeat_observations"]
    assert archive["pages"] == 4052 and archive["categories"] == len(CATEGORIES) == 9
    working = evidence["working_db_20261121"]
    assert working["database"] == "arvectum_local" and working["not_production_db"]
    assert archive["unique_ids"] - working["overlap_with_archive"] == working["archive_missing_in_working"] == 18251
    assert working["distinct_sibur_public_external_ids"] - working["overlap_with_archive"] == working["working_extra_to_archive"] == 551
    by_category = evidence["historic_missing_by_category"]
    assert set(by_category) == set(CATEGORIES)
    assert sum(by_category.values()) == 18251


def test_document_provenance_exceptions_and_dp_evidence_preserved():
    evidence = load()["saved_evidence"]
    docs = evidence["original_documents_20261121"]
    assert docs["saved_source_urls"] == docs["byte_and_size_hash_verified"] == 516
    assert docs["url_extension_matches_saved_file"] + docs["ambiguous_ppt_vs_pptx"] == 516
    assert docs["source_mismatch_issue"] == 686
    dp = evidence["data_platform_old_receipts"]
    assert dp["archived_source_files_sha_verified"] == 7
    assert dp["direct_source_url_attested"] + dp["unattested_from_this_registry"] == 7
    assert dp["matching_chunk_and_embedding_identities"] == 958
    assert dp["live_dp_current_verified"] is False


def test_reuse_targets_exist_and_inventory_is_nonoperational():
    data = load()
    for name in data["reusable_modules"]:
        assert (ROOT / name).is_file(), name
    assert "mass_import" in data["forbidden"]
    assert "bidding" in data["forbidden"]
    assert "authenticated_srm_crawl" in data["forbidden"]
    text = REPORT.read_text(encoding="utf8")
    assert "NOT a live" in text
    assert "#692" in text and "#686" in text
    assert "read" in data["next_stage"] and "import" not in data["next_stage"]



def test_saved_private_receipt_hashes_are_sha256_strings():
    digests = load()["saved_evidence"]["private_historical_receipt_sha256"]
    assert set(digests) == {"archive_corpus", "saved_documents", "old_dp_provenance"}
    assert all(len(value) == 64 and all(char in "0123456789abcdef" for char in value)
               for value in digests.values())
