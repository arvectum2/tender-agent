"""CZN v4 source facts and qualification gate must never turn into human acceptance."""
from __future__ import annotations

import json
import re
from pathlib import Path

RECEIPT = (
    Path(__file__).resolve().parents[1]
    / "docs/acceptance/apr06_czn_v4_provisional_semantic_review_2026-10-13.json"
)


def _data() -> dict:
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def test_current_original_eis_v4_and_seven_byte_receipts_without_false_acceptance():
    evidence = _data()
    assert evidence["schema_version"] == "apr06-czn-v4-ai-source-review-v1"
    assert evidence["review_type"] == "PROVISIONAL_AI_SOURCE_GROUNDED_NOT_HUMAN_GOLD"
    original = evidence["primary_source"]
    assert original["notice_version"] == 4
    assert original["notice_uid_filename_size_sha_matches"] == 7
    assert original["notice_deadline_msk"] == "2026-10-23T10:00:00+03:00"
    assert re.fullmatch(r"[a-f0-9]{64}", original["original_soap_archive_sha256"])
    assert re.fullmatch(r"[a-f0-9]{64}", original["original_soap_eok_xml_sha256"])
    assert original["original_xml_digital_signature_validated"] is False
    assert evidence["provisional_analysis"]["human_gold_label"] is False
    assert evidence["provisional_analysis"]["owner_commercial_approval"] is False
    assert evidence["provisional_analysis"]["bid_submitted"] is False


def test_70_30_qualification_first_is_separate_from_technical_feasibility():
    evidence = _data()
    primary = evidence["primary_confirmed"]
    scoring = primary["award_scoring"]
    assert scoring["price_weight_percent"] == 30
    assert scoring["qualification_weight_percent"] == 70
    assert scoring["qualification_basis"].startswith("количество исполненных")
    assert scoring["qualifying_contracts_user_confirmed"] is None
    assert scoring["price_weight_percent"] + scoring["qualification_weight_percent"] == 100
    decision = evidence["provisional_analysis"]
    assert decision["recommendation"].startswith("DEFER_")
    assert decision["cost_estimate_rub"] is None
    assert decision["legal_opinion_final"] is False
    assert decision["user_should_not_auto_bid"] is True


def test_primary_three_item_nmck_and_due_dates_are_consistent():
    evidence = _data()
    facts = evidence["primary_confirmed"]
    assert len(facts["items"]) == 3
    assert sum(x["nmck_rub"] for x in facts["items"]) == facts["nmck_rub"] == 1245000
    assert sorted(x["nmck_rub"] for x in facts["items"]) == [245000, 315000, 685000]
    dates = facts["deadlines"]
    assert dates["youth_and_training_implementation"] == "2026-12-02"
    assert dates["chatbot_implementation"] == "2026-12-10"
    assert dates["chatbot_go_live"] == "2026-12-15"
    contract = facts["contract"]
    assert contract["advance"] is False
    assert contract["warranty_months"] == 12
    assert contract["critical_defect_remedy_workdays"] == 1
    assert contract["noncritical_defect_remedy_workdays"] == 5
    assert contract["customer_access_due_workdays_after_contract"] == 3


def test_document_inventory_no_duplicate_pdf_count_or_manufactured_signatures():
    evidence = _data()
    docs = evidence["document_inventory"]
    assert len(docs) == 6
    assert len({x["source_uid"] for x in docs}) == 6
    pdf = next(x for x in docs if x["key"] == "technical_spec")
    assert pdf["pages"] == 95
    assert pdf["duplicated_in_other_zip"] is True
    assert pdf["original_sha256"] == (
        "3a668cd9140770851920d4a6b99ea0568f129a7eba0496ad63e1254d619b8364"
    )
    assert evidence["provisional_analysis"]["owner_commercial_approval"] is False
