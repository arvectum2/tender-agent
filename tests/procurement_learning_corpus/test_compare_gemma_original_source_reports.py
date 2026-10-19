"""Controlled same-archive comparison must reject a modified registry ID."""
from __future__ import annotations

from scripts.procurement_llm.compare_gemma_original_source_reports import compare
from scripts.procurement_llm.gemma_originals_quality_benchmark import ARCHIVE_SHA


def test_strict_registry_check_rejects_extra_digit_despite_valid_chunk_id():
    base = ("## subject. Предмет закупки\nНМЦК — 15 000 000 рублей\n"
            "## notice_info. Информация об извещении\nИзвещение неизвестно\n")
    next_report = {
        "schema": "gemma_12b_reasoning_xml_full_source_benchmark_v1",
        "source": {"original_archive_sha": ARCHIVE_SHA, "official_docx_count": 5},
        "sections": [
            {"id": "subject", "status": "completed",
             "answer": "НМЦК 497 178,33 руб; chunk_id=src-aabbccdd00112233 "
                       "registry_number=01632000003260005243",
             "model_seconds": 120},
            {"id": "notice_info", "status": "completed",
             "answer": "Открытый конкурс 0163200000326005243; "
                       "chunk_id=src-aabbccdd00112233 "
                       "registry_number=0163200000326005243",
             "model_seconds": 100},
        ],
    }
    result=compare(base,next_report)
    assert result["enhanced_completed_sections"]==2
    assert result["enhanced_strictly_validated_sections"]==1
    assert result["sections_rejected_by_extra_registry_number_audit"]==["subject"]
    assert result["enhanced_elapsed_total_seconds"]==220.0
    assert any(row["fact"]=="НМЦК 497 178,33 ₽" and row["new_found"]
               and not row["new_strictly_cited"]
               for row in result["mechanical_checks"])
    assert result["human_training_gold"] is False
