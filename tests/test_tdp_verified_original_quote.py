"""Source quote attestation reads only the authorized hashed original."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.modules.tender_operator_agent_demo.verified_original_quote import (
    attest_original_quote,
)
from src.shared.document_processing import ProcessedChunk, ProcessedDocument

QUOTE = "Оплата выполненных работ в течение семи рабочих дней."


def _evidence(tmp_path: Path):
    original = tmp_path / "source"
    original.mkdir()
    data = ("Введение. " + QUOTE + " Заключение.").encode("utf-8")
    (original / "FILE-01.docx").write_bytes(data)
    uri = "tender-upload://" + hashlib.sha256(data).hexdigest()
    text = data.decode("utf-8")
    chunk = ProcessedChunk(
        index=0, text=text, text_hash=hashlib.sha256(text.encode()).hexdigest(),
        char_start=0, char_end=len(text), token_estimate=19, chunk_id="c-001",
    )
    result = ProcessedDocument(
        "extracted", text, (chunk,), "resource-1", "document-1", uri,
    )
    record = {
        "file_id": "FILE-01", "stored_name": "FILE-01.docx",
        "data_platform_source": {
            "resource_id": "resource-1", "document_id": "document-1",
            "canonical_uri": uri, "extraction_status": "extracted",
            "offset_space": "data_platform_normalized_text",
        },
        "evidence_chunks": [{
            "file_id": "FILE-01", "resource_id": "resource-1",
            "document_id": "document-1", "chunk_id": "c-001",
            "text_hash": chunk.text_hash, "char_start": 0,
            "char_end": len(text),
        }],
    }
    return original, record, result


def test_attests_literal_quote_from_stable_dp_source_and_hash(tmp_path):
    root, record, processed = _evidence(tmp_path)
    calls = []

    def processor(**kwargs):
        calls.append(kwargs)
        return processed

    evidence = attest_original_quote(
        input_root=root, file_record=record, exact_quote=QUOTE,
        collection_id="company-tenant-upload", processor=processor,
    )
    assert evidence is not None
    assert evidence["status"] == "literal_quote_found_in_hashed_dp_chunk_only"
    assert evidence["chunk_id"] == "c-001"
    assert evidence["original_sha256"] == hashlib.sha256(
        (root / "FILE-01.docx").read_bytes()
    ).hexdigest()
    assert calls[0]["collection_id"] == "company-tenant-upload"
    assert calls[0]["min_chunk_chars"] == 1


@pytest.mark.parametrize("change", ["wrong_uri", "wrong_id", "changed_original", "wrong_chunk_hash"])
def test_source_mismatch_fails_closed(tmp_path, change):
    root, record, processed = _evidence(tmp_path)
    if change == "wrong_uri":
        record["data_platform_source"]["canonical_uri"] = "tender-upload://wrong"
    elif change == "wrong_id":
        record["data_platform_source"]["document_id"] = "other-document"
    elif change == "changed_original":
        (root / "FILE-01.docx").write_bytes(b"changed original")
    else:
        record["evidence_chunks"][0]["text_hash"] = "other hash"
    assert attest_original_quote(
        input_root=root, file_record=record, exact_quote=QUOTE,
        collection_id="tenant", processor=lambda **_kwargs: processed,
    ) is None


@pytest.mark.parametrize("filename", ["../source/FILE-01.docx", "/etc/passwd", "sub/FILE-01.docx", "..", "sub\\file.docx"])
def test_traversal_and_absolute_path_denied(tmp_path, filename):
    root, record, processed = _evidence(tmp_path)
    record["stored_name"] = filename
    assert attest_original_quote(
        input_root=root, file_record=record, exact_quote=QUOTE,
        collection_id="tenant", processor=lambda **_kwargs: processed,
    ) is None


def test_symlink_denied_even_if_target_is_within_original_directory(tmp_path):
    root, record, processed = _evidence(tmp_path)
    (root / "symlink.docx").symlink_to(root / "FILE-01.docx")
    record["stored_name"] = "symlink.docx"
    assert attest_original_quote(
        input_root=root, file_record=record, exact_quote=QUOTE,
        collection_id="tenant", processor=lambda **_kwargs: processed,
    ) is None


def test_fail_on_oversized_original_and_no_secret_exception_logging(tmp_path):
    root, record, processed = _evidence(tmp_path)
    assert attest_original_quote(
        input_root=root, file_record=record, exact_quote=QUOTE,
        collection_id="tenant", processor=lambda **_kwargs: processed,
        max_original_bytes=4,
    ) is None

    def fail(**_kwargs):
        raise ValueError("secret source document content")

    assert attest_original_quote(
        input_root=root, file_record=record, exact_quote=QUOTE,
        collection_id="tenant", processor=fail,
    ) is None


def test_false_paraphrase_is_not_evidence(tmp_path):
    root, record, processed = _evidence(tmp_path)
    assert attest_original_quote(
        input_root=root, file_record=record,
        exact_quote="Оплата договора через семь рабочих дней.",
        collection_id="tenant", processor=lambda **_kwargs: processed,
    ) is None


def test_authenticated_route_requires_validated_literal_quote(monkeypatch):
    import base64

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.modules.tender_operator_agent_demo import router as operator_router
    from src.shared.api.middleware import TenderPilotBasicAuthMiddleware
    from src.shared.config.settings import Settings

    invoked = []
    monkeypatch.setattr(operator_router, "get_settings", lambda: Settings(
        pilot_auth_enabled=True,
        pilot_auth_username="pilot-operator",
        pilot_auth_password="pilot-private-unique-test-12345",
    ))
    monkeypatch.setattr(
        operator_router, "verify_operator_run_quote",
        lambda **kwargs: (invoked.append(kwargs), {
            "status": "unverified", "evidence": None,
        })[-1],
    )
    app = FastAPI()
    app.include_router(operator_router.router)
    app.add_middleware(
        TenderPilotBasicAuthMiddleware,
        username="pilot-operator",
        password="pilot-private-unique-test-12345",
        protected=("/pilot/tender-agent", "/api/demo/tender-agent"),
        public=("/health",),
    )
    client = TestClient(app)
    url = "/api/demo/tender-agent/workspace/runs/toa-run-20261009101331-bfdddd/verify-quote"
    payload = {"file_id": "FILE-04", "exact_quote": QUOTE}
    assert client.post(url, json=payload).status_code == 401
    headers = {"Authorization": "Basic " + base64.b64encode(
        b"pilot-operator:pilot-private-unique-test-12345"
    ).decode()}
    assert client.post(url, headers=headers, json={
        **payload, "file_id": "../../etc/passwd",
    }).status_code == 422
    assert client.post(url, headers=headers, json={
        **payload, "exact_quote": "short",
    }).status_code == 422
    good = client.post(url, headers=headers, json=payload)
    assert good.status_code == 200
    assert good.json() == {"status": "unverified", "evidence": None}
    assert invoked == [{"run_id": "toa-run-20261009101331-bfdddd", **payload}]


def test_run_level_facade_uses_stored_original_and_fails_closed(monkeypatch, tmp_path):
    from fastapi import HTTPException

    from src.modules.tender_operator_agent_demo import upload_service
    from src.modules.tender_operator_agent_demo.verified_original_quote import (
        verify_operator_run_quote,
    )

    root, record, processed = _evidence(tmp_path)
    metadata = {"files": [record]}
    monkeypatch.setattr(upload_service, "_load_metadata", lambda _run_id: metadata)
    monkeypatch.setattr(upload_service, "_input_dir", lambda _run_id: root)
    monkeypatch.setattr(
        upload_service, "tender_processing_collection_id",
        lambda _scope: "stable-tenant-upload",
    )
    from src.shared import document_processing
    monkeypatch.setattr(
        document_processing, "process_document_bytes",
        lambda **_kwargs: processed,
    )

    good = verify_operator_run_quote(
        run_id="toa-run-20261009101331-bfdddd",
        file_id="FILE-01",
        exact_quote=QUOTE,
    )
    assert good["status"] == "literal_quote_found_in_extracted_original_only"
    assert good["evidence"]["chunk_id"] == "c-001"
    assert "original_pdf_page" not in good["evidence"]
    assert verify_operator_run_quote(
        run_id="toa-run-20261009101331-bfdddd",
        file_id="FILE-01",
        exact_quote="Оплата по договору осуществляется авансом в полном размере.",
    ) == {"status": "unverified", "evidence": None}
    with pytest.raises(HTTPException) as failure:
        verify_operator_run_quote(
            run_id="toa-run-20261009101331-bfdddd",
            file_id="FILE-98",
            exact_quote=QUOTE,
        )
    assert failure.value.status_code == 404
