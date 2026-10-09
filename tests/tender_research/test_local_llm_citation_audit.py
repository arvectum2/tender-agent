from scripts.benchmarks.local_llm_citation_audit import audit_entry


def test_rejects_fabricated_chunk_identifier():
    a = "ce05b458-5069-4b62-bbc3-dce35b66b665"
    b = "ce05b458-5062-4b62-bbc3-dce35b66b665"
    result = audit_entry(
        {"law": "223-ФЗ", "context_chunk_ids": [a], "answer": f"Ответ [{b}]."}
    )
    assert result["citation_integrity"] == "INVALID_SOURCE_CITATION"
    assert result["invalid_chunk_ids"] == [b]
    assert result["decision"] == "NOT_DECIDED"


def test_no_citations_is_not_claimed_grounded():
    result = audit_entry(
        {
            "law": "44-ФЗ",
            "context_chunk_ids": ["abc"],
            "answer": "Сведения о количестве не найдены",
        }
    )
    assert result["citation_integrity"] == "NO_CITATIONS"
    assert result["generative_quality"] == "NOT_ASSESSED"
