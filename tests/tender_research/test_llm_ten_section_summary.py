from scripts.benchmarks.local_llm_ten_section_summary import summarize


def test_source_integrity_and_truncation_are_separate_metrics():
    rows = [
        {
            "law": "223-ФЗ",
            "cited_uuids": ["a"],
            "invalid_citations": [],
            "finish_reason": "stop",
            "time_seconds": 10,
        },
        {
            "law": "223-ФЗ",
            "cited_uuids": ["b"],
            "invalid_citations": [],
            "finish_reason": "length",
            "time_seconds": 12,
        },
        {
            "law": "223-ФЗ",
            "cited_uuids": [],
            "finish_reason": "stop",
            "time_seconds": 5,
        },
        {
            "law": "44-ФЗ",
            "cited_uuids": ["x"],
            "invalid_citations": ["x"],
            "finish_reason": "stop",
            "time_seconds": 8,
        },
    ]
    result = summarize(rows)
    a = next(x for x in result if x["law"] == "223-ФЗ")
    assert (
        a["cases"],
        a["complete_with_source_ids"],
        a["uncited"],
        a["truncated_by_length"],
    ) == (3, 1, 1, 1)
    assert a["factual_accuracy"] == "NOT_ASSESSED_AUTOMATICALLY"
    b = next(x for x in result if x["law"] == "44-ФЗ")
    assert (b["changed_or_unknown_ids"], b["complete_with_source_ids"]) == (1, 0)
    assert b["decision"] == "NOT_DECIDED"
