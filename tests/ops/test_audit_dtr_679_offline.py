"""Pure offline, fixture-only regression gates for issue #679 source evidence."""
from __future__ import annotations

import hashlib
import json

from scripts.ops.audit_dtr_679_offline import CASES, audit, audit_case


def _synthetic_html(registry: str, *, unsafe: bool = False) -> bytes:
    host = "malicious.example" if unsafe else "zakupki.gov.ru"
    links = "".join(
        f'<div class="attachment row"><div class="col clipText"><span class="section__value">'
        f'<a href="https://{host}/44fz/filestore/public/1.0/download/priz/file.html?uid=TEST{i}"'
        f' title="test{i}.docx">test</a></span></div></div>'
        for i in range(4)
    )
    return f'''<div class="row no-gutters notice-documents blockInfo__section">
        <a href="/epz/order/notice/printForm/viewByVersionNumber.html?regNumber={registry}&versionNumber=1&qualifier=regNumberAndVersion">print</a>
        <div class="section__value docName"><span>Извещение в ред. 1</span></div>
        <div><div class="section__attrib">Размещено</div><div class="section__value">19.11.2026 15:28 (МСК)</div></div>
        <div><div class="section__attrib">Редакция</div><div class="section__value">Действующая</div></div>
        <div class="attachmentsTabDocs">{links}</div>
        </div>'''.encode()


def _snapshot(tmp_path, *, unsafe=False):
    number = CASES[2]
    raw = tmp_path / number / "raw"
    raw.mkdir(parents=True)
    files = {
        "public_detail_documents.html": _synthetic_html(number, unsafe=unsafe),
        "public_detail_common_info.html": b"<html><body>synthetic official card</body></html>",
    }
    for name, content in files.items():
        (raw / name).write_bytes(content)
    receipts = {number: {name: (hashlib.sha256(blob).hexdigest(), len(blob)) for name, blob in files.items()}}
    return number, receipts


def test_two_no_source_cases_do_not_infer_empty_official_notices(tmp_path):
    for number in CASES[:2]:
        (tmp_path / number).mkdir()
    result = audit(tmp_path)
    assert result["network_requests"] == result["database_queries"] == 0
    assert result["source_retry_authorized"] is False
    assert all(row["readiness"] == "BLOCKED" for row in result["cases"])
    assert all(row["disposition"] == "source_unavailable" for row in result["cases"][:2])


def test_verified_archived_revision_never_grants_live_current_revision(tmp_path):
    number, receipts = _snapshot(tmp_path)
    before = [(p.name, p.stat().st_mtime_ns) for p in (tmp_path / number / "raw").iterdir()]
    report = audit(tmp_path, receipts=receipts)
    result = report["cases"][2]
    assert result["archived_html_sha_size_verified"] is True
    assert result["historical_revision_verified"] is True
    assert result["historical_attachment_count"] == 4
    assert result["current_official_revision_verified"] is False
    assert result["verified_original_docx_count"] == 0
    assert result["disposition"] == "historical_snapshot_only_original_bytes_unavailable"
    assert before == [(p.name, p.stat().st_mtime_ns) for p in (tmp_path / number / "raw").iterdir()]


def test_hash_drift_is_fail_closed_and_does_not_echo_payload(tmp_path):
    number, receipts = _snapshot(tmp_path)
    secret = "?token=do-not-publish"
    (tmp_path / number / "raw" / "public_detail_documents.html").write_text(secret)
    report = audit(tmp_path, receipts=receipts)
    result = report["cases"][2]
    assert result["disposition"] == "source_evidence_unverified"
    assert result["historical_revision_verified"] is False
    assert secret not in json.dumps(report)


def test_nonofficial_document_links_are_rejected_even_when_html_sha_matches(tmp_path):
    number, receipts = _snapshot(tmp_path, unsafe=True)
    result = audit_case(tmp_path, number, receipts=receipts)
    assert result["archived_html_sha_size_verified"] is True
    assert result["historical_revision_verified"] is False
    assert result["disposition"] == "manual_source_reconciliation_required"
    assert "malicious.example" not in json.dumps(result)


def test_symlink_original_candidate_is_not_trusted(tmp_path):
    number, receipts = _snapshot(tmp_path)
    folder = tmp_path / number / "documents" / "original"
    folder.mkdir(parents=True)
    (folder / "fake.docx").symlink_to(tmp_path / number / "raw" / "public_detail_documents.html")
    result = audit_case(tmp_path, number, receipts=receipts)
    assert result["disposition"] == "source_evidence_unverified"
    assert result["original_bytes_sha_verified"] is False


def test_unverified_local_docx_candidate_never_counts_as_original(tmp_path):
    number, receipts = _snapshot(tmp_path)
    folder = tmp_path / number / "documents" / "original"
    folder.mkdir(parents=True)
    (folder / "unknown.docx").write_bytes(b"not an attested original")
    result = audit_case(tmp_path, number, receipts=receipts)
    assert result["local_original_candidates"] == 1
    assert result["verified_original_docx_count"] == 0
    assert result["disposition"] == "manual_source_reconciliation_required"


def test_symlink_source_root_is_blocked_before_opening_sources(tmp_path):
    root = tmp_path / "true_root"
    root.mkdir()
    link = tmp_path / "source_root_link"
    link.symlink_to(root, target_is_directory=True)
    result = audit_case(link, CASES[2])
    assert result["disposition"] == "unsafe_source_root"
    assert result["original_bytes_sha_verified"] is False
