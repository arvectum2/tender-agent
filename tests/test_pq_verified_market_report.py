import hashlib
import json
from pathlib import Path

import pytest

from src.modules.market_intelligence.pq_verified_market_report import (
    exact_filestore_sha_receipts,
    markdown,
    source_receipts,
    summarize,
)


def _dummy_case(root: Path, case: str = "32616339168") -> Path:
    folder = root / case
    folder.mkdir(parents=True)
    payload = b"Official downloaded protocol"
    digest = hashlib.sha256(payload).hexdigest()
    (folder / "protocol.pdf").write_bytes(payload)
    (folder / "public-page-receipt.json").write_text(json.dumps({
        "schema_version": "pq-223-public-page-download/1",
        "registry_number": case,
        "status": "public_page_files_downloaded",
        "public_page_sha256": "f" * 64,
        "files": [{"filename": "protocol.pdf", "sha256": digest}],
    }))
    return folder


def test_public_eis_source_sha_guard(tmp_path: Path):
    folder = _dummy_case(tmp_path)
    items = source_receipts(tmp_path)
    assert items[0]["verified_file_instances"] == 1
    (folder / "protocol.pdf").write_bytes(b"modified")
    with pytest.raises(ValueError, match="SHA-256 changed"):
        source_receipts(tmp_path)


def test_no_market_value_extrapolation_from_commission_sample():
    commission = {"facts_accepted": 4, "records": [
        {"procedure_id": "32514947144", "bid_price_rub": "3158400.00",
         "price_kind": "commission_winning_offer_vat_included",
         "market_category": "filter_capacitor_supply",
         "committee_participant": "Supplier", "initial_price_rub": "3186960.00"},
        {"procedure_id": "32515029641", "bid_price_rub": "3490560.00",
         "price_kind": "commission_proposed_single_bidder_amount_vat_included",
         "market_category": "filter_capacitor_supply",
         "committee_participant": "Supplier2", "initial_price_rub": "3621456.00"},
        {"procedure_id": "32616339168", "bid_price_rub": "4350000.00",
         "price_kind": "winning_24_bsk_capacitors_offer_vat_included",
         "market_category": "capacitor_bank_component_supply",
         "committee_participant": "Supplier3", "initial_price_rub": "6807600.00"},
        {"procedure_id": "32413581034", "bid_price_rub": "1517360443.50",
         "price_kind": "winning_mixed_epc_offer_vat_included_not_pq_only",
         "market_category": "adjacent_epc_lot2_ps_hani_parent_project_mentions_scrm",
         "committee_participant": "Adjacent", "initial_price_rub": "1518147770.00"},
    ]}
    leads = [{"procedure_id": "32616339168"}, {"procedure_id": "32800000000"},
             {"procedure_id": "358-830"}]
    result = summarize(
        leads=leads,
        eis=[{"registry_number": "32616339168", "verified_file_instances": 1}],
        commissions=commission,
        etp={"original_etp_cases_verified": 1, "records": []},
        contracts={"distinct_contract_lots_matched": 1,
                   "contract_lots_with_rub_price": 1, "records": []},
    )
    assert result["direct_capacitor_supply_bid_sample_cases"] == 3
    assert result["direct_capacitor_supply_bid_sample_vat_included_rub"] == "10998960.00"
    assert result["pq_equipment_market_value_rub"] is None
    assert result["verified_signed_contract_suppliers"] == 0
    assert result["non_223_or_nonstandard_leads"] == 1
    assert "10 998 960.00 ₽" in markdown(result)


def test_direct_official_source_sha_receipt_is_verified(tmp_path: Path):
    case = tmp_path / "32616355390"
    case.mkdir()
    blob = b"Original EIS DOCX"
    sha = hashlib.sha256(blob).hexdigest()
    (case / (sha + ".docx")).write_bytes(blob)
    (case / "official-sha-receipt.json").write_text(json.dumps({
        "schema_version": "pq-official-filestore-sha-receipt/1",
        "registry_number": case.name, "verified": [
            {"stored_name": sha + ".docx", "sha256": sha}],
    }))
    result = exact_filestore_sha_receipts(tmp_path)
    assert result[0]["verified_file_instances"] == 1
    assert result[0]["status"] == "official_filestore_exact_sha_verified"
    (case / (sha + ".docx")).write_bytes(b"bad")
    with pytest.raises(ValueError, match="SHA mismatch"):
        exact_filestore_sha_receipts(tmp_path)


def test_warning_counts_follow_verified_source_population():
    """An intermediate report must not claim stale corpus size/coverage."""
    def render(candidates):
        return summarize(
            leads=candidates, eis=[],
            commissions={"facts_accepted": 0, "records": []},
            etp={"original_etp_cases_verified": 0, "records": []},
            contracts={"distinct_contract_lots_matched": 0,
                       "contract_lots_with_rub_price": 0, "records": []},
        )

    small = render([
        {"procedure_id": "32616339168"},
        {"procedure_id": "32615969197"},
        {"procedure_id": "358-830"},
    ])
    assert small["v29_candidate_leads"] == 3
    assert small["source_number_223_leads"] == 2
    assert small["non_223_or_nonstandard_leads"] == 1
    assert small["warnings"][0].startswith("3 candidate leads ")
    assert small["warnings"][1].startswith("1 non-223/nonstandard lead is ")
    assert "69 non-223/" not in " ".join(small["warnings"])

    corpus = (
        [{"procedure_id": str(32_600_000_000 + i)} for i in range(33)]
        + [{"procedure_id": f"ETP-{i}"} for i in range(68)]
    )
    larger = render(corpus)
    assert larger["source_number_223_leads"] == 33
    assert larger["non_223_or_nonstandard_leads"] == 68
    assert larger["warnings"][0].startswith("101 candidate leads ")
    assert larger["warnings"][1].startswith("68 non-223/nonstandard leads ")
    assert larger["pq_equipment_market_value_rub"] is None
    assert larger["verified_signed_contract_suppliers"] == 0
    assert larger["completeness"] == "partial_do_not_extrapolate"
