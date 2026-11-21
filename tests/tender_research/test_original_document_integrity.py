"""Synthetic original-file fixtures: never call EIS, SOAP or a real network."""

import hashlib
import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.shared.db.base import Base
from src.tender_research import document_store
from src.tender_research.repository import TenderRepository

BODY = b"original-pdf-bytes\n"
URL = "https://zakupki.gov.ru/public/synthetic.pdf"


def _case(tmp_path, *, state="pending", body=None, pinned=None, file_url=URL, declared=None):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    repo = TenderRepository(session)
    tender = repo.upsert_tender({
        "source": "eis", "external_id": "00000000000001",
        "registry_number": "00000000000001", "title": "Synthetic notice",
    })
    local = tmp_path / "stored-original.pdf"
    if body is not None:
        local.write_bytes(body)
    doc = repo.upsert_document({
        "tender_id": tender.id, "source_document_id": "original-1",
        "file_name": "synthetic.pdf", "file_url": file_url,
        "local_path": str(local) if body is not None or state == "downloaded" else None,
        "download_status": state,
        "sha256": pinned,
        "size_bytes": declared,
    })
    cfg = SimpleNamespace(data_dir=str(tmp_path), document_download_max_size_mb=1)
    return session, repo, tender, doc, cfg, local


def _cache_path(tmp_path: Path):
    return tmp_path / "tenders/eis/00000000000001/documents/original/synthetic.pdf"


def test_unchanged_existing_original_is_verified_without_network(tmp_path, monkeypatch):
    digest = hashlib.sha256(BODY).hexdigest()
    session, repo, tender, doc, cfg, _ = _case(
        tmp_path, state="downloaded", body=BODY, pinned=digest, declared=len(BODY),
    )
    monkeypatch.setattr(document_store, "_build_url_opener", lambda *_: pytest.fail("no network"))
    assert document_store.download_tender_documents(repo, tender, cfg) == {"downloaded": 1, "failed": 0}
    assert doc.download_status == "downloaded"
    session.close()


@pytest.mark.parametrize("problem", ["wrong_hash", "missing_file", "missing_digest", "wrong_length", "symlink"])
def test_previously_downloaded_unverified_original_is_blocked(tmp_path, monkeypatch, problem):
    digest = hashlib.sha256(BODY).hexdigest()
    session, repo, tender, doc, cfg, local = _case(
        tmp_path, state="downloaded", body=BODY,
        pinned=digest if problem != "missing_digest" else None,
        declared=len(BODY) if problem != "wrong_length" else len(BODY) + 1,
    )
    if problem == "wrong_hash":
        local.write_bytes(b"tampered")
    if problem == "missing_file":
        local.unlink()
    if problem == "symlink":
        local.unlink()
        local.symlink_to(tmp_path / "outside.pdf")
    monkeypatch.setattr(document_store, "_build_url_opener", lambda *_: pytest.fail("no network retry"))
    assert document_store.download_tender_documents(repo, tender, cfg) == {"downloaded": 0, "failed": 1}
    assert doc.download_status == "failed"
    assert doc.text_extraction_status == "failed"
    assert doc.error_message.startswith("Original integrity failed:")
    session.close()


def test_reused_cached_file_requires_pinned_exact_digest(tmp_path, monkeypatch):
    path = _cache_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(BODY)
    session, repo, tender, doc, cfg, _ = _case(tmp_path, pinned=None)
    monkeypatch.setattr(document_store, "_build_url_opener", lambda *_: pytest.fail("no network"))
    assert document_store.download_tender_documents(repo, tender, cfg) == {"downloaded": 0, "failed": 1}
    assert doc.error_message.startswith("Original integrity failed:")
    assert path.read_bytes() == BODY
    session.close()

    session, repo, tender, doc, cfg, _ = _case(
        tmp_path, pinned=hashlib.sha256(BODY).hexdigest(), declared=len(BODY),
    )
    assert document_store.download_tender_documents(repo, tender, cfg) == {"downloaded": 1, "failed": 0}
    assert doc.download_status == "downloaded"
    assert doc.sha256 == hashlib.sha256(BODY).hexdigest()
    session.close()


@pytest.mark.parametrize("scenario", ["valid", "pinned_hash_mismatch", "declared_size_mismatch", "empty", "oversized"])
def test_original_download_is_size_bounded_and_not_trusted_until_complete(tmp_path, monkeypatch, scenario):
    payload = BODY
    if scenario == "empty":
        payload = b""
    if scenario == "oversized":
        payload = b"X" * (1024 * 1024 + 1)
    pinned = hashlib.sha256(BODY).hexdigest()
    if scenario == "pinned_hash_mismatch":
        pinned = hashlib.sha256(b"another-original").hexdigest()
    declared = len(BODY) + 1 if scenario == "declared_size_mismatch" else None
    session, repo, tender, doc, cfg, _ = _case(tmp_path, pinned=pinned, declared=declared)

    class LimitedStream(io.BytesIO):
        def read(self, size=-1):
            assert 0 <= size <= 1024 * 1024 + 1
            return super().read(size)

    monkeypatch.setattr(document_store, "_build_url_opener", lambda *_: SimpleNamespace(
        open=lambda *_args, **_kwargs: LimitedStream(payload)))
    summary = document_store.download_tender_documents(repo, tender, cfg)
    local = _cache_path(tmp_path)
    if scenario == "valid":
        assert summary == {"downloaded": 1, "failed": 0}
        assert local.read_bytes() == BODY
        assert doc.local_path == str(local)
        assert doc.sha256 == hashlib.sha256(BODY).hexdigest()
    else:
        assert summary == {"downloaded": 0, "failed": 1}
        assert not local.exists()
        assert doc.download_status in {"failed", "skipped"}
        assert not list(local.parent.glob(".source-*"))
    session.close()


def test_preparation_refuses_stale_chunks_when_original_integrity_failed(monkeypatch):
    from unittest.mock import MagicMock, patch

    from src.tender_research.config import TenderResearchConfig
    from src.tender_research.rag.prepare_service import prepare_tender_for_analysis

    doc = MagicMock(
        download_status="failed", text_extraction_status="failed",
        error_message="Original integrity failed: original SHA-256 mismatch",
    )
    tender = MagicMock(
        id="tender-with-stale-index", source="eis", external_id="00000000000001",
        registry_number="00000000000001", documents=[doc],
    )
    repo = MagicMock()
    repo.get_tender_by_registry_number.return_value = tender
    repo.count_chunks_by_tender.return_value = 10  # Previously indexed but unsafe.
    session = MagicMock()
    with (
        patch("src.tender_research.rag.prepare_service.TenderRepository", return_value=repo),
        patch("src.tender_research.rag.prepare_service.load_config",
              return_value=TenderResearchConfig(rag_retrieval_backend="data_platform")),
        patch("src.tender_research.rag.prepare_service.recover_missing_attachments", return_value=0),
        patch("src.tender_research.rag.prepare_service.download_tender_documents",
              return_value={"downloaded": 0, "failed": 1}),
        patch("src.tender_research.rag.prepare_service.build_data_platform_client") as platform,
    ):
        result = prepare_tender_for_analysis("00000000000001", session=session)
    assert result.status == "failed"
    assert result.ready_for_analysis is False
    assert any("Original document verification failed" in e for e in result.errors)
    assert any(s.name == "verify_originals" and s.status == "failed" for s in result.steps)
    platform.assert_not_called()
    session.commit.assert_called_once()


def test_status_flags_existing_integrity_block_without_querying_data_platform():
    from unittest.mock import MagicMock, patch

    from src.tender_research.config import TenderResearchConfig
    from src.tender_research.rag.prepare_service import check_preparation_status

    bad = MagicMock(
        download_status="failed", error_message="Original integrity failed: original file missing",
    )
    tender = MagicMock(id="old-tender", documents=[bad])
    repo = MagicMock()
    repo.get_tender_by_registry_number.return_value = tender
    repo.count_chunks_by_tender.return_value = 10
    repo.count_extracted_documents_by_tender.return_value = 1
    with (
        patch("src.tender_research.rag.prepare_service.TenderRepository", return_value=repo),
        patch("src.tender_research.rag.prepare_service.load_config",
              return_value=TenderResearchConfig(rag_retrieval_backend="data_platform")),
        patch("src.tender_research.rag.prepare_service.build_tender_collection_id",
              return_value="tender:old-tender:rev"),
        patch("src.tender_research.rag.prepare_service.build_data_platform_client") as platform,
    ):
        status = check_preparation_status("00000000000001", session=MagicMock())
    assert status["ready_for_analysis"] is False
    assert "original_integrity" in status["missing"]
    platform.assert_not_called()
