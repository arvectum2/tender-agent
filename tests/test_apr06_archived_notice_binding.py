"""APR06 archived EIS edition/attachment evidence; no live-source promotion."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.acceptance.apr06_archived_notice_binding import (
    audit_original_notice_revisions,
)

REG = "0372200172326000015"
RUN = "toa-run-20261009052409-9c4515"


def _xml(version=1, number=REG, deadline="2026-10-16T10:00:00+03:00",
         attachments=(("terms.docx", 5),), tag="epNotificationEZK2020",
         url=None):
    url = url or f"https://zakupki.gov.ru/epz/order/notice/view?regNumber={number}"
    xml_attachments = "".join(
        f"<attachmentInfo><fileName>{name}</fileName><fileSize>{size}</fileSize></attachmentInfo>"
        for name, size in attachments
    )
    xml_deadline = f"<endDT>{deadline}</endDT>" if deadline is not None else ""
    return (
        f"<export><{tag}><versionNumber>{version}</versionNumber>"
        f"<commonInfo><purchaseNumber>{number}</purchaseNumber><href>{url}</href></commonInfo>"
        f"<attachmentsInfo>{xml_attachments}</attachmentsInfo>"
        f"<notificationInfo>{xml_deadline}</notificationInfo>"
        f"</{tag}></export>"
    ).encode()


def _fixture(tmp_path: Path, *, second=False, missing_doc=False, no_date=False):
    base = tmp_path / "runs"
    input_root = base / RUN / "input"
    extracted = input_root / "extracted"
    extracted.mkdir(parents=True)
    archive_root = base / RUN / "procurement"
    archive_root.mkdir()
    pieces = [
        ("notice_1.xml", _xml(version=1, deadline="2026-10-09T08:00:00+03:00"), "notice_1.xml"),
    ]
    if second:
        pieces.append(("notice_2.xml", _xml(version=2, deadline=None if no_date
                                         else "2026-10-16T10:00:00+03:00",
                                         attachments=(("new_terms.docx", 4),)), "notice_2.xml"))
    if not missing_doc:
        pieces.append(("old_terms.docx", b"abcde", "terms.docx"))
        if second:
            pieces.append(("new_terms.docx", b"abcd", "new_terms.docx"))
    originals = []
    rows = []
    for i, (saved, raw, original_name) in enumerate(pieces):
        (extracted / saved).write_bytes(raw)
        originals.append({"sha256": hashlib.sha256(raw).hexdigest(),
                          "bytes": len(raw), "file_id": f"FILE-{i+1:02}"})
        rows.append({"status": "saved",
                     "source_type": ("getdocs_archive" if original_name.endswith(".xml")
                                     else "notice_xml_attachments"),
                     "name": original_name, "stored_name": f"extracted/{saved}",
                     "size_bytes": len(raw)})
    (archive_root / "attachments_manifest.json").write_text(json.dumps(rows), encoding="utf-8")
    manifest = {"schema_version": "apr06-readonly-receipts-v1",
                "cases": [{"reg_number": REG, "run_id": RUN, "document_files": originals}]}
    return manifest, base, extracted


def test_offline_latest_v2_selected_and_only_latest_doc_matched(tmp_path):
    manifest, base, _ = _fixture(tmp_path, second=True)
    result = audit_original_notice_revisions(manifest, base)
    case = result["cases"][0]
    assert case["archived_notice_revisions"] == [1, 2]
    assert case["latest_archived_notice_version"] == 2
    assert case["latest_archived_deadline"] == "2026-10-16T10:00:00+03:00"
    assert case["source_state"] == "ARCHIVED_NAME_SIZE_ONLY_CORRELATION"
    assert case["archive_name_size_correlated"] == 1
    assert case["official_current_eis_status_verified"] is False
    assert case["official_attachment_uid_bound"] is False
    assert result["human_gold_labels"] == 0


def test_latest_attachment_missing_is_not_implied_by_old_version(tmp_path):
    manifest, base, _ = _fixture(tmp_path, second=True, missing_doc=True)
    c = audit_original_notice_revisions(manifest, base)["cases"][0]
    assert c["latest_archived_notice_version"] == 2
    assert c["archive_name_size_unmatched"] == 1
    assert c["source_state"] == "ARCHIVED_LATEST_ATTACHMENTS_INCOMPLETE"


def test_no_deadline_cannot_create_confident_open_state(tmp_path):
    manifest, base, _ = _fixture(tmp_path, second=True, no_date=True)
    c = audit_original_notice_revisions(manifest, base)["cases"][0]
    assert c["source_state"] == "DEADLINE_UNKNOWN_FROM_ARCHIVED_NOTICE"
    assert c["latest_archived_deadline"] is None


def test_receipt_bytes_tampered_fails_closed(tmp_path):
    manifest, base, extracted = _fixture(tmp_path)
    (extracted / "notice_1.xml").write_bytes(_xml(number="1111111111111111111"))
    c = audit_original_notice_revisions(manifest, base)["cases"][0]
    assert c["source_state"] == "FAIL_CLOSED_ORIGINAL_SOURCE_INCONSISTENT"
    assert c["archived_notice_revisions"] == []


def test_wrong_notice_id_fails_closed_even_with_valid_updated_receipt(tmp_path):
    manifest, base, extracted = _fixture(tmp_path)
    altered = _xml(number="1111111111111111111")
    (extracted / "notice_1.xml").write_bytes(altered)
    manifest["cases"][0]["document_files"][0].update({
        "sha256": hashlib.sha256(altered).hexdigest(), "bytes": len(altered)
    })
    c = audit_original_notice_revisions(manifest, base)["cases"][0]
    assert c["source_state"] == "FAIL_CLOSED_ORIGINAL_SOURCE_INCONSISTENT"


def test_conflicting_duplicate_v1_fails_closed(tmp_path):
    manifest, base, extracted = _fixture(tmp_path)
    raw = _xml(version=1,deadline="2026-11-16T10:00:00+03:00")
    (extracted / "notice_duplicate.xml").write_bytes(raw)
    manifest["cases"][0]["document_files"].append({
        "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)
    })
    index = base / RUN / "procurement/attachments_manifest.json"
    rows = json.loads(index.read_text())
    rows.append({"name":"notice_duplicate.xml","stored_name":"extracted/notice_duplicate.xml",
                 "status":"saved","source_type":"getdocs_archive","size_bytes":len(raw)})
    index.write_text(json.dumps(rows))
    c = audit_original_notice_revisions(manifest,base)["cases"][0]
    assert c["source_state"] == "FAIL_CLOSED_ORIGINAL_SOURCE_INCONSISTENT"


def test_untrusted_host_fails_closed(tmp_path):
    manifest, base, extracted = _fixture(tmp_path)
    altered = _xml(url="https://zakupki.gov.ru.bad.example/view")
    (extracted / "notice_1.xml").write_bytes(altered)
    manifest["cases"][0]["document_files"][0].update({
        "sha256":hashlib.sha256(altered).hexdigest(),"bytes":len(altered)})
    assert audit_original_notice_revisions(manifest,base)["cases"][0]["source_state"] == "FAIL_CLOSED_ORIGINAL_SOURCE_INCONSISTENT"


def test_nonnotice_protocol_and_clarification_ignored(tmp_path):
    manifest, base, extracted = _fixture(tmp_path)
    raw = b"<export><epClarificationDoc><versionNumber>999</versionNumber></epClarificationDoc></export>"
    (extracted / "clarification.xml").write_bytes(raw)
    manifest["cases"][0]["document_files"].append({
        "sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw)})
    path=base / RUN / "procurement/attachments_manifest.json"
    rows=json.loads(path.read_text());rows.append({"name":"clarification.xml",
        "stored_name":"extracted/clarification.xml","status":"saved",
        "source_type":"getdocs_archive","size_bytes":len(raw)})
    path.write_text(json.dumps(rows))
    c=audit_original_notice_revisions(manifest,base)["cases"][0]
    assert c["archived_notice_revisions"] == [1]


def test_no_source_files_is_not_a_verified_notice(tmp_path):
    manifest, base, _ = _fixture(tmp_path)
    manifest["cases"][0]["document_files"] = []
    c = audit_original_notice_revisions(manifest,base)["cases"][0]
    assert c["source_state"] == "NO_ARCHIVED_NOTICE"
    assert c["official_current_eis_status_verified"] is False


def test_symlinked_original_does_not_read_other_path(tmp_path):
    manifest, base, extracted = _fixture(tmp_path)
    source=extracted / "notice_1.xml"
    original=source.read_bytes()
    source.unlink()
    outside=tmp_path / "outside.xml"
    outside.write_bytes(original)
    source.symlink_to(outside)
    c=audit_original_notice_revisions(manifest,base)["cases"][0]
    assert c["source_state"] == "FAIL_CLOSED_ORIGINAL_SOURCE_INCONSISTENT"


def test_unsafe_stored_filename_rejected(tmp_path):
    manifest, base, _ = _fixture(tmp_path)
    p=base / RUN / "procurement/attachments_manifest.json"
    rows=json.loads(p.read_text())
    rows[0]["stored_name"]="../../other.xml"
    p.write_text(json.dumps(rows))
    c=audit_original_notice_revisions(manifest,base)["cases"][0]
    assert c["source_state"] == "FAIL_CLOSED_ORIGINAL_SOURCE_INCONSISTENT"


def test_archive_index_missing_is_not_pass(tmp_path):
    manifest, base, _ = _fixture(tmp_path)
    (base / RUN / "procurement/attachments_manifest.json").unlink()
    c = audit_original_notice_revisions(manifest,base)["cases"][0]
    assert c["source_state"] == "FAIL_CLOSED_ORIGINAL_SOURCE_INCONSISTENT"


def test_duplicate_case_cannot_inflate_denominators(tmp_path):
    manifest, base, _ = _fixture(tmp_path)
    manifest["cases"].append(copy.deepcopy(manifest["cases"][0]))
    with pytest.raises(ValueError,match="duplicate"):
        audit_original_notice_revisions(manifest,base)
