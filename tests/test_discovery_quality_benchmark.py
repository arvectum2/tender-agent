from __future__ import annotations

import pytest

from src.modules.discovery_quality.benchmark import (
    aggregate_discovery_metrics,
    evaluate_query_ranking,
)


def _case(index: int, score: float, *, query: str = "кабель") -> dict:
    return {
        "case_id": f"case-{index:02d}",
        "query": query,
        "source_rank": index,
        "registry_number": f"reg-{index:02d}",
        "score": score,
        "status": "medium",
        "reasons": ["source-grounded explanation"],
        "breakdown": {"keywords": score},
        "source_status": None,
        "detail_status": None,
        "source_deadline": "2026-09-20T00:00:00+00:00",
        "detail_deadline": "2026-09-20T00:00:00+00:00",
    }


def test_query_metrics_use_frozen_labels_and_score_order() -> None:
    cases = [_case(index, 100 - index) for index in range(1, 16)]
    labels = {
        **{f"case-{index:02d}": "RELEVANT" for index in range(1, 5)},
        **{f"case-{index:02d}": "PARTIALLY_RELEVANT" for index in range(5, 9)},
        **{f"case-{index:02d}": "IRRELEVANT" for index in range(9, 16)},
    }

    result = evaluate_query_ranking(query="кабель", sut_cases=cases, blind_labels=labels)

    assert result["case_count"] == 15
    assert result["scored_case_count"] == 15
    assert result["metrics_by_k"]["5"]["precision"] == 1.0
    assert result["metrics_by_k"]["5"]["recall"] == pytest.approx(5 / 8)
    assert result["metrics_by_k"]["10"]["precision"] == pytest.approx(0.8)
    assert result["metrics_by_k"]["10"]["recall"] == 1.0
    assert result["metrics_by_k"]["10"]["false_positive_rate"] == pytest.approx(0.2)
    assert result["metrics_by_k"]["10"]["ndcg"] is not None
    assert result["missed_relevant_rate_at_primary_k"] == 0.0
    assert result["duplicate_rate"] == 0.0
    assert result["explainability_coverage"] == 1.0
    assert result["deadline_correctness"]["accuracy"] == 1.0
    assert result["status_correctness"]["accuracy"] is None


def test_unclear_is_reported_but_excluded_from_scored_denominators() -> None:
    cases = [_case(1, 100), _case(2, 90), _case(3, 80)]
    labels = {
        "case-01": "UNCLEAR",
        "case-02": "RELEVANT",
        "case-03": "IRRELEVANT",
    }

    result = evaluate_query_ranking(query="кабель", sut_cases=cases, blind_labels=labels)

    assert result["unclear_count"] == 1
    assert result["scored_case_count"] == 2
    assert result["metrics_by_k"]["5"]["evaluated_count"] == 2
    assert result["metrics_by_k"]["5"]["precision"] == 0.5
    assert result["metrics_by_k"]["5"]["recall"] == 1.0


def test_duplicate_rate_and_failure_inventory_are_explicit() -> None:
    cases = [_case(index, 100 - index) for index in range(1, 12)]
    cases[10]["registry_number"] = cases[0]["registry_number"]
    labels = {case["case_id"]: "IRRELEVANT" for case in cases}
    labels["case-11"] = "RELEVANT"

    result = evaluate_query_ranking(query="кабель", sut_cases=cases, blind_labels=labels)

    assert result["duplicate_rate"] == pytest.approx(1 / 11)
    assert "case-11" in result["failure_cases"]["missed_relevant"]
    assert result["failure_cases"]["top_k_irrelevant"]


def test_aggregate_discovery_metrics_macro_averages_queries() -> None:
    cases_a = [_case(index, 100 - index, query="a") for index in range(1, 11)]
    cases_b = [_case(index, 100 - index, query="b") for index in range(1, 11)]
    labels_a = {case["case_id"]: "RELEVANT" for case in cases_a}
    labels_b = {case["case_id"]: "IRRELEVANT" for case in cases_b}

    result_a = evaluate_query_ranking(query="a", sut_cases=cases_a, blind_labels=labels_a)
    result_b = evaluate_query_ranking(query="b", sut_cases=cases_b, blind_labels=labels_b)
    aggregate = aggregate_discovery_metrics([result_a, result_b])

    assert aggregate["query_count"] == 2
    assert aggregate["case_count"] == 20
    assert aggregate["macro_metrics_by_k"]["5"]["precision"] == 0.5
    assert aggregate["macro_metrics_by_k"]["10"]["false_positive_rate"] == 0.5
    assert aggregate["macro_explainability_coverage"] == 1.0


def test_missing_label_fails_closed() -> None:
    with pytest.raises(ValueError, match="missing/invalid blind discovery label"):
        evaluate_query_ranking(query="кабель", sut_cases=[_case(1, 10)], blind_labels={})
