"""PQ extraction stays inside the approved local Data Platform SDK boundary."""
from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from src.modules.market_intelligence import pq_dp_ingest


def _settings(url: str = "http://127.0.0.1:8094"):
    return SimpleNamespace(rag_data_platform_base_url=url)


def test_local_sdk_processes_source_with_sha_and_no_dp_checkout(tmp_path, monkeypatch):
    source = tmp_path / "originals"
    source.mkdir()
    original = "УКРМ 10 кВ: проверенный исходный документ".encode()
    (source / "evidence.txt").write_bytes(original)
    calls = []

    def fake_process(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            extraction_status="extracted", text=original.decode("utf-8"),
            document_id="sdk-document-1", chunks=(object(), object()),
        )

    monkeypatch.setattr(pq_dp_ingest, "process_document_bytes", fake_process)
    output = tmp_path / "result.json"
    result = pq_dp_ingest.ingest(
        sources=source, output=output, dp_source=tmp_path / "nonexistent-dp",
        settings=_settings(),
    )
    assert result == {"files_inspected": 1, "extracted": 1, "errors": 0, "ocr_unverified": 0}
    record = json.loads(output.read_text())["records"][0]
    digest = hashlib.sha256(original).hexdigest()
    assert record["sha256"] == digest
    assert record["document_id"] == "sdk-document-1"
    assert record["chunks"] == 2
    assert record["text_excerpt"] == original.decode("utf-8")
    assert calls[0]["canonical_uri"] == f"content-sha256://{digest}"
    assert calls[0]["content"] == original
    assert calls[0]["collection_id"] == "arvectum-pq-evidence"


@pytest.mark.parametrize("url", [
    "https://dp.example.com", "http://192.168.1.2:8094",
    "http://localhost:8094/unsafe", "http://user:secret@localhost:8094",
])
def test_remote_or_unsafe_sdk_endpoint_is_rejected(tmp_path, monkeypatch, url):
    source = tmp_path / "originals"
    source.mkdir()
    (source / "doc.txt").write_text("test")
    monkeypatch.setattr(pq_dp_ingest, "process_document_bytes",
                        lambda **_: pytest.fail("must not call SDK"))
    output = tmp_path / "out.json"
    with pytest.raises(ValueError, match="local Data Platform"):
        pq_dp_ingest.ingest(sources=source, output=output, dp_source=tmp_path,
                            settings=_settings(url))
    assert not output.exists()


def test_failed_sdk_processing_never_counts_as_verified_extraction(tmp_path, monkeypatch):
    source = tmp_path / "originals"
    source.mkdir()
    (source / "doc.txt").write_text("unknown", encoding="utf-8")
    monkeypatch.setattr(
        pq_dp_ingest, "process_document_bytes",
        lambda **_: SimpleNamespace(extraction_status="failed", text="",
                                   document_id=None, chunks=()),
    )
    output = tmp_path / "out.json"
    result = pq_dp_ingest.ingest(sources=source, output=output,
                                 dp_source=tmp_path, settings=_settings())
    assert result["errors"] == 1
    assert result["extracted"] == 0
    assert json.loads(output.read_text())["records"][0]["status"] == "extraction_error"
