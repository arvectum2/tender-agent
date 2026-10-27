import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from src.modules.market_intelligence.pq_public_223_expand import expand

NUMBER = "32615969197"


def _fixture(tmp_path: Path, member: str = "docs/ukrm.docx",
             correct_sha: bool = True) -> Path:
    source = tmp_path / "source"
    folder = source / NUMBER
    folder.mkdir(parents=True)
    archive = folder / "notice.zip"
    with zipfile.ZipFile(archive, "w") as writer:
        writer.writestr(member, b"Primary document about UKRM")
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    (folder / "public-page-receipt.json").write_text(json.dumps({
        "schema_version": "pq-223-public-page-download/1",
        "registry_number": NUMBER,
        "public_page_sha256": "1" * 64,
        "files": [{"filename": "notice.zip",
                   "sha256": sha if correct_sha else "0" * 64}],
    }))
    return source


def test_safe_public_zip_expand_and_idempotence(tmp_path: Path):
    source = _fixture(tmp_path)
    output = tmp_path / "output"
    result = expand(source_root=source, output_root=output)
    assert result["members_staged"] == 1
    assert result["errors"] == 0
    manifest = json.loads((output / "public-members-manifest.json").read_text())
    item = manifest["records"][0]
    assert item["original_xml_binding_verified"] is False
    assert item["source_page_sha256"] == "1" * 64
    target = output / NUMBER / item["stored_name"]
    assert target.is_file()
    assert expand(source_root=source, output_root=output)["members_staged"] == 1


def test_archive_sha_mismatch_blocks_extraction(tmp_path: Path):
    source = _fixture(tmp_path, correct_sha=False)
    output = tmp_path / "output"
    result = expand(source_root=source, output_root=output)
    assert result["members_staged"] == 0
    assert result["errors"] == 1


def test_unsafe_member_path_is_not_extracted(tmp_path: Path):
    source = _fixture(tmp_path, member="../escape.pdf")
    output = tmp_path / "output"
    result = expand(source_root=source, output_root=output)
    assert result["errors"] == 1
    assert not (tmp_path / "escape.pdf").exists()


def test_invalid_zip_payload_is_recorded_not_aborted(tmp_path: Path):
    source = _fixture(tmp_path)
    archive = source / NUMBER / "notice.zip"
    archive.write_bytes(b"This is not a zip file")
    new_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    receipt = source / NUMBER / "public-page-receipt.json"
    item = json.loads(receipt.read_text())
    item["files"][0]["sha256"] = new_sha
    receipt.write_text(json.dumps(item))
    output = tmp_path / "output"
    result = expand(source_root=source, output_root=output)
    assert result["members_staged"] == 0
    assert result["errors"] == 1
    details = json.loads((output / "public-members-manifest.json").read_text())
    assert details["errors"][0]["error_type"] == "BadZipFile"



def test_manifest_refuses_silent_case_truncation(tmp_path: Path):
    source = _fixture(tmp_path)
    output = tmp_path / "output"
    expand(source_root=source, output_root=output, max_cases=1)
    previous = (output / "public-members-manifest.json").read_bytes()
    original = source / NUMBER
    second = source / "32615969198"
    second.mkdir()
    (second / "notice.zip").write_bytes((original / "notice.zip").read_bytes())
    receipt = json.loads((original / "public-page-receipt.json").read_text())
    receipt["registry_number"] = second.name
    (second / "public-page-receipt.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="would truncate"):
        expand(source_root=source, output_root=output, max_cases=1)
    assert (output / "public-members-manifest.json").read_bytes() == previous
    result = expand(source_root=source, output_root=output, max_cases=2)
    assert result["cases_checked"] == 2
    assert result["members_staged"] == 2


def test_manifest_refuses_silent_archive_truncation(tmp_path: Path):
    source = _fixture(tmp_path)
    case = source / NUMBER
    (case / "another.zip").write_bytes((case / "notice.zip").read_bytes())
    receipt_file = case / "public-page-receipt.json"
    receipt = json.loads(receipt_file.read_text())
    receipt["files"].append({"filename": "another.zip", "sha256": receipt["files"][0]["sha256"]})
    receipt_file.write_text(json.dumps(receipt))
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="would truncate"):
        expand(source_root=source, output_root=output, max_archives=1)
    assert not (output / "public-members-manifest.json").exists()
