"""PRICE-01: synthetic source-corruption tests plus public aggregate receipt only."""
from __future__ import annotations

import csv
import io
import json
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from scripts.price01.audit_aksay_baseline import verify_original_bid_rows
from src.tender_research.competitive_bid_protocol import (
    AKSAY,
    AKSAY_ZIP_SHA256,
    build_aksay_baseline,
    compute_owner_supplied_break_even,
)

FIELDS = (
    "application_id", "price_rub", "status", "rank",
    "rejection_reason_code", "rejection_reason_original",
)
BASELINE = json.loads((
    Path(__file__).resolve().parents[2] /
    "docs/roadmap/price01_aksay_original_protocol_baseline_2026-10-17.json"
).read_text())


def _fixture():
    """Synthetic 55-bid source, NOT copied from the private first-party file."""
    bids = []
    for rank in range(1, 46):
        bids.append({
            "application_id": f"test-{rank:03d}",
            "price_rub": rank * 1000,
            "status": "admitted",
            "rank": rank,
            "rejection_reason_code": None,
            "rejection_reason_original": "",
        })
    for number in range(10):
        bids.append({
            "application_id": f"test-rejected-{number}",
            "price_rub": 100,
            "status": "rejected",
            "rank": None,
            "rejection_reason_code": "invalid_documents",
            "rejection_reason_original": "synthetic reason",
        })
    summary = {
        "procurement_number": AKSAY, "protocol_date": "2026-10-14",
        "nmck_rub": 100_000,
        "applications_total": 55, "applications_admitted": 45,
        "applications_rejected": 10, "winner_application_id": "test-001",
        "winner_price_rub": 1000,
        "our_application_id": "test-038", "our_price_rub": 38000,
        "our_rank": 38, "our_status": "admitted",
        "median_admitted_rub": 23000, "min_admitted_rub": 1000,
        "max_admitted_rub": 45000, "rejection_causes": {"invalid_documents": 10},
    }
    return {"summary": summary, "bids": bids}


def _encode(record):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=FIELDS)
    writer.writeheader()
    for row in record["bids"]:
        writer.writerow(row)
    return json.dumps(record).encode(), output.getvalue().encode()


def _build(record=None, *, csv_override=None, archive_hash=AKSAY_ZIP_SHA256):
    statistics, csv_bytes = _encode(record or _fixture())
    return build_aksay_baseline(
        statistics_bytes=statistics,
        csv_bytes=csv_override if csv_override is not None else csv_bytes,
        official_archive_sha256=archive_hash,
    )


def test_one_protocol_competition_only_and_rejected_low_price_excluded():
    result = _build()
    assert result["bids_total"] == 55
    assert result["admitted_count"] == 45
    assert result["rejected_count"] == 10
    assert result["rejection_reason_counts"] == {"invalid_documents": 10}
    assert result["winner"]["price_rub"] == "1000"
    assert result["admitted_bid_prices_rub"]["min"] == "1000"
    assert result["admitted_bid_prices_rub"]["median"] == "23000"
    assert result["arvectum_bid"]["rank"] == 38
    assert result["arvectum_bid"]["admitted_offers_with_lower_price"] == 37
    assert result["comparable_distinct_procurements"] == 1
    assert result["cross_procurement_price_evidence"] == "INSUFFICIENT_EVIDENCE"
    assert result["cost_break_even_scenarios"] is None
    assert result["is_bid_recommendation"] is False
    assert result["submission_or_payment_performed"] is False


@pytest.mark.parametrize(("mutation", "message"), [
    (lambda d: d["summary"].update(procurement_number="another"), "case or date"),
    (lambda d: d["summary"].update(protocol_date="2026-10-15"), "case or date"),
    (lambda d: d["summary"].update(applications_total=54), "count"),
    (lambda d: d["summary"].update(applications_admitted=46), "admitted"),
    (lambda d: d["summary"].update(rejection_causes={"invalid_documents": 9}), "rejection"),
    (lambda d: d["summary"].update(winner_price_rub=1001), "winner"),
    (lambda d: d["summary"].update(our_rank=37), "company bid"),
    (lambda d: d["summary"].update(median_admitted_rub=22000), "median"),
    (lambda d: d["bids"].__setitem__(1, {**d["bids"][1], "rank": 1}), "ranking"),
    (lambda d: d["bids"].__setitem__(1, {**d["bids"][1], "price_rub": 0}), "positive"),
    (lambda d: d["bids"].__setitem__(1, {**d["bids"][1], "price_rub": float("nan")}), "finite"),
    (lambda d: d["bids"].__setitem__(1, {**d["bids"][1], "price_rub": 1234.567}), "precision"),
    (lambda d: d["bids"].__setitem__(0, {**d["bids"][0], "status": "rejected"}), "status"),
    (lambda d: d["bids"].__setitem__(45, {**d["bids"][45], "rank": 9}), "rank"),
    (lambda d: d["bids"].__setitem__(45, {**d["bids"][45], "rejection_reason_code": None}), "reason"),
    (lambda d: d["bids"].__setitem__(1, {**d["bids"][1], "application_id": "test-001"}), "duplicate"),
])
def test_corrupted_source_is_never_accepted(mutation, message):
    data = _fixture()
    mutation(data)
    with pytest.raises((ValueError, TypeError)):
        _build(data)


def test_cross_export_bid_price_or_rejection_reason_mismatch_rejected():
    data = _fixture()
    original_json, _ = _encode(data)
    changed = _fixture()
    changed["bids"][0]["price_rub"] = 1001
    _, corrupt_csv = _encode(changed)
    with pytest.raises(ValueError, match="price differs"):
        build_aksay_baseline(statistics_bytes=original_json, csv_bytes=corrupt_csv,
                             official_archive_sha256=AKSAY_ZIP_SHA256)
    changed = _fixture()
    changed["bids"][45]["rejection_reason_original"] = "different"
    _, corrupt_csv = _encode(changed)
    with pytest.raises(ValueError, match="rejection evidence"):
        build_aksay_baseline(statistics_bytes=original_json, csv_bytes=corrupt_csv,
                             official_archive_sha256=AKSAY_ZIP_SHA256)


def test_unverified_official_original_identity_is_rejected():
    with pytest.raises(ValueError, match="original EIS"):
        _build(archive_hash="0" * 64)


def test_owner_inputs_have_no_defaults_or_hidden_labour():
    inputs = {
        "external_direct_rub": "1000",
        "labor_rub": "2000",
        "reserve_rub": "100",
        "fixed_platform_fees_rub": "50",
        "revenue_tax_rate": "0.06",
        "variable_platform_fee_rate": "0.02",
        "target_profit_rub": "300",
    }
    result = compute_owner_supplied_break_even(**inputs)
    assert result["cash_cost_break_even_rub"] == "1250.00"
    assert result["full_economic_break_even_rub"] == "3423.92"
    assert result["full_cost_plus_explicit_target_rub"] == "3750.00"
    assert result["assumptions"] == "EXPLICIT_OWNER_INPUT_ONLY_NOT_A_BID"
    with pytest.raises(TypeError):
        compute_owner_supplied_break_even(external_direct_rub=1000)


@pytest.mark.parametrize("rate", ["0.99", "-0.01", "NaN", "Infinity", "garbage"])
def test_invalid_unsupported_rates_and_fee_mass_rejected(rate):
    kwargs = {
        "external_direct_rub": 100, "labor_rub": 100, "reserve_rub": 1,
        "fixed_platform_fees_rub": 1, "target_profit_rub": 0,
        "revenue_tax_rate": rate, "variable_platform_fee_rate": "0.05",
    }
    with pytest.raises(ValueError):
        compute_owner_supplied_break_even(**kwargs)


def test_real_source_aggregate_receipt_without_transferring_bidder_data():
    assert BASELINE["schema_version"] == "ta-price01-protocol-one-procedure-v1"
    assert BASELINE["procurement_number"] == AKSAY
    assert BASELINE["original_eis_zip_sha256"] == AKSAY_ZIP_SHA256
    assert BASELINE["original_bid_rows_individually_cross_checked"] == 55
    assert BASELINE["official_protocol_xml_sha256"] == "2b9f510c48e7d828c432e32b4dca3a4fff8edb75c66c3da37d46a12af3456af5"
    assert BASELINE["bids_total"] == 55
    assert BASELINE["admitted_count"] == 45
    assert BASELINE["rejected_count"] == 10
    assert BASELINE["winner"] == {
        "application_id": "122023425", "rank": 1, "price_rub": "28400.0"
    }
    assert BASELINE["arvectum_bid"]["rank"] == 38
    assert Decimal(BASELINE["arvectum_bid"]["price_rub"]) == Decimal(119000)
    assert BASELINE["admitted_bid_prices_rub"]["median"] == "74000.0"
    assert BASELINE["rejection_reason_counts"] == {
        "inapplicable_software_registry_entry": 1,
        "missing_software_registry_document_old_notice": 9,
    }
    assert BASELINE["cross_procurement_price_evidence"] == "INSUFFICIENT_EVIDENCE"
    assert BASELINE["cost_break_even_scenarios"] is None
    assert BASELINE["is_bid_recommendation"] is False


def _official_xml_fixture(original):
    root = ET.Element("original")
    for row in original["bids"]:
        item = ET.SubElement(root, "applicationInfo")
        ET.SubElement(item, "appNumber").text = row["application_id"]
        ET.SubElement(item, "finalPrice").text = str(row["price_rub"])
        ET.SubElement(item, "admitted").text = (
            "true" if row["status"] == "admitted" else "false"
        )
        if row["rank"] is not None:
            ET.SubElement(item, "appRating").text = str(row["rank"])
    return ET.tostring(root, encoding="utf8")


def test_all_original_bid_rows_cross_checked_not_just_summary_and_csv():
    record = _fixture()
    stats, _ = _encode(record)
    xml = _official_xml_fixture(record)
    assert verify_original_bid_rows(stats, xml) == 55
    changed = _fixture()
    changed["bids"][22]["price_rub"] += 1
    bad_stats, _ = _encode(changed)
    with pytest.raises(ValueError, match="original EIS and JSON price"):
        verify_original_bid_rows(bad_stats, xml)
    changed = _fixture()
    changed["bids"][22]["status"] = "rejected"
    bad_stats, _ = _encode(changed)
    with pytest.raises(ValueError, match="admissibility"):
        verify_original_bid_rows(bad_stats, xml)


def test_original_xml_rejects_dtd_entity_and_duplicate_ids():
    record = _fixture()
    stats, _ = _encode(record)
    with pytest.raises(ValueError, match="unsafe"):
        verify_original_bid_rows(stats, b"<!DOCTYPE x><root/>")
    root = ET.fromstring(_official_xml_fixture(record))
    root.append(root[0])
    with pytest.raises(ValueError, match="duplicate"):
        verify_original_bid_rows(stats, ET.tostring(root, encoding="utf8"))
