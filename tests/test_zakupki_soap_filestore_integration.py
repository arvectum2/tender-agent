from pathlib import Path
from zipfile import ZipFile
from scripts.diagnose_zakupki_soap import download_xml_referenced_attachments
from src.modules.tender_operator_agent_demo import attachment_downloader as module


def test_xml_archive_fetches_attachments_and_verifies_sizes(tmp_path: Path, monkeypatch):
    archive = tmp_path / "notice.zip"
    with ZipFile(archive, "w") as z:
        z.writestr("notice.xml", "<export><attachmentsInfo><attachmentInfo><publishedContentId>123</publishedContentId><fileName>spec.docx</fileName><fileSize>4</fileSize><url>https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid=123</url></attachmentInfo></attachmentsInfo></export>")
    monkeypatch.setattr(module, "_default_transport", lambda *_args, **_kwargs: (b"TEST", "application/octet-stream"))
    result = download_xml_referenced_attachments(archive, tmp_path / "files")
    assert result["complete"] is True and result["downloaded"] == 1
    assert len(list((tmp_path / "files").glob("*"))) == 1


def test_xml_archive_size_mismatch_fails_closed(tmp_path: Path, monkeypatch):
    archive = tmp_path / "notice.zip"
    with ZipFile(archive, "w") as z:
        z.writestr("notice.xml", "<export><attachmentInfo><fileName>spec.docx</fileName><fileSize>10</fileSize><url>https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid=123</url></attachmentInfo></export>")
    monkeypatch.setattr(module, "_default_transport", lambda *_args, **_kwargs: (b"TEST", "application/octet-stream"))
    result = download_xml_referenced_attachments(archive, tmp_path / "files")
    assert result["complete"] is False and result["size_mismatches"] == ["spec.docx"]
