"""Original archival EIS R4 replay must never run from corrupt saved source."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.acceptance.apr067_r4_problematic_quote_replay import verify_copy_source


@pytest.fixture
def case(tmp_path: Path):
    run = tmp_path / "runs" / "toa-run-20261009052414-56bbe6"
    root = run / "input"
    root.mkdir(parents=True)
    rows = []
    for i in range(8):
        name = f"input-{i:02d}.docx"
        raw = f"archived-source-{i}".encode()
        (root / name).write_bytes(raw)
        rows.append({"file_id": f"FILE-{i + 1:02d}", "stored_name": name,
                     "sha256": hashlib.sha256(raw).hexdigest()})
    z = b"historical-official-zip-test"
    (root / "documentation-archive.zip").write_bytes(z)
    receipt = {
        "run_id": run.name,
        "notice_number": "0376300000126000193",
        "file_sha256": rows, "original_source_file_count": 8,
        "official_archived_zip_sha256": hashlib.sha256(z).hexdigest(),
    }
    return run, receipt


def test_all_eight_unchanged_staged_originals(case):
    assert verify_copy_source(*case) == 8


@pytest.mark.parametrize("bad", ["wrong_case", "wrong_number", "short_inventory", "duplicate_file_id"])
def test_forged_identity_and_manifest_rejected(case, bad):
    run, packet = case
    if bad == "wrong_case":
        packet["run_id"] = "toa-run-20261009052419-3f3f00"
    elif bad == "wrong_number":
        packet["notice_number"] = "0376300000126000194"
    elif bad == "short_inventory":
        packet["file_sha256"].pop()
    else:
        packet["file_sha256"][1]["file_id"] = packet["file_sha256"][0]["file_id"]
    with pytest.raises(ValueError):
        verify_copy_source(run, packet)


def test_modified_saved_original_prevents_replay(case):
    run, packet = case
    (run / "input/input-04.docx").write_bytes(b"forged")
    with pytest.raises(ValueError, match="changed"):
        verify_copy_source(run, packet)


def test_zip_bytes_changed_refuse_model_e2e(case):
    run, packet = case
    (run / "input/documentation-archive.zip").write_bytes(b"forged-archive")
    with pytest.raises(ValueError, match="source ZIP"):
        verify_copy_source(run, packet)


@pytest.mark.parametrize("unsafe", ["../other.docx", "/tmp/unknown.docx", "input-11.docx"])
def test_traversal_and_missing_original_disallowed(case, unsafe):
    run, packet = case
    packet["file_sha256"][0]["stored_name"] = unsafe
    with pytest.raises(ValueError):
        verify_copy_source(run, packet)


def test_absolute_external_symlink_refused(case, tmp_path):
    run, packet = case
    target = tmp_path / "out.docx"
    target.write_bytes(b"forged")
    location = run / "input" / packet["file_sha256"][0]["stored_name"]
    location.unlink()
    location.symlink_to(target)
    with pytest.raises(ValueError):
        verify_copy_source(run, packet)


def test_malformed_source_receipt_refused(case):
    run, packet = case
    packet["file_sha256"][0] = "invalid"
    with pytest.raises(TypeError):
        verify_copy_source(run, packet)
