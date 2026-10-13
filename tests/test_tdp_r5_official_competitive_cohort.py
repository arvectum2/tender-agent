"""Offline guard for public hash-only R5 EIS type corpus, not a legal GO test."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "docs/acceptance/data/tdp_r5_eis_competitive_20_and_noncompetitive_4_2026-10-12.json"
)


@pytest.fixture(scope="module")
def cohort() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_original_source_verified_cohort_is_20_competitive_plus_4_negative(cohort):
    positives = cohort["positive_cases"]
    negatives = cohort["negative_cases"]
    reserve = cohort["reserve_case"]
    assert cohort["schema_version"] == 1
    assert cohort["confirmed_competitive_positives"] == len(positives) == 20
    assert cohort["confirmed_noncompetitive_negatives"] == len(negatives) == 4
    assert cohort["confirmed_competitive_reserves"] == 1
    numbers = [c["reg_number"] for c in positives + negatives + [reserve]]
    assert len(numbers) == len(set(numbers)) == 25
    assert all(re.fullmatch(r"[0-9]{19}", n) for n in numbers)


def test_competitive_procedure_types_are_from_original_eis_xml(cohort):
    positives = cohort["positive_cases"]
    allowed = cohort["competitive_methods"]
    actual = Counter(c["notice_type_xml"] for c in positives)
    assert actual == {
        "epNotificationEF2020": 11,
        "epNotificationEZK2020": 7,
        "epNotificationEOK2020": 2,
    }
    for c in positives:
        assert c["procurement_method"] == allowed[c["notice_type_xml"]]
        assert c["source_type"] == "OFFICIAL_EIS_GETDOCSIP_SHA_PINNED_XML"
        assert c["last_observed_archive_revision"] >= 1
        assert re.fullmatch(r"[0-9a-f]{64}", c["source_notice_xml_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", c["source_zip_sha256"])


def test_four_real_replacements_and_one_reserve_not_duplicated(cohort):
    positives = cohort["positive_cases"]
    newer = [c for c in positives if c["evidence_edition"] == "retrieved_2026_10_12"]
    assert {c["reg_number"] for c in newer} == {
        "0151600003226000011",
        "0162200011826003089",
        "0152200004026000069",
        "0348100024426000021",
    }
    assert len([c for c in positives if c["evidence_edition"] == "cached_2026_10_11"]) == 16
    assert all(c["notice_type_xml"] == "epNotificationEF2020" for c in newer)
    assert next(c for c in newer if c["reg_number"] == "0162200011826003089")["last_observed_archive_revision"] == 4
    assert cohort["reserve_case"]["reg_number"] == "0369100012826000157"


def test_all_noncompetitive_types_are_separate_and_source_attested(cohort):
    negatives = cohort["negative_cases"]
    price = [c for c in negatives if c["corpus_role"] == "negative_market_research"]
    special = [c for c in negatives if c["corpus_role"] == "negative_other_procedure"]
    assert len(price) == 3 and len(special) == 1
    assert {c["reg_number"] for c in price} == {
        "0148300050426000047",
        "0318200087026000163",
        "0348100024426000052",
    }
    for c in price:
        assert c["procedure_reason"] == "MARKET_RESEARCH_PRICE_INFORMATION_REQUEST"
        assert set(c["official_page_sha256"]) == {"search", "card", "docs"}
        assert all(re.fullmatch(r"[0-9a-f]{64}", x) for x in c["official_page_sha256"].values())
    assert special[0]["reg_number"] == "0349500000226000003"
    assert special[0]["notice_type_xml"] == "epNotificationEZT2020"
    assert special[0]["procedure_reason"] == "SPECIAL_SINGLE_SUPPLIER_NOT_REGULAR_COMPETITIVE_TENDER"


def test_proof_of_historical_type_is_not_live_legal_or_owner_go(cohort):
    all_cases = cohort["positive_cases"] + cohort["negative_cases"] + [cohort["reserve_case"]]
    assert cohort["owner_legal_approval_count"] == 0
    assert cohort["live_eis_bid_status_verified"] is False
    assert cohort["original_source_binaries_committed"] is False
    assert all(c["live_eis_bid_status_verified"] is False for c in all_cases)
    assert all(c["owner_go_decision"] == "DEFER" for c in all_cases)
    assert all(c.get("full_current_legal_review", False) is False for c in all_cases)
