"""The operator intake facade delegates extraction without copying DP engine."""

from __future__ import annotations

import hashlib

from src.modules.tender_operator_agent_demo.operator_document_extraction import (
    extract_operator_document,
)
from src.shared.document_processing import ProcessedDocument


def test_process_request_retains_content_hash_uri_and_source_response():
    observed = {}

    def processor(**kwargs):
        observed.update(kwargs)
        return ProcessedDocument("extracted", "  Русский текст  ", ())

    output = extract_operator_document(
        file_name="техзадание.docx",
        content=b"example",
        collection_id="tenant-tender-collection",
        processor=processor,
    )
    assert output[0] == "Русский текст"
    assert output[1] == []
    assert output[2] == "extracted"
    assert output[3].text == "  Русский текст  "
    assert observed["filename"] == "техзадание.docx"
    assert observed["collection_id"] == "tenant-tender-collection"
    assert observed["canonical_uri"] == "tender-upload://" + hashlib.sha256(b"example").hexdigest()
    assert observed["min_chunk_chars"] == 1


def test_processor_failure_is_fail_closed_and_does_not_persist_exception_details():
    def processor(**kwargs):
        raise ValueError("private document data should not enter warning")

    text, warnings, status, document = extract_operator_document(
        file_name="../../unsafe.doc", content=b"secret", collection_id="tenant", processor=processor,
    )
    assert status == "failed" and text is None and document is None
    assert len(warnings) == 1
    assert "private document data" not in str(warnings)
    assert "unsafe.doc" in warnings[0]


def test_unsupported_document_still_warns_without_inventing_content():
    text, warnings, status, document = extract_operator_document(
        file_name="скан.pdf", content=b"pdf", collection_id="tenant",
        processor=lambda **_kwargs: ProcessedDocument("unsupported", "", ()),
    )
    assert text is None and status == "unsupported"
    assert len(warnings) == 1
    assert document is not None
