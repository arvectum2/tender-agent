import hashlib
import io
import json
import zipfile

from src.modules.market_intelligence.pq_verified_zip_expand import expand
from src.modules.market_intelligence.pq_zip_dp_resume import run


def test_verified_zip_expansion_is_source_bound(tmp_path):
    source = tmp_path / "source"
    folder = source / "32616280467"
    attach = folder / "source-bound-attachments"
    attach.mkdir(parents=True)
    archive = attach / "proof.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("specification.docx", b"original test file")
        z.writestr("malware.exe", b"binary")
        z.writestr("duplicate.docx", b"original test file")
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    (folder / "download_receipt.json").write_text(json.dumps({
        "registry_number": folder.name, "status": "downloaded",
        "records": [{"status": "saved", "stored_name": archive.name,
                     "document_sha256": sha}]}))
    output = tmp_path / "unpacked"
    first = expand(source_root=source, output_root=output)
    second = expand(source_root=source, output_root=output)
    assert first["members_staged"] == second["members_staged"] == 1
    assert first["errors"] == second["errors"] == 0
    assert (output / "32616280467").is_dir()
    m = json.loads((output / "source-manifest.json").read_text())
    assert m["files"][0]["source_zip_sha256"] == sha


def test_zip_ingest_resumes_with_manifest_checksum(tmp_path):
    source = tmp_path / "unpacked"
    source.mkdir()
    (source / "source-manifest.json").write_text(json.dumps({
        "schema_version": "pq-verified-zip-members/1",
        "files": [{"member_sha256": "1"}, {"member_sha256": "2"}]}))
    calls = []
    def extractor(**kwargs):
        calls.append(kwargs["start_offset"])
        return {"files_inspected": 1, "extracted": 1, "errors": 0}
    first = run(source_root=source, runtime=tmp_path / "runtime",
                dp_source=tmp_path, max_files=1, extractor=extractor)
    second = run(source_root=source, runtime=tmp_path / "runtime",
                 dp_source=tmp_path, max_files=1, extractor=extractor)
    third = run(source_root=source, runtime=tmp_path / "runtime",
                dp_source=tmp_path, max_files=1, extractor=extractor)
    assert calls == [0, 1]
    assert first["status"] == "in_progress"
    assert second["status"] == third["status"] == "complete"
