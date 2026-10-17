"""Local 17-original offline E2E may never analyze modified original bytes."""
from __future__ import annotations

import hashlib

import pytest

from scripts.acceptance.apr067_r4_four_revisions_llm_replay import (
    verify_copy_source,
)

NOTICE = "0151600003226000011"


@pytest.fixture
def staged(tmp_path):
    run = tmp_path / "runs" / "toa-run-isolated"
    src = run / "input"
    src.mkdir(parents=True)
    items = []
    for index in range(5):
        name = f"source-{index:02d}.xml" if index < 1 else f"source-{index:02d}.docx"
        raw = f"original-{index}".encode()
        (src / name).write_bytes(raw)
        items.append({
            "file_id": f"FILE-{index + 1:02d}",
            "stored_name": name,
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
    z = b"synthetic original archive"
    (src / "documentation-archive.zip").write_bytes(z)
    record = {
        "run_id": run.name,
        "registry_number": NOTICE,
        "archive_xml_originals": 1,
        "first_party_attachment_originals": [{} for _ in range(4)],
        "all_input_sha256": items,
        "archived_eis_zip_sha256": hashlib.sha256(z).hexdigest(),
    }
    return run, record


def test_unmodified_all_five_official_sources(staged):
    assert verify_copy_source(*staged) == 5


def test_tampered_real_original_attachment_rejected(staged):
    run, record = staged
    (run / "input/source-01.docx").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="changed"):
        verify_copy_source(run, record)


def test_wrong_original_edition_zip_rejected(staged):
    run, record = staged
    (run / "input/documentation-archive.zip").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="ZIP"):
        verify_copy_source(run, record)


@pytest.mark.parametrize("mutate", [
    lambda x: x.update(registry_number="0376300000126000193"),
    lambda x: x.update(archive_xml_originals=11),
    lambda x: x["all_input_sha256"].pop(),
    lambda x: x["all_input_sha256"][0].update(stored_name="../other.xml"),
    lambda x: x["all_input_sha256"][1].update(file_id="FILE-01"),
])
def test_forged_identity_or_unsafe_metadata_rejected(staged, mutate):
    run, record = staged
    mutate(record)
    with pytest.raises(ValueError):
        verify_copy_source(run, record)
