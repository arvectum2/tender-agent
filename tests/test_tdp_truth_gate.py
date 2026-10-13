"""R5 human review gates cannot be satisfied by repeated machine results."""

from __future__ import annotations

import pytest

from scripts.ops.verify_tdp_truth_gate import evaluate_gate

FIELDS = ("subject", "deadline", "price", "technical_requirements", "contract_risks")


def case(number: int):
    n = str(32600000000 + number)
    source = {"procurement_number": n, "run_id": f"run-{number}", "file_count": 2,
                  "original_files_present": 2, "files_marked_extracted": 2, "report_available": True}
    review = {"procurement_number": n, "run_id": f"run-{number}", "reviewer": "Human reviewer",
                  "reviewed_at": "2026-10-10", "human_approved": True,
                  "checks": {field: {"outcome": "correct", "file_id": "FILE-01", "source_locator": "chunk-1"}
                          for field in FIELDS}}
    return source, review


def test_empty_reviews_never_prove_quality():
    assert not evaluate_gate({"procurements": [case(0)[0]]}, [])["pass"]


def test_duplicate_eis_records_cannot_be_twenty_independent_reviews():
    source, review = case(0)
    result = evaluate_gate({"procurements": [source]}, [review] * 25)
    assert not result["pass"]
    assert result["reviewed_unique"] == 1


def test_unverified_original_rejected():
    source, review = case(1)
    source["original_files_present"] = 1
    assert evaluate_gate({"procurements": [source]}, [review])["reviewed_unique"] == 0


def test_missing_source_locator_is_not_verified():
    source, review = case(1)
    review["checks"]["price"].pop("source_locator")
    assert evaluate_gate({"procurements": [source]}, [review])["reviewed_unique"] == 0


def test_twenty_unique_attested_cases_pass_structure_gate():
    rows = [case(i) for i in range(20)]
    result = evaluate_gate({"procurements": [source for source, _ in rows]},
                           [review for _, review in rows])
    assert result["pass"] and result["reviewed_unique"] == 20
    assert "independent audit" in result["warning"]


def test_cannot_lower_minimum():
    with pytest.raises(ValueError):
        evaluate_gate({}, [], minimum=1)
