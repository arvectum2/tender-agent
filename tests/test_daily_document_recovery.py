import hashlib
import io
import zipfile
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.daily_tender_run.document_recovery import (
    save_original,
    source_inventory,
    validate_docx,
    verified_original,
)
from src.tender_research.providers.public_44fz_search import (
    PublicDocumentLink,
    PublicNoticeRevision,
    PublicTenderDetail,
)


def package(extra=None):
    f = io.BytesIO()
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<document/>")
        if extra:
            z.writestr(extra, "fixture")
    return f.getvalue()


def test_bounded_docx_exclusive_preservation(tmp_path):
    original = package()
    validate_docx(original)
    doc = SimpleNamespace(
        id=str(uuid4()), file_name="same.docx", local_path=None, sha256=None
    )
    folder = tmp_path.resolve() / "original"
    path, digest = save_original(folder, doc, original)
    assert digest == hashlib.sha256(original).hexdigest()
    assert path.stat().st_mode & 0o077 == 0
    with pytest.raises(FileExistsError):
        save_original(folder, doc, original)
    doc.local_path = str(path)
    doc.sha256 = digest
    doc.size_bytes = len(original)
    assert verified_original(doc, folder) == path
    path.write_bytes(b"changed")
    with pytest.raises(ValueError):
        verified_original(doc, folder)


@pytest.mark.parametrize(
    "data",
    [
        b"<html>failure</html>",
        b"",
        package("../bad"),
        package("/absolute"),
        package("word\\bad"),
    ],
)
def test_invalid_docx(data):
    with pytest.raises(ValueError):
        validate_docx(data)


def test_exact_inventory_and_revision():
    n = "0173100007526000046"
    revision_url = f"https://zakupki.gov.ru/epz/order/notice/printForm/viewByVersionNumber.html?regNumber={n}&versionNumber=1"
    link = PublicDocumentLink(
        file_name="test.docx",
        url="https://zakupki.gov.ru/filestore/public/1",
        raw={"uid": "id"},
    )
    revision = PublicNoticeRevision(
        revision=1,
        active=True,
        publication_timestamp="20.11.2026",
        source_url=revision_url,
        document_links=[link],
    )
    detail = PublicTenderDetail(
        registry_number=n,
        law_type="44fz",
        document_links=[link],
        active_revision=revision,
        documents_html="<html>fixture</html>",
        raw={
            "documents_fetch_status": "success",
            "document_revision_selection": {
                "status": "active_revision_selected",
                "requires_review": False,
            },
        },
    )
    tender = SimpleNamespace(
        source="eis", law_type="44fz", registry_number=n, documents=[]
    )
    first = source_inventory(tender, detail)
    tender.documents.append(
        SimpleNamespace(
            source_document_id="id",
            file_name=link.file_name,
            file_url=link.url,
            raw_meta={
                "raw": {
                    "revision": 1,
                    "revision_publication_timestamp": revision.publication_timestamp,
                    "revision_source_url": revision_url,
                }
            },
        )
    )
    assert source_inventory(tender, detail) == first
    revision.revision = 2
    with pytest.raises(ValueError, match="revision differs"):
        source_inventory(tender, detail)


def test_stage_transitions_and_no_orphan_overwrite(tmp_path):
    from unittest.mock import Mock

    from src.modules.daily_tender_run.document_recovery import next_document_stage

    folder = tmp_path.resolve() / "documents" / "original"
    repo = Mock()
    repo.count_chunks_by_tender.return_value = 0
    repo.list_document_chunks.return_value = []
    t = SimpleNamespace(id="tender", documents=[])
    assert next_document_stage(repo, t, folder)[0] == "register_inventory"
    d = SimpleNamespace(
        id=str(uuid4()),
        file_name="test.docx",
        download_status="pending",
        text_extraction_status="pending",
        local_path=None,
        sha256=None,
        extracted_text_path=None,
    )
    t.documents = [d]
    assert next_document_stage(repo, t, folder)[0] == "download_document"
    blob = package()
    path, sha = save_original(folder, d, blob)
    with pytest.raises(ValueError, match="unreconciled"):
        next_document_stage(repo, t, folder)
    d.local_path = str(path)
    d.sha256 = sha
    d.size_bytes = len(blob)
    d.download_status = "downloaded"
    assert next_document_stage(repo, t, folder)[0] == "project_document"
    text_dir = folder.parent / "extracted_text"
    text_dir.mkdir()
    f = text_dir / (d.id + ".txt")
    f.write_text("content")
    d.extracted_text_path = str(f)
    d.extracted_text_chars = 7
    d.text_extraction_status = "extracted"
    d.raw_meta = {
        "data_platform_processing": {"ocr_review": {"requires_review": False}}
    }
    chunk = SimpleNamespace(
        id="c",
        document_id=d.id,
        text="content",
        text_hash=hashlib.sha256(b"content").hexdigest(),
        raw_meta={
            "source": "data_platform_projection",
            "data_platform": {"chunk_id": "platform-c"},
        },
    )
    repo.list_document_chunks.return_value = [chunk]
    assert next_document_stage(repo, t, folder)[0] == "ensure_collection"
    chunk.text = "changed"
    with pytest.raises(ValueError, match="projection"):
        next_document_stage(repo, t, folder)


def test_projector_rejects_unknown_scope():
    from unittest.mock import Mock

    from src.tender_research.rag.data_platform import DataPlatformDocumentProjector

    p = DataPlatformDocumentProjector(Mock(), Mock(), Mock())
    t = SimpleNamespace(documents=[SimpleNamespace(id="one")])
    with pytest.raises(ValueError, match="scope"):
        p.build_for_tender(t, document_ids={"other"})
