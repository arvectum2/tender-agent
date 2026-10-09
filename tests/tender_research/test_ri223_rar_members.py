"""Sanitized RAR5 safety tests and canonical read-only child-document projection."""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.shared.db.base import Base
from src.tender_research.document_store import download_tender_documents
from src.tender_research.providers import ri223_rar_members as rar
from src.tender_research.repository import TenderRepository

ORIGINAL = b"Rar!\x1a\x07\x01\x00" + b"synthetic-no-real-content"
EVIDENCE = {
    "regime": "223fz", "source": "RI223_getDocsIP",
    "archive_sha256": "a" * 64, "xml_sha256": "b" * 64,
    "xml_member": "purchaseNotice.xml",
}


def _fake_archive(tmp_path: Path) -> Path:
    path = tmp_path / "fixture.rar"
    path.write_bytes(ORIGINAL)
    return path


def _mock_listing(monkeypatch, filenames, verbose):
    # Pure archive-metadata unit tests must not require libarchive installed
    # on the GitHub quality runner. The runtime absence remains fail-closed.
    monkeypatch.setattr(rar.shutil, "which", lambda _: "/mocked/bsdtar")
    results = iter([filenames, verbose])
    monkeypatch.setattr(rar, "_run_listing", lambda _args: next(results))


def test_source_bound_rar_only_and_no_44fz_assumptions():
    good = SimpleNamespace(file_name="some.rar", raw_meta={
        "source_regime": "223fz", "evidence": EVIDENCE,
    })
    assert rar.is_ri223_rar_document(good)
    good.raw_meta["source_regime"] = "44fz"
    assert not rar.is_ri223_rar_document(good)
    good.raw_meta["source_regime"] = "223fz"
    good.raw_meta["evidence"] = {}
    assert not rar.is_ri223_rar_document(good)


def test_regular_member_is_returned_with_original_bytes(monkeypatch, tmp_path):
    file = _fake_archive(tmp_path)
    _mock_listing(monkeypatch,
                  ["docs/notice.pdf", "docs/"],
                  ["-rw-r--r-- 0 0 0 6 Jan 1 00:00 docs/notice.pdf",
                   "drwxr-xr-x 0 0 0 0 Jan 1 00:00 docs"])
    monkeypatch.setattr(rar, "_stream_member", lambda _archive, name, size: b"source" if size == 6 else None)
    result = rar.extract_ri223_rar_members(file)
    assert len(result) == 1
    assert result[0].path == "docs/notice.pdf"
    assert result[0].content == b"source"


@pytest.mark.parametrize("name,mode,size", [
    ("../../etc/passwd.pdf", "-", 5),
    ("/tmp/malicious.pdf", "-", 5),
    ("C:/windows/system32.pdf", "-", 5),
    ("dir\\unsafe.pdf", "-", 5),
    ("dir/evil.exe", "-", 5),
    ("docs/symlink.pdf", "l", 5),
    ("valid.pdf", "-", rar.MAX_MEMBER_BYTES + 1),
])
def test_unsafe_member_fails_closed(monkeypatch, tmp_path, name, mode, size):
    file = _fake_archive(tmp_path)
    _mock_listing(monkeypatch, [name],
                  [f"{mode}rw-r--r-- 0 0 0 {size} Jan 1 00:00 {name}"])
    monkeypatch.setattr(rar, "_stream_member", lambda *_: pytest.fail("must reject before streaming"))
    with pytest.raises(rar.Ri223RarError):
        rar.extract_ri223_rar_members(file)


def test_duplicate_names_fail_closed(monkeypatch, tmp_path):
    file = _fake_archive(tmp_path)
    _mock_listing(monkeypatch, ["same.pdf", "same.pdf"], [
        "-rw-r--r-- 0 0 0 5 Jan 1 00:00 same.pdf",
        "-rw-r--r-- 0 0 0 5 Jan 1 00:00 same.pdf",
    ])
    with pytest.raises(rar.Ri223RarError, match="Duplicate"):
        rar.extract_ri223_rar_members(file)


def test_truncated_archive_magic_rejected(tmp_path):
    p = tmp_path / "invalid.rar"
    p.write_bytes(b"malformed")
    with pytest.raises(rar.Ri223RarError, match="signature"):
        rar.extract_ri223_rar_members(p)


def test_ri223_child_document_idempotence_and_provenance(monkeypatch, tmp_path):
    from src.tender_research import document_store
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repo = TenderRepository(session)
        tender = repo.upsert_tender({
            "source": "eis", "external_id": "32616445795", "registry_number": "32616445795",
            "law_type": "223fz", "title": "Synthetic 223-FZ case",
        })
        source = _fake_archive(tmp_path)
        parent = repo.upsert_document({
            "tender_id": tender.id, "source_document_id": "public-uid",
            "file_name": "source.rar",
            "local_path": str(source),
            "file_url": "https://zakupki.gov.ru/public/source.rar",
            "download_status": "downloaded", "sha256": hashlib.sha256(ORIGINAL).hexdigest(),
            "raw_meta": {"source_regime": "223fz", "evidence": EVIDENCE},
        })
        children = [rar.Ri223RarMember("directory/ТЗ.pdf", "ТЗ.pdf", b"%PDF-1.4\ntext")]
        monkeypatch.setattr(document_store, "extract_ri223_rar_members", lambda _: tuple(children))
        cfg = SimpleNamespace(data_dir=str(tmp_path), document_download_max_size_mb=16)
        report = download_tender_documents(repo, tender, cfg)
        assert report == {"downloaded": 1, "failed": 0}
        assert len(tender.documents) == 2
        child = next(d for d in tender.documents if d.id != parent.id)
        assert child.download_status == "downloaded"
        assert child.text_extraction_status == "pending"
        assert Path(child.local_path).read_bytes() == children[0].content
        assert child.raw_meta["evidence"] == EVIDENCE
        assert child.raw_meta["parent_document_id"] == parent.id
        assert child.raw_meta["archive_member"] == "directory/ТЗ.pdf"
        assert child.raw_meta["parent_archive_sha256"] == hashlib.sha256(ORIGINAL).hexdigest()
        assert parent.text_extraction_status == "unsupported"
        assert parent.raw_meta["rar_analysis"]["content_analysis_complete"] is False

        again = download_tender_documents(repo, tender, cfg)
        assert again["downloaded"] == 2
        assert len(tender.documents) == 2  # no additional children / reprocessing


def test_failure_persists_manual_review_not_fake_parsed(monkeypatch, tmp_path):
    from src.tender_research import document_store
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repo = TenderRepository(session)
        tender = repo.upsert_tender({"source": "eis", "external_id": "test", "title": "T"})
        original = _fake_archive(tmp_path)
        parent = repo.upsert_document({
            "tender_id": tender.id, "source_document_id": "not-verified",
            "file_name": "source.rar", "local_path": str(original),
            "download_status": "downloaded", "sha256": hashlib.sha256(ORIGINAL).hexdigest(),
            "raw_meta": {"source_regime": "223fz", "evidence": EVIDENCE},
        })
        monkeypatch.setattr(document_store, "extract_ri223_rar_members",
                            lambda _: (_ for _ in ()).throw(rar.Ri223RarError("Encrypted source")))
        download_tender_documents(repo, tender,
                                  SimpleNamespace(data_dir=str(tmp_path), document_download_max_size_mb=16))
        assert parent.text_extraction_status == "unsupported"
        assert parent.raw_meta["rar_analysis"]["status"] == "NEEDS_REVIEW"
        assert len(tender.documents) == 1


def test_existing_data_platform_projection_ingests_child_files_without_rar(monkeypatch, tmp_path):
    from src.tender_research import document_store
    from src.tender_research.rag.data_platform import DataPlatformDocumentProjector

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repo = TenderRepository(session)
        tender = repo.upsert_tender({
            "source": "eis", "external_id": "32616445795",
            "registry_number": "32616445795", "law_type": "223fz",
            "title": "Synthetic procurement",
        })
        original = _fake_archive(tmp_path)
        repo.upsert_document({
            "tender_id": tender.id, "source_document_id": "public-uid",
            "file_name": "source.rar", "local_path": str(original),
            "download_status": "downloaded",
            "sha256": hashlib.sha256(ORIGINAL).hexdigest(),
            "raw_meta": {"source_regime": "223fz", "evidence": EVIDENCE},
        })
        monkeypatch.setattr(document_store, "extract_ri223_rar_members",
                            lambda _: (rar.Ri223RarMember("ТЗ.docx", "ТЗ.docx", b"safe-document"),))
        cfg = SimpleNamespace(
            data_dir=str(tmp_path), document_download_max_size_mb=16,
            rag_chunk_size_chars=3000, rag_chunk_overlap_chars=150,
            rag_min_chunk_chars=20, document_extract_max_chars=10000,
        )
        download_tender_documents(repo, tender, cfg)
        called = []

        class FakeDataPlatform:
            def process_document(self, *, filename, content, **_kwargs):
                called.append((filename, content))
                return {
                    "extraction_status": "extracted",
                    "text": "Техническое задание: проверенный текст документа для анализа",
                    "chunks": [{"ordinal": 0, "text": "Техническое задание: проверенный текст документа для анализа",
                                "content_hash": hashlib.sha256(b"safe-document").hexdigest(),
                                "char_start": 0, "char_end": 61, "token_estimate": 8}],
                }

        summary = DataPlatformDocumentProjector(repo, FakeDataPlatform(), cfg).build_for_tender(tender)
        assert summary.documents_processed == 1
        assert len(called) == 1 and called[0][1] == b"safe-document"
        child = next(x for x in tender.documents if x.file_name == "ТЗ.docx")
        assert child.text_extraction_status == "extracted"
        assert child.extracted_text_path
        assert len(repo.list_document_chunks(child.id)) == 1
        container = next(x for x in tender.documents if x.file_name == "source.rar")
        assert container.text_extraction_status == "unsupported"
        assert container.raw_meta["rar_analysis"]["status"] == "TEXT_READY_FOR_ANALYSIS"
        assert container.raw_meta["rar_analysis"]["text_projection_complete"] is True
        assert container.raw_meta["rar_analysis"]["members_text_extracted"] == 1
        assert container.raw_meta["rar_analysis"]["content_analysis_complete"] is False
