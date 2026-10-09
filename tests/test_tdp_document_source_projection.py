"""No inferred source IDs or offset drift during the DP -> TA file handoff."""

from __future__ import annotations

import json

from src.modules.tender_operator_agent_demo.document_source_projection import (
    project_document_source,
)
from src.shared.document_processing import ProcessedChunk, ProcessedDocument


def test_source_ids_chunks_and_untrimmed_offset_coordinate_are_preserved():
    original = "  оплата в срок  "
    doc = ProcessedDocument(
        extraction_status="extracted",
        text=original,
        chunks=(ProcessedChunk(
            index=0,
            text="оплата в срок",
            text_hash="actual-platform-hash",
            char_start=2,
            char_end=len(original) - 2,
            token_estimate=3,
            chunk_id="platform-chunk-01",
        ),),
        resource_id="platform-resource-01",
        document_id="platform-document-01",
        canonical_uri="tender-upload://content-sha256",
        metadata={"full_ocr_text": "SECRET_UNPERSISTED_PAYLOAD"},
    )
    provenance, chunks = project_document_source(doc, file_id="FILE-04")
    assert provenance["resource_id"] == "platform-resource-01"
    assert provenance["document_id"] == "platform-document-01"
    assert provenance["source_chunk_count"] == 1
    assert provenance["attributable_chunk_count"] == 1
    assert provenance["normalized_text_leading_trim_chars"] == 2
    assert provenance["normalized_text_trailing_trim_chars"] == 2
    assert provenance["offset_space"] == "data_platform_extracted_text_untrimmed"
    assert chunks[0]["chunk_id"] == "platform-chunk-01"
    assert chunks[0]["file_id"] == "FILE-04"
    assert original[chunks[0]["char_start"]:chunks[0]["char_end"]] == "оплата в срок"
    assert "SECRET_UNPERSISTED_PAYLOAD" not in json.dumps((provenance, chunks))


def test_missing_document_or_chunk_identity_is_not_fabricated():
    doc = ProcessedDocument(
        "extracted",
        "реальные данные",
        (ProcessedChunk(0, "реальные данные", "hash", 0, 15, 2),),
    )
    provenance, chunks = project_document_source(doc, file_id="FILE-01")
    assert provenance["document_id"] is None
    assert provenance["resource_id"] is None
    assert provenance["source_chunk_count"] == 1
    assert provenance["attributable_chunk_count"] == 0
    assert chunks == []


def test_bad_offset_is_never_claimed_as_a_valid_source_chunk():
    doc = ProcessedDocument(
        "extracted", "текст",
        (ProcessedChunk(0, "текст", "hash", 0, 500, 1, "bad-chunk"),),
        "r1", "d1",
    )
    provenance, chunks = project_document_source(doc, file_id="FILE-01")
    assert provenance["source_chunk_count"] == 1
    assert provenance["attributable_chunk_count"] == 0
    assert chunks == []


def test_persisted_operator_file_metadata_keeps_platform_source_chunks(
    client, monkeypatch, tmp_path
):
    """Real upload->analyze HTTP flow retains DP identities per original file."""
    import hashlib

    from tests.test_tender_operator_agent_upload_demo import (
        _sample_upload_payload,
        _set_runs_root,
    )

    runs_root = _set_runs_root(monkeypatch, tmp_path)

    def fake_process_document_bytes(**kwargs):
        text = kwargs["content"].decode("utf-8")
        digest = hashlib.sha256(kwargs["content"]).hexdigest()
        return ProcessedDocument(
            extraction_status="extracted",
            text=text,
            chunks=(ProcessedChunk(
                index=0,
                text=text,
                text_hash=digest,
                char_start=0,
                char_end=len(text),
                token_estimate=10,
                chunk_id="platform-chunk-" + digest[:12],
            ),),
            resource_id="platform-resource-" + digest[:12],
            document_id="platform-document-" + digest[:12],
            canonical_uri=kwargs["canonical_uri"],
            metadata={"ocr_raw_payload": "NEVER_PERSIST_RAW_OCR"},
        )

    monkeypatch.setattr(
        "src.modules.tender_operator_agent_demo.upload_service_legacy.process_document_bytes",
        fake_process_document_bytes,
    )
    data, files = _sample_upload_payload(include_quote=False)
    created = client.post("/api/demo/tender-agent/runs", data=data, files=files)
    assert created.status_code == 200
    rid = created.json()["run_id"]
    analyzed = client.post(f"/api/demo/tender-agent/runs/{rid}/analyze")
    assert analyzed.status_code == 200
    metadata = json.loads((runs_root / rid / "metadata.json").read_text(encoding="utf-8"))
    assert len(metadata["files"]) == 3
    for file in metadata["files"]:
        provenance = file["data_platform_source"]
        assert provenance["resource_id"].startswith("platform-resource-")
        assert provenance["document_id"].startswith("platform-document-")
        assert provenance["attributable_chunk_count"] == 1
        assert provenance["offset_space"] == "data_platform_extracted_text_untrimmed"
        assert file["evidence_chunks"][0]["chunk_id"].startswith("platform-chunk-")
        assert file["evidence_chunks"][0]["file_id"] == file["file_id"]
        assert "NEVER_PERSIST_RAW_OCR" not in json.dumps(provenance)
        assert "NEVER_PERSIST_RAW_OCR" not in json.dumps(file["evidence_chunks"])
