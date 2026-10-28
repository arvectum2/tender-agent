import hashlib
import json
from pathlib import Path

import pytest

from src.modules.market_intelligence.pq_primary_etp_capture import capture
from src.modules.market_intelligence.pq_research_coverage import (
    _months,
    _source_year,
    build,
)

ETP = "https://bidzaar.com/app/process/light/019fb323-f23b-7872-845e-ba2cb6b43355"


def _fixture(tmp_path: Path):
    leads = tmp_path / "leads.json"
    leads.write_text(json.dumps({
        "records": [
            {"canonical_id": "223:32616339168:lot1", "procedure_id": "32616339168",
             "family": "capacitor_bank", "scope": "supply",
             "evidence": [{"source_tier": "primary_eis", "url": "https://zakupki.gov.ru/223/"}]},
            {"canonical_id": "etp:358-830", "procedure_id": "358-830",
             "family": "harmonic_filter", "scope": "supply",
             "evidence": [{"source_tier": "primary_platform", "url": ETP}]},
            {"canonical_id": "secondary:no-id", "procedure_id": None,
             "family": "ukrm", "scope": "unknown",
             "evidence": [{"source_tier": "third_party", "url": "https://example.com/card"}]},
        ]}))
    official = tmp_path / "public"
    case = official / "32616339168"
    case.mkdir(parents=True)
    blob = b"Original receipt verified byte stream"
    sha = hashlib.sha256(blob).hexdigest()
    (case / "original.pdf").write_bytes(blob)
    (case / "public-page-receipt.json").write_text(json.dumps({
        "schema_version": "pq-223-public-page-download/1",
        "registry_number": case.name,
        "status": "public_page_files_downloaded",
        "files": [{"filename": "original.pdf", "sha256": sha}]}))
    filestore = tmp_path / "filestore"
    filestore.mkdir()
    original_etp = tmp_path / "etp"
    html = (
        "<!DOCTYPE html><html><head>"
        "<title>Тендер 358-830 — Поставка активных фильтров гармоник | Bidzaar</title>"
        f'<meta property="og:url" content="{ETP}">'
        '<meta name="description" content="ВАЙЛДБЕРРИЗ — Поставка фильтров гармоник">'
        "</head></html>"
    ).encode()
    card = capture(number="358-830", url=ETP,
                   source_root=original_etp,
                   fetch=lambda _: (html, ETP))
    facts = tmp_path / "facts.json"
    facts.write_text(json.dumps({
        "schema_version": "pq-primary-etp-facts/1",
        "facts": [{
            "procedure_id": "358-830", "slug": ETP.rsplit("/", 1)[-1],
            "expected_sha256": card["original_html_sha256"],
            "source_quote": "Поставка активных фильтров гармоник",
            "platform_displayed_organizer": "ВАЙЛДБЕРРИЗ",
            "scope": "equipment_supply_tender", "family": "active_harmonic_filter",
            "signed_contract_verified": False,
        }]}))
    return {"leads": leads, "public223": official, "filestore": filestore,
            "etp_facts": facts, "etp_originals": original_etp}


def test_synthetic_source_coverage_no_market_inference(tmp_path: Path):
    sources = _fixture(tmp_path)
    result = build(**sources)
    assert result["candidate_denominator"] == 3
    assert result["source_category_counts"] == {
        "223fz": 1, "commercial_or_unresolved": 2}
    assert result["candidate_rows_with_primary_original"] == 2
    assert result["candidate_rows_without_verified_primary_original"] == 1
    assert result["distinct_223_notice_numbers"] == 1
    assert result["numbered_223_candidate_lot_rows"] == 1
    assert result["unique_notice_or_etp_numbers_with_primary_original"] == 2
    assert result["primary_original_source_types"]["official_223_unique_notices_with_files"] == 1
    assert result["primary_original_source_types"]["original_commercial_etp_unique_cards"] == 1
    assert all(row["coverage_state"] == "not_demonstrated"
               for row in result["period_search_coverage"])
    assert len(result["period_search_coverage"]) == 34
    assert result["cases"][-1]["primary_source_state"] == "secondary_or_unverified_source_only"
    assert all(row["signed_contract_supplier_verified"] is False for row in result["cases"])
    assert _source_year("32616339168") == 2026
    assert result["source_223_year_hint_not_publication_date"]["2026"]["distinct_223_notices"] == 1


def test_absent_documents_not_zero_market(tmp_path: Path):
    sources = _fixture(tmp_path)
    case = sources["public223"] / "32616339168"
    (case / "original.pdf").unlink()
    receipt = case / "public-page-receipt.json"
    r = json.loads(receipt.read_text())
    r["files"] = []
    r["status"] = "no_files_saved"
    receipt.write_text(json.dumps(r))
    result = build(**sources)
    assert result["cases"][0]["primary_source_state"] == "official_notice_receipt_without_files"
    assert result["candidate_rows_with_primary_original"] == 1
    assert result["completeness"] == "partial_period_discovery_not_established"


def test_source_ledger_must_have_unique_canonical_ids(tmp_path: Path):
    sources = _fixture(tmp_path)
    data = json.loads(sources["leads"].read_text())
    data["records"][1]["canonical_id"] = data["records"][0]["canonical_id"]
    sources["leads"].write_text(json.dumps(data))
    with pytest.raises(ValueError, match="duplicate canonical"):
        build(**sources)


def test_real_attempt_schemas_are_enforced(tmp_path: Path):
    sources = _fixture(tmp_path)
    journal = tmp_path / "source-attempts.json"
    journal.write_text(json.dumps({"schema_version": "wrong-schema", "attempts": []}))
    with pytest.raises(ValueError, match="journal schema"):
        build(**sources, eis_journal=journal)


def test_calendar_window_does_not_infer_nonsearched_months():
    assert _months("2024-01-01", "2024-02-28") == ["2024-01", "2024-02"]
    with pytest.raises(ValueError):
        _months("2026-10-28", "2024-01-01")



def test_two_lots_share_one_223_notice_but_remain_two_rows(tmp_path: Path):
    sources = _fixture(tmp_path)
    data = json.loads(sources["leads"].read_text())
    data["records"].append({
        "canonical_id": "223:32616339168:lot2",
        "procedure_id": "32616339168", "scope": "supply_components",
        "family": "capacitor_components", "evidence": [],
    })
    sources["leads"].write_text(json.dumps(data))
    result = build(**sources)
    assert result["candidate_denominator"] == 4
    assert result["source_category_counts"]["223fz"] == 2
    assert result["distinct_223_notice_numbers"] == 1
    assert result["numbered_223_candidate_lot_rows"] == 2
    assert result["additional_lot_rows_sharing_223_notice"] == 1
    assert result["commercial_or_nonstandard_candidate_rows"] == 2
    assert result["candidate_rows_with_primary_original"] == 3
    assert result["unique_notice_or_etp_numbers_with_primary_original"] == 2


def test_month_search_journal_counts_only_query_samples(tmp_path: Path):
    sources = _fixture(tmp_path)
    journal = tmp_path / "month.json"
    journal.write_text(json.dumps({
        "schema_version": "pq-month-scoped-eis/1",
        "attempts": [
            {"month": "2025-05", "law": "223fz", "date_bounds_verified": True,
             "query_scoped_not_exhaustive": True, "query": "УКРМ",
             "source_url": "https://zakupki.gov.ru/epz/order/extendedsearch/results.html?fz223=on&pageNumber=1&publishDateFrom=01.05.2025&publishDateTo=31.05.2025&searchString=%D0%A3%D0%9A%D0%A0%D0%9C"},
            {"month": "2025-05", "law": "44fz", "date_bounds_verified": False,
             "query_scoped_not_exhaustive": True},
        ]}))
    result = build(**sources, month_journal=journal)
    month = next(x for x in result["period_search_coverage"] if x["month"] == "2025-05")
    assert month["source_queries_with_verified_month_bounds"] == 1
    assert month["coverage_state"] == "query_scoped_first_page_only"
    assert month["zero_procurements_claimed"] is False
    assert result["completeness"] == "partial_period_discovery_not_established"
    assert result["search_attempt_log"]["official_month_scoped_first_page_attempts"] == 2


def test_month_source_receipt_rejects_forged_date_bound(tmp_path: Path):
    sources = _fixture(tmp_path)
    journal = tmp_path / "month.json"
    journal.write_text(json.dumps({
        "schema_version": "pq-month-scoped-eis/1",
        "attempts": [{"month": "2025-05", "law": "223fz", "query": "УКРМ",
                      "date_bounds_verified": True,
                      "query_scoped_not_exhaustive": True,
                      "source_url": "https://example.com/forged"}]}))
    with pytest.raises(ValueError, match="Invalid official month-bound"):
        build(**sources, month_journal=journal)
