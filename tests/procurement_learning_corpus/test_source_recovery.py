"""No-new-store tests of original archive provenance and report source recovery."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.procurement_llm.source_recovery import (
    inspect_final_eis_protocol,
    locate_original_report_names,
    report_missing_rows,
)

REF = "0137200001226007700"
APP = "193"


def fixture_xml(app: str = APP) -> bytes:
    return (
        "<root><applicationsInfo><applicationInfo>"
        f"<appNumber>{app}</appNumber>"
        "<admissionResultsInfo><admissionResultInfo><admitted>true</admitted>"
        "</admissionResultInfo></admissionResultsInfo>"
        "<finalPrice>449000.00</finalPrice><appRating>26</appRating>"
        "</applicationInfo></applicationsInfo></root>"
    ).encode()


def fixture_zip(path: Path, xml: bytes | None = None) -> Path:
    with ZipFile(path, "w") as archive:
        archive.writestr(
            f"epProtocolEZK2020Final_{REF}_1_ABC.xml",
            xml if xml is not None else fixture_xml(),
        )
    return path


def test_official_zip_sha_and_application_but_no_attribution(tmp_path):
    p = fixture_zip(tmp_path / "original.zip")
    result = inspect_final_eis_protocol(p, REF, APP)
    assert result["application_number"] == APP
    assert result["admitted_in_protocol"] == "true"
    assert result["final_price_rub"] == "449000.00"
    assert result["application_rating"] == "26"
    assert result["original_archive_sha256"] == sha256(p.read_bytes()).hexdigest()
    assert result["protocol_xml_sha256"] == sha256(fixture_xml()).hexdigest()
    assert result["applicant_identity_verified"] is False
    assert result["mutations"] == 0
    assert "Arvectum" not in str(result)


def test_rejects_ambiguous_app_or_wrong_number(tmp_path):
    p = fixture_zip(tmp_path / "original.zip")
    with pytest.raises(ValueError, match="absent or ambiguous"):
        inspect_final_eis_protocol(p, REF, "194")
    duplicated = fixture_xml().replace(b"</root>", b"<applicationInfo><appNumber>193</appNumber></applicationInfo></root>")
    fixture_zip(p, duplicated)
    with pytest.raises(ValueError, match="ambiguous"):
        inspect_final_eis_protocol(p, REF, APP)


def test_rejects_doctype_and_non_official_registry(tmp_path):
    p = fixture_zip(tmp_path / "original.zip", b"<!DOCTYPE root><root/>")
    with pytest.raises(ValueError, match="DOCTYPE|entities"):
        inspect_final_eis_protocol(p, REF, APP)
    with pytest.raises(ValueError, match="19-digit"):
        inspect_final_eis_protocol(p, "not-an-eis-number", APP)


def test_rejects_linked_archives(tmp_path):
    p = fixture_zip(tmp_path / "original.zip")
    link = tmp_path / "symlink.zip"
    link.symlink_to(p)
    with pytest.raises(ValueError, match="symlinked"):
        inspect_final_eis_protocol(link, REF, APP)


def test_report_search_finds_basename_without_restoring_or_claiming_integrity(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    file = root / "analyze_tender_0323100010326000013.md"
    file.write_text("historical fixture, no true receipt")
    missing = [
        {"basename": file.name, "procurement_ref": "0323100010326000013"},
        {"basename": "absent-report.md", "procurement_ref": "0323100010326000013"},
    ]
    summary = locate_original_report_names(missing, [root])
    assert summary["missing_report_rows"] == 2
    assert summary["candidate_report_basenames_found"] == 1
    assert summary["candidate_report_paths_found_unverified"] == 1
    assert summary["restored"] == 0 and summary["mutations"] == 0
    assert file.read_text() == "historical fixture, no true receipt"


def test_file_search_fails_closed_on_budget_and_ignores_symlinks(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    original = tmp_path / "private"
    original.write_text("sensitive")
    (root / "private").symlink_to(original)
    missing = [{"basename": "private", "procurement_ref": REF}]
    summary = locate_original_report_names(missing, [root])
    assert summary["candidate_report_basenames_found"] == 0
    with pytest.raises(RuntimeError, match="budget exceeded"):
        locate_original_report_names(missing, [root], max_files=0)


def test_pg_source_recovery_fails_closed_on_parallel_sqlite(monkeypatch):
    from scripts.procurement_llm import source_recovery

    monkeypatch.setattr(source_recovery, "_engine_url", lambda: "sqlite+pysqlite:///:memory:")
    with pytest.raises(ValueError, match="existing PostgreSQL"):
        report_missing_rows(Path("/nonexistent"))


def test_no_untrusted_xml_external_entities(tmp_path):
    p = fixture_zip(
        tmp_path / "original.zip",
        b'<!DOCTYPE root [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><root>&xxe;</root>',
    )
    with pytest.raises(ValueError, match="entities/DTD"):
        inspect_final_eis_protocol(p, REF, APP)
