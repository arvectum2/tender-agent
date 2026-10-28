"""PQ original-document processing through the supported Data Platform SDK facade."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.modules.market_intelligence import pq_dp_ingest
from src.shared.document_processing import ProcessedChunk, ProcessedDocument


def _create_original(root: Path, name: str, payload: bytes) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    file = root / name
    file.write_bytes(payload)
    return file


def test_uses_existing_sdk_facade_and_preserves_source_sha(tmp_path, monkeypatch):
    root = tmp_path / "originals"
    payload = b"Official PQ procurement source in UTF-8"
    doc = _create_original(root, "notice.txt", payload)
    seen = []

    def fake_process(**kwargs):
        seen.append(kwargs)
        return ProcessedDocument(
            extraction_status="extracted",
            text="PQ evidence fragment",
            document_id="dp-source-doc-1",
            chunks=(ProcessedChunk(
                index=0, text="PQ evidence fragment", text_hash="verified-chunk-hash",
                char_start=0, char_end=20, token_estimate=4,
            ),),
        )

    monkeypatch.setattr(pq_dp_ingest, "process_document_bytes", fake_process)
    output = tmp_path / "reports" / "extract.json"
    result = pq_dp_ingest.ingest(
        sources=root, output=output,
        dp_source=tmp_path / "old-dp-source-does-not-exist",
    )
    sha = hashlib.sha256(payload).hexdigest()
    assert result == {
        "files_inspected": 1, "extracted": 1, "errors": 0, "ocr_unverified": 0,
    }
    assert seen == [{
        "content": payload,
        "filename": doc.name,
        "collection_id": "arvectum-pq-evidence",
        "canonical_uri": f"content-sha256://{sha}",
        "max_chars": 100000,
    }]
    saved = json.loads(output.read_text())
    assert saved["signed_contracts_verified"] is False
    assert saved["records"][0]["sha256"] == sha
    assert saved["records"][0]["document_id"] == "dp-source-doc-1"
    assert saved["records"][0]["chunks"] == 1
    assert saved["records"][0]["text_excerpt"] == "PQ evidence fragment"
    assert "Official PQ procurement source" not in output.read_text()


def test_external_failure_has_no_invented_extraction(tmp_path, monkeypatch):
    root = tmp_path / "originals"
    _create_original(root, "notice.xml", b"<source>test</source>")
    def unavailable(**kwargs):
        raise RuntimeError("Data Platform service unavailable")
    monkeypatch.setattr(pq_dp_ingest, "process_document_bytes", unavailable)
    output = tmp_path / "extract.json"
    stats = pq_dp_ingest.ingest(sources=root, output=output, dp_source=tmp_path)
    item = json.loads(output.read_text())["records"][0]
    assert stats["errors"] == 1
    assert stats["extracted"] == 0
    assert item["status"] == "extraction_error"
    assert item["error_type"] == "RuntimeError"
    assert "text_excerpt" not in item
    assert "Data Platform service unavailable" not in output.read_text()


def test_empty_sdk_pdf_keeps_native_fallback_and_sha(tmp_path, monkeypatch):
    root = tmp_path / "originals"
    blob = b"%PDF-synthetic"
    _create_original(root, "spec.pdf", blob)
    monkeypatch.setattr(
        pq_dp_ingest, "process_document_bytes",
        lambda **kw: ProcessedDocument(
            extraction_status="empty", text="", document_id="dp-pdf",
            chunks=(),
        ),
    )
    monkeypatch.setattr(
        pq_dp_ingest, "pdf_text_fallback",
        lambda path: {"status": "extracted", "method": "pdftotext_native_fallback",
                      "text": "Technical PQ text"},
    )
    output = tmp_path / "extract.json"
    stats = pq_dp_ingest.ingest(sources=root, output=output, dp_source=tmp_path)
    item = json.loads(output.read_text())["records"][0]
    assert stats["extracted"] == 1
    assert item["extraction_method"] == "pdftotext_native_fallback"
    assert item["text_excerpt"] == "Technical PQ text"
    assert item["sha256"] == hashlib.sha256(blob).hexdigest()


def test_selective_and_unsafe_source_rejected(tmp_path, monkeypatch):
    root = tmp_path / "originals"
    _create_original(root, "a.txt", b"a")
    _create_original(root, "b.txt", b"b")
    seen = []
    monkeypatch.setattr(
        pq_dp_ingest, "process_document_bytes",
        lambda **kw: (
            seen.append(kw["filename"]),
            ProcessedDocument(extraction_status="extracted", text="ok", chunks=()),
        )[1],
    )
    result = pq_dp_ingest.ingest(
        sources=root, output=tmp_path / "extract.json", dp_source=tmp_path,
        include_relative_paths=frozenset({"b.txt"}),
    )
    assert result["files_inspected"] == 1
    assert seen == ["b.txt"]
    with pytest.raises(ValueError, match="Unsafe selected"):
        pq_dp_ingest.ingest(
            sources=root, output=tmp_path / "unsafe.json", dp_source=tmp_path,
            include_relative_paths=frozenset({"../secret.txt"}),
        )
