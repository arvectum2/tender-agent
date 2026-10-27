import hashlib
import json
import zipfile
from pathlib import Path

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
