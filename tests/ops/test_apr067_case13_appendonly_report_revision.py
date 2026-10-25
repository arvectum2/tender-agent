"""Append-only case-13 report integrity and conservative history protections."""
import hashlib
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from src.modules.tender_operator_agent_demo.operator_report_revision import (
    published_report_path,
    verified_revision,
)

RUN = "synthetic-source-run"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fake_revision(tmp_path: Path) -> Path:
    root = tmp_path / "runs" / RUN
    output = root / "output"
    input_dir = root / "input"
    revision = output / "report-revisions" / "source-correction-v1"
    revision.mkdir(parents=True)
    input_dir.mkdir()
    (root / "metadata.json").write_text('{"run_id":"synthetic-source-run"}')
    (output / "report.json").write_text('{"original":true}')
    (output / "report.html").write_text("original immutable historical HTML")
    rows = []
    for i in range(9):
        name = f"original-{i}.docx" if i else "extracted/original-xml.xml"
        source = input_dir / name
        source.parent.mkdir(exist_ok=True)
        source.write_bytes(f"official source {i}".encode())
        rows.append({"stored_name": name, "sha256": sha(source)})
    (revision / "report.json").write_text('{"revision":true}')
    (revision / "report.html").write_text("corrected source-only HTML")
    manifest = {
        "revision": "source-correction-v1",
        "run_id": RUN,
        "registry_number": "0349100009326000005",
        "original_report_json_sha256": sha(output / "report.json"),
        "original_report_html_sha256": sha(output / "report.html"),
        "original_metadata_sha256": sha(root / "metadata.json"),
        "original_source_files": rows,
        "revision_report_json_sha256": sha(revision / "report.json"),
        "revision_report_html_sha256": sha(revision / "report.html"),
    }
    (output / "report-revision.json").write_text(json.dumps(manifest))
    return output


def test_without_revision_original_report_preserved(tmp_path: Path):
    output = tmp_path / "output"
    output.mkdir()
    assert verified_revision(output, RUN) is None
    assert published_report_path(output, RUN, "html") == output / "report.html"


def test_valid_append_only_revision_is_selected(tmp_path: Path):
    output = fake_revision(tmp_path)
    assert verified_revision(output, RUN) is not None
    assert published_report_path(output, RUN, "json").read_text() == '{"revision":true}'
    assert published_report_path(output, RUN, "html").read_text() == "corrected source-only HTML"
    assert (output / "report.html").read_text() == "original immutable historical HTML"


@pytest.mark.parametrize("tamper", (
    "original_html", "original_json", "metadata", "original_file",
    "revision_html", "revision_json", "wrong_registry",
    "wrong_run", "path_traversal", "duplicate_source_slot",
))
def test_revision_integrity_fails_closed(tmp_path: Path, tamper: str):
    output = fake_revision(tmp_path)
    manifest_path = output / "report-revision.json"
    manifest = json.loads(manifest_path.read_text())
    if tamper == "original_html":
        (output / "report.html").write_text("modified original")
    elif tamper == "original_json":
        (output / "report.json").write_text("modified original")
    elif tamper == "metadata":
        (output.parent / "metadata.json").write_text("modified original")
    elif tamper == "original_file":
        (output.parent / "input" / "original-5.docx").write_bytes(b"tampered file")
    elif tamper == "revision_html":
        (output / "report-revisions/source-correction-v1/report.html").write_text("damaged")
    elif tamper == "revision_json":
        (output / "report-revisions/source-correction-v1/report.json").write_text("damaged")
    elif tamper == "wrong_registry":
        manifest["registry_number"] = "0000000000000000000"
    elif tamper == "wrong_run":
        manifest["run_id"] = "wrong-run"
    elif tamper == "path_traversal":
        manifest["original_source_files"][0]["stored_name"] = "../unbound.xml"
    elif tamper == "duplicate_source_slot":
        manifest["original_source_files"].append(manifest["original_source_files"][0])
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(HTTPException) as error:
        published_report_path(output, RUN, "html")
    assert error.value.status_code == 409


def test_never_accept_symlinked_original_source(tmp_path: Path):
    output = fake_revision(tmp_path)
    original = output.parent / "input" / "original-2.docx"
    original.unlink()
    original.symlink_to(output.parent / "input" / "original-1.docx")
    with pytest.raises(HTTPException) as error:
        verified_revision(output, RUN)
    assert error.value.status_code == 409


def test_unsupported_report_kind_rejected(tmp_path: Path):
    output = fake_revision(tmp_path)
    with pytest.raises(ValueError):
        published_report_path(output, RUN, "../metadata.json")
