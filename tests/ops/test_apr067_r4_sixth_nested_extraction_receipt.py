"""Original ZIP bytes != native text extraction; count nested content separately."""
from scripts.acceptance.apr067_r4_four_revisions_llm_replay import (
    summarize_original_and_nested_extraction,
)


def test_original_sha_containers_and_nested_substantive_documents_counted_separately():
    files = [
        *[{"extension": ".xml", "text_extraction_status": "extracted", "extracted_text_available": True}
          for _ in range(8)],
        *[{"extension": ".docx", "text_extraction_status": "extracted", "extracted_text_available": True}
          for _ in range(2)],
        *[{"extension": ".zip", "text_extraction_status": "archive_extracted",
           "extracted_text_available": True, "nested_document_count": count,
           "nested_extracted_text_count": count, "nested_failed_text_count": 0}
          for count in (2, 1, 1, 1)],
    ]
    s = summarize_original_and_nested_extraction(files)
    assert s["extracted_original_count"] == 14
    assert s["failed_original_count"] == 0
    assert s["direct_original_text_extracted"] == 10
    assert s["zip_original_containers"] == 4
    assert s["zip_containers_with_extracted_children"] == 4
    assert s["zip_substantive_children_extracted"] == 5
    assert s["zip_substantive_children_failed"] == 0
    assert s["zip_substantive_child_count"] == 5


def test_pending_or_partially_extracted_zip_cannot_pass_strict_source_status_gate():
    for status, extracted, failed in (
        ("pending", 0, 0),
        ("archive_unreadable", 0, 1),
        ("archive_partial", 1, 1),
    ):
        s = summarize_original_and_nested_extraction([
            {"extension": ".zip", "text_extraction_status": status,
             "extracted_text_available": bool(extracted),
             "nested_document_count": extracted + failed,
             "nested_extracted_text_count": extracted,
             "nested_failed_text_count": failed},
        ])
        assert s["extracted_original_count"] == 0
        assert s["failed_original_count"] == 1


def test_zip_status_cannot_claim_extracted_when_boolean_provenance_is_false():
    s = summarize_original_and_nested_extraction([
        {"extension": ".zip", "text_extraction_status": "archive_extracted",
         "extracted_text_available": False, "nested_extracted_text_count": 0},
    ])
    assert s["extracted_original_count"] == 0
