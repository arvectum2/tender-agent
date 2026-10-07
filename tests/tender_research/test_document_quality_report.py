from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.shared.db.base import Base
from src.tender_research.cli import build_document_quality_report
from src.tender_research.repository import TenderRepository


def _repo() -> TenderRepository:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    return TenderRepository(session)


def test_document_quality_report_summarizes_extensions_and_html_detection(tmp_path):
    repo = _repo()
    tender = repo.upsert_tender({"source": "eis", "external_id": "t-1", "title": "Test"})
    suspicious_path = tmp_path / "spec.pdf"
    suspicious_path.write_text("<html><body>blocked</body></html>", encoding="utf-8")
    repo.upsert_document({
        "tender_id": tender.id,
        "file_name": "spec.pdf",
        "local_path": str(suspicious_path),
        "download_status": "downloaded",
        "text_extraction_status": "empty",
        "content_type": "application/pdf",
        "raw_meta": {
            "data_platform_processing": {
                "ocr_review": {
                    "requires_review": True,
                    "reason": "ocr_low_confidence",
                    "provider": "tesseract",
                    "mean_confidence": 86.89,
                }
            }
        },
    })
    repo.upsert_document({
        "tender_id": tender.id,
        "file_name": "archive.zip",
        "download_status": "downloaded",
        "text_extraction_status": "unsupported",
        "content_type": "application/zip",
        "size_bytes": 2048,
    })
    repo.upsert_document({
        "tender_id": tender.id,
        "file_name": "notes.docx",
        "download_status": "failed",
        "text_extraction_status": "failed",
        "error_message": "boom",
        "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "size_bytes": 1024,
    })

    report = build_document_quality_report(repo, limit=100)

    assert report["total_documents"] == 3
    assert report["downloaded"] == 2
    assert report["empty"] == 1
    assert report["unsupported"] == 1
    assert report["failed_downloads"] == 1
    assert report["zip_count"] == 1
    assert report["docx_count"] == 1
    assert report["pdf_count"] == 1
    assert report["ocr_review_required"] == 1
    assert report["ocr_review_examples"] == [
        {
            "file_name": "spec.pdf",
            "provider": "tesseract",
            "mean_confidence": 86.89,
            "reason": "ocr_low_confidence",
        }
    ]
    assert report["files_with_suspicious_html_instead_of_document"][0]["file_name"] == "spec.pdf"
    assert report["empty_examples"][0]["file_name"] == "spec.pdf"
    assert report["unsupported_examples"][0]["file_name"] == "archive.zip"
