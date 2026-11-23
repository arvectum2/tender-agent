"""Exact archived EIS notice filestore manifest and registered original tests."""
from __future__ import annotations

import hashlib
import io
import json
import stat
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from scripts.procurement_llm import prepare_eis_original_documents as p
from scripts.procurement_llm.analysis_queue_worker import (
    QUALITY_GEMMA_LLAMA_BASE_URL,
    QUALITY_GEMMA_LLAMA_MODEL,
    PinnedSource,
)
from src.modules.procurement_learning_corpus.service import (
    append_candidate,
    make_manual_candidate,
)
from src.tender_research.repository import TenderRepository

NUMBER = "0163200000326005243"
ORIGINAL = b"Original fake fixture ZIP bytes from EIS"
SHA = hashlib.sha256(ORIGINAL).hexdigest()


def test_quality_gemma_default_is_llamacpp_not_ollama():
    assert QUALITY_GEMMA_LLAMA_BASE_URL == "http://127.0.0.1:8081/v1"
    assert QUALITY_GEMMA_LLAMA_MODEL == "arvectum-gemma4-12b-it-qat-q4_0"
    assert "11434" not in QUALITY_GEMMA_LLAMA_BASE_URL
    assert "qwen" not in QUALITY_GEMMA_LLAMA_MODEL.lower()


def fixture_docx():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>Настоящее описание объекта закупки</w:t></w:r></w:p>'
            "</w:body></w:document>",
        )
    return stream.getvalue()


def fixture_xml():
    root = ET.Element("epNotificationEOK2020")
    info = ET.SubElement(root, "commonInfo")
    ET.SubElement(info, "purchaseNumber").text = NUMBER
    ET.SubElement(info, "purchaseObjectInfo").text = (
        "Оказание услуг по изменению сайта Смоленской областной Думы"
    )
    attachments = ET.SubElement(root, "attachments")
    node = ET.SubElement(attachments, "attachment")
    ET.SubElement(node, "fileName").text = "Описание объекта закупки.docx"
    ET.SubElement(node, "url").text = (
        "https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?fileId=testid"
    )
    return ET.tostring(root, encoding="utf-8")


def test_manifest_rejects_untrusted_file_before_network(monkeypatch, tmp_path):
    source = PinnedSource(
        observation_id="a" * 64, procurement_ref=NUMBER,
        event_kind="manual:ta-eis-zip:a", original_sha256=SHA,
        path=tmp_path / (SHA + ".zip"), platform="eis",
    )
    monkeypatch.setattr(p, "_selected_notice", lambda src: (
        fixture_xml(),
        {"source_version": 2, "notice_xml_sha256": hashlib.sha256(
            fixture_xml()
        ).hexdigest(), "notice_type": "epNotificationEOK2020"},
    ))
    touched = []
    def fetch(url):
        touched.append(url)
        return fixture_docx()
    manifest, docs = p._snapshot(source, fetch=fetch)
    assert manifest["complete_xml_linked_attachment_count"] == 1
    assert len(docs) == 1
    assert docs[0].kind == "DOCX_MAIN_BODY_OK"
    assert docs[0].sha256 == hashlib.sha256(fixture_docx()).hexdigest()
    assert manifest["selected_notice_source_version"] == 2
    assert not manifest["all_original_binaries_saved"]
    assert not manifest["owner_legal_bid_go"]
    assert "fileId" not in json.dumps(manifest)
    assert len(touched) == 1


@pytest.mark.parametrize("evil", [
    "http://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?x=y",
    "https://evil.example/44fz/filestore/public/1.0/download/priz/file.html?x=y",
    "https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html",
])
def test_filestore_official_host_path_required(monkeypatch, evil):
    xml = fixture_xml().replace(
        b"https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?fileId=testid",
        evil.encode(),
    )
    monkeypatch.setattr(p, "_selected_notice", lambda src: (
        xml, {"source_version": 2, "notice_xml_sha256": hashlib.sha256(xml).hexdigest(),
              "notice_type": "epNotificationEOK2020"},
    ))
    source = PinnedSource(
        observation_id="a" * 64, procurement_ref=NUMBER,
        event_kind="manual:ta-eis-zip:a", original_sha256=SHA,
        path=Path("/tmp/dummy.zip"), platform="eis",
    )
    with pytest.raises(p.SourcePreparationError):
        p._snapshot(source, fetch=lambda x: fixture_docx())


def test_magic_mismatch_rejected(monkeypatch):
    monkeypatch.setattr(p, "_selected_notice", lambda src: (
        fixture_xml(),
        {"source_version": 2, "notice_xml_sha256": hashlib.sha256(
            fixture_xml()
        ).hexdigest(), "notice_type": "epNotificationEOK2020"},
    ))
    source = PinnedSource(
        observation_id="a" * 64, procurement_ref=NUMBER,
        event_kind="manual:ta-eis-zip:a", original_sha256=SHA,
        path=Path("/tmp/dummy.zip"), platform="eis",
    )
    with pytest.raises(p.SourcePreparationError, match="binary format"):
        p._snapshot(source, fetch=lambda x: b"%PDF-This is not DOCX")


def test_exact_original_storage_private_immutable_and_doc_registration(
    session, tmp_path
):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    blob = fixture_docx()
    doc = p.SourceDocument(
        name="Описание объекта закупки.docx",
        source_url_sha256="1" * 64, original_url="https://zakupki.gov.ru/secret",
        role="procurement_object_description", data=blob,
        sha256=hashlib.sha256(blob).hexdigest(), extension=".docx",
        kind="DOCX_MAIN_BODY_OK",
    )
    manifest = {
        "schema": "arvectum_original_eis_source_documents_v1",
        "purchase_number": NUMBER,
        "source_observation_id": "a" * 64,
        "archived_original_zip_sha256": SHA,
        "selected_notice_xml_sha256": "b" * 64,
        "selected_notice_source_version": 2,
        "title_original": "Оказание услуг по изменению сайта Смоленской областной Думы",
        "customer_name_original": "СМОЛЕНСКАЯ ОБЛАСТНАЯ ДУМА",
        "nmck_original": 497178.33,
        "attachments": [{
            "source_index": 1, "original_name": doc.name,
            "source_url_sha256": doc.source_url_sha256,
            "source_role_hint": doc.role,
            "original_binary_sha256": doc.sha256,
            "original_binary_size": len(blob), "binary_type": doc.kind,
            "opaque_unread_content": False,
        }],
        "all_original_binaries_saved": False,
        "owner_legal_bid_go": False,
    }
    saved, fresh = p._attach_paths(manifest, [doc], root)
    assert len(fresh) == 2
    assert all(stat.S_IMODE(q.stat().st_mode) == 0o600 for q in fresh)
    assert "secret" not in (root / "eis-source-documents" / NUMBER / SHA
                             / "source-manifest.json").read_text()
    repeat, changes = p._attach_paths(manifest, [doc], root)
    assert repeat == saved and changes == []
    info = p.register_with_tender_research(session, saved)
    session.commit()
    assert info["registered_original_documents"] == 1
    repo = TenderRepository(session)
    tender = repo.get_tender_by_registry_number(NUMBER)
    assert tender.raw_payload["owner_attested_original_archive_sha256"] == SHA
    assert tender.law_type == "44fz"
    assert len(tender.documents) == 1
    assert tender.documents[0].sha256 == doc.sha256
    assert tender.documents[0].download_status == "downloaded"
    assert tender.documents[0].file_url is None
    assert repo.count_chunks_by_tender(tender.id) == 0
    assert p.register_with_tender_research(session, saved)["registered_original_documents"] == 1
    session.commit()


def test_registration_requires_matching_every_file_sha(session, tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    target = root / "tampered.docx"
    target.write_bytes(b"BAD")
    target.chmod(0o600)
    manifest = {
        "purchase_number": NUMBER, "all_original_binaries_saved": True,
        "attachments": [{
            "owner_private_original_path": str(target),
            "original_binary_sha256": "0" * 64,
        }],
    }
    with pytest.raises(p.SourcePreparationError, match="changed"):
        p.register_with_tender_research(session, manifest)
    assert TenderRepository(session).get_tender_by_registry_number(NUMBER) is None


def test_changed_source_manifest_is_not_overwritten(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    blob = fixture_docx()
    doc = p.SourceDocument(
        name="Описание объекта закупки.docx",
        source_url_sha256="1" * 64, original_url="url", role="attachment",
        data=blob, sha256=hashlib.sha256(blob).hexdigest(), extension=".docx",
        kind="DOCX_MAIN_BODY_OK",
    )
    base = {
        "purchase_number": NUMBER, "archived_original_zip_sha256": SHA,
        "attachments": [{"binary_type": doc.kind}],
    }
    p._attach_paths(base, [doc], root)
    corrupted = {**base, "note": "mutated without a new archive SHA"}
    with pytest.raises(p.SourcePreparationError, match="manifest collision"):
        p._attach_paths(corrupted, [doc], root)


def test_bad_name_is_rejected():
    for name in ("../docx.docx", "evil.exe", "a/b.docx", "", "\x00.docx"):
        with pytest.raises(p.SourcePreparationError):
            p._safe_name(name)


def test_real_gemma_llama_model_only_without_changing_global_process():
    assert QUALITY_GEMMA_LLAMA_BASE_URL.endswith(":8081/v1")
    assert QUALITY_GEMMA_LLAMA_MODEL.startswith("arvectum-gemma4")


def test_full_registered_manifest_revalidated_against_original_xml(
    session, tmp_path, monkeypatch
):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    folder = root / "original-snapshots" / "eis" / NUMBER
    folder.mkdir(mode=0o700, parents=True)
    folder.chmod(0o700)
    source_path = folder / (SHA + ".zip")
    source_path.write_bytes(ORIGINAL)
    source_path.chmod(0o600)
    row = make_manual_candidate({
        "event_id": "ta-eis-zip:" + SHA[:38],
        "procurement_ref": NUMBER, "participation": "reviewed_only",
        "review_state": "source_documented",
        "original_zip_owner_private_path": str(source_path),
        "official_archive_sha256": SHA,
        "training_labels": "NOT_REVIEWED",
    })
    assert append_candidate(session, row)
    session.commit()
    monkeypatch.setattr(p, "_selected_notice", lambda bound_src: (
        fixture_xml(),
        {"source_version": 2, "notice_xml_sha256": hashlib.sha256(
            fixture_xml()
        ).hexdigest(), "notice_type": "epNotificationEOK2020"},
    ))
    live_source = p.source_rows(session)[0]
    assert live_source.observation_id == row["observation_id"]
    manifest, docs = p._snapshot(live_source, fetch=lambda url: fixture_docx())
    saved, _ = p._attach_paths(manifest, docs, root)
    p.register_with_tender_research(session, saved)
    session.commit()
    result = p.verify_registered_exact_source_set(session, NUMBER, root=root)
    assert result["registered_documents_verified"] == 1
    assert result["source_indexable_docx_count"] == 1
    assert result["has_verified_current_legal_status"] is False
    original = Path(saved["attachments"][0]["owner_private_original_path"])
    original.write_bytes(b"changed source")
    with pytest.raises(p.SourcePreparationError, match="checksum"):
        p.verify_registered_exact_source_set(session, NUMBER, root=root)
