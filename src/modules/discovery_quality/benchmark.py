from __future__ import annotations

import math
from collections import Counter
from typing import Any

BENCHMARK_VERSION = "1"
DISCOVERY_LABELS = {"RELEVANT", "PARTIALLY_RELEVANT", "IRRELEVANT", "UNCLEAR"}
RELEVANT_LABELS = {"RELEVANT", "PARTIALLY_RELEVANT"}
GRADE = {
    "RELEVANT": 2,
    "PARTIALLY_RELEVANT": 1,
    "IRRELEVANT": 0,
}


def _safe_div(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _dcg(grades: list[int], k: int) -> float:
    value = 0.0
    for index, grade in enumerate(grades[:k]):
        gain = (2**grade) - 1
        value += gain / math.log2(index + 2)
    return value


def _ndcg(grades: list[int], k: int) -> float | None:
    actual = _dcg(grades, k)
    ideal = _dcg(sorted(grades, reverse=True), k)
    return actual / ideal if ideal else None


def _deadline_key(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text[:10] if len(text) >= 10 else text


def evaluate_query_ranking(
    *,
    query: str,
    sut_cases: list[dict[str, Any]],
    blind_labels: dict[str, str],
    ks: tuple[int, ...] = (5, 10),
) -> dict[str, Any]:
    """Evaluate one frozen query pool without changing ranking or labels.

    `UNCLEAR` labels are reported but excluded from scored ranking denominators.
    Relevant for precision/recall means RELEVANT or PARTIALLY_RELEVANT; nDCG
    keeps the two levels distinct with grades 2 and 1.
    """

    ordered = sorted(
        sut_cases,
        key=lambda item: (-float(item["score"]), int(item["source_rank"]), item["case_id"]),
    )
    seen_registry: set[str] = set()
    duplicate_count = 0
    explainable = 0
    deadline_supported = 0
    deadline_correct = 0
    status_supported = 0
    status_correct = 0
    rows: list[dict[str, Any]] = []
    unclear_case_ids: list[str] = []

    for rank, item in enumerate(ordered, start=1):
        case_id = item["case_id"]
        label = blind_labels.get(case_id)
        if label not in DISCOVERY_LABELS:
            raise ValueError(f"missing/invalid blind discovery label for {case_id}: {label!r}")
        registry = str(item.get("registry_number") or "")
        if registry and registry in seen_registry:
            duplicate_count += 1
        if registry:
            seen_registry.add(registry)
        if item.get("reasons") and item.get("breakdown"):
            explainable += 1

        card_deadline = _deadline_key(item.get("source_deadline"))
        detail_deadline = _deadline_key(item.get("detail_deadline"))
        if card_deadline and detail_deadline:
            deadline_supported += 1
            deadline_correct += int(card_deadline == detail_deadline)

        source_status = item.get("source_status")
        detail_status = item.get("detail_status")
        if source_status not in (None, "") and detail_status not in (None, ""):
            status_supported += 1
            status_correct += int(str(source_status).strip() == str(detail_status).strip())

        row = {
            "case_id": case_id,
            "registry_number": registry or None,
            "rank": rank,
            "source_rank": item["source_rank"],
            "score": item["score"],
            "status": item.get("status"),
            "label": label,
        }
        rows.append(row)
        if label == "UNCLEAR":
            unclear_case_ids.append(case_id)

    scored = [row for row in rows if row["label"] != "UNCLEAR"]
    total_relevant = sum(row["label"] in RELEVANT_LABELS for row in scored)
    metrics_by_k: dict[str, dict[str, Any]] = {}
    for k in ks:
        top = scored[:k]
        relevant_at_k = sum(row["label"] in RELEVANT_LABELS for row in top)
        irrelevant_at_k = sum(row["label"] == "IRRELEVANT" for row in top)
        grades = [GRADE[row["label"]] for row in scored]
        metrics_by_k[str(k)] = {
            "evaluated_count": len(top),
            "relevant_count": relevant_at_k,
            "precision": _safe_div(relevant_at_k, len(top)),
            "recall": _safe_div(relevant_at_k, total_relevant),
            "ndcg": _ndcg(grades, k),
            "false_positive_rate": _safe_div(irrelevant_at_k, len(top)),
        }

    primary_k = max(ks)
    top_primary = scored[:primary_k]
    primary_relevant = sum(row["label"] in RELEVANT_LABELS for row in top_primary)
    missed = max(total_relevant - primary_relevant, 0)
    top_irrelevant = [row["case_id"] for row in top_primary if row["label"] == "IRRELEVANT"]
    missed_relevant = [
        row["case_id"]
        for row in scored[primary_k:]
        if row["label"] in RELEVANT_LABELS
    ]

    return {
        "benchmark_version": BENCHMARK_VERSION,
        "query": query,
        "case_count": len(rows),
        "scored_case_count": len(scored),
        "unclear_count": len(unclear_case_ids),
        "unclear_case_ids": unclear_case_ids,
        "relevant_total": total_relevant,
        "metrics_by_k": metrics_by_k,
        "missed_relevant_rate_at_primary_k": _safe_div(missed, total_relevant),
        "duplicate_rate": _safe_div(duplicate_count, len(rows)),
        "explainability_coverage": _safe_div(explainable, len(rows)),
        "deadline_correctness": {
            "supported_count": deadline_supported,
            "correct_count": deadline_correct,
            "accuracy": _safe_div(deadline_correct, deadline_supported),
        },
        "status_correctness": {
            "supported_count": status_supported,
            "correct_count": status_correct,
            "accuracy": _safe_div(status_correct, status_supported),
        },
        "failure_cases": {
            "top_k_irrelevant": top_irrelevant,
            "missed_relevant": missed_relevant,
        },
        "ranked_cases": rows,
    }


def _mean(values: list[float | None]) -> float | None:
    scored = [float(value) for value in values if value is not None]
    return sum(scored) / len(scored) if scored else None


def aggregate_discovery_metrics(query_results: list[dict[str, Any]]) -> dict[str, Any]:
    if not query_results:
        raise ValueError("at least one query result is required")
    k_values = sorted(
        {int(k) for result in query_results for k in result["metrics_by_k"]},
    )
    macro_by_k: dict[str, dict[str, float | None]] = {}
    for k in k_values:
        key = str(k)
        macro_by_k[key] = {
            metric: _mean([result["metrics_by_k"][key][metric] for result in query_results])
            for metric in ("precision", "recall", "ndcg", "false_positive_rate")
        }

    label_counts: Counter[str] = Counter()
    top_irrelevant: list[str] = []
    missed_relevant: list[str] = []
    for result in query_results:
        for row in result["ranked_cases"]:
            label_counts[row["label"]] += 1
        top_irrelevant.extend(result["failure_cases"]["top_k_irrelevant"])
        missed_relevant.extend(result["failure_cases"]["missed_relevant"])

    deadline_supported = sum(result["deadline_correctness"]["supported_count"] for result in query_results)
    deadline_correct = sum(result["deadline_correctness"]["correct_count"] for result in query_results)
    status_supported = sum(result["status_correctness"]["supported_count"] for result in query_results)
    status_correct = sum(result["status_correctness"]["correct_count"] for result in query_results)

    return {
        "benchmark_version": BENCHMARK_VERSION,
        "query_count": len(query_results),
        "case_count": sum(result["case_count"] for result in query_results),
        "scored_case_count": sum(result["scored_case_count"] for result in query_results),
        "label_counts": dict(sorted(label_counts.items())),
        "macro_metrics_by_k": macro_by_k,
        "macro_missed_relevant_rate_at_primary_k": _mean(
            [result["missed_relevant_rate_at_primary_k"] for result in query_results]
        ),
        "macro_duplicate_rate": _mean([result["duplicate_rate"] for result in query_results]),
        "macro_explainability_coverage": _mean(
            [result["explainability_coverage"] for result in query_results]
        ),
        "deadline_correctness": {
            "supported_count": deadline_supported,
            "correct_count": deadline_correct,
            "accuracy": _safe_div(deadline_correct, deadline_supported),
        },
        "status_correctness": {
            "supported_count": status_supported,
            "correct_count": status_correct,
            "accuracy": _safe_div(status_correct, status_supported),
        },
        "failure_inventory": {
            "top_k_irrelevant": sorted(top_irrelevant),
            "missed_relevant": sorted(missed_relevant),
        },
        "queries": query_results,
    }
