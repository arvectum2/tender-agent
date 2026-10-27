import hashlib
import json
from pathlib import Path

from src.modules.market_intelligence.pq_public_dp_resume import run


def _source(tmp_path: Path):
    root = tmp_path / "sources"
    root.mkdir()
    return root


def _add(root: Path, registry: str, payload: bytes, extension: str = ".docx"):
    digest = hashlib.sha256(payload).hexdigest()
    directory = root / registry
    directory.mkdir(exist_ok=True)
    name = digest + extension
    (directory / name).write_bytes(payload)
    manifest = root / "canonical-manifest.json"
    data = json.loads(manifest.read_text()) if manifest.exists() else {
        "schema_version": "pq-public-canonical/1", "records": []}
    data["records"].append({"registry_number": registry,
                            "member_sha256": digest,
                            "canonical_stored_name": name})
    manifest.write_text(json.dumps(data))
    return f"{registry}/{name}"


def test_resume_only_processes_new_sha_records(tmp_path: Path):
    root = _source(tmp_path)
    one = _add(root, "32615969197", b"First procurement")
    runtime = tmp_path / "runtime"
    seen = []
    def fake_ingest(*, sources, output, include_relative_paths, max_files, **unused):
        selected = sorted(include_relative_paths)
        seen.append(selected)
        rows = [{"path": str(root / name),
                 "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(),
                 "extraction_status": "extracted"} for name in selected]
        output.write_text(json.dumps({"records": rows}))
        return {"files_inspected": len(rows), "errors": 0, "extracted": len(rows)}
    first = run(source_root=root, runtime=runtime, dp_source=tmp_path,
                extractor=fake_ingest)
    assert first["status"] == "complete"
    assert seen == [[one]]
    assert run(source_root=root, runtime=runtime, dp_source=tmp_path,
               extractor=fake_ingest)["files_inspected"] == 0
    two = _add(root, "32616120582", b"New procurement")
    third = run(source_root=root, runtime=runtime, dp_source=tmp_path,
                extractor=fake_ingest)
    assert third["source_count"] == 2
    assert third["processed_count"] == 2
    assert seen == [[one], [two]]


def test_reject_manifest_sha_filename_mismatch(tmp_path: Path):
    root = _source(tmp_path)
    _add(root, "32615969197", b"Evidence")
    manifest = root / "canonical-manifest.json"
    data = json.loads(manifest.read_text())
    data["records"][0]["member_sha256"] = "f" * 64
    manifest.write_text(json.dumps(data))
    import pytest
    with pytest.raises(ValueError, match="Unsafe canonical"):
        run(source_root=root, runtime=tmp_path / "runtime",
            dp_source=tmp_path, extractor=lambda **kwargs: None)
