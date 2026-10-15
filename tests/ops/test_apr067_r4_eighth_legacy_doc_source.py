"""4 original 44FZ .doc/.docx sources must retain first-party UID/SHA binding."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.acceptance.apr067_r4_four_notice_offline_source import (
    resolve_recovered_legacy_word_originals,
)

NUMBER = "0127100008626000013"
MANIFEST = "APR067_R4_EIGHTH_LEGACY_DOC_V1_SHA_PINNED_SOURCES_2026-10-15.json"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture()
def source(tmp_path: Path) -> tuple[Path, dict, Path]:
    root = tmp_path / "ai-expert-20261012"
    run = root / "tender_operator_demo/toa-run-20261009052438-25d890"
    (run / "input").mkdir(parents=True)
    (run / "metadata.json").write_text(json.dumps({"procurement_id": NUMBER}))
    zip_path = run / "input/documentation-archive.zip"
    zip_path.write_bytes(b"verified first-party archived getDocsIP source")
    receipt_path = root / "competitive-missing-14-originals-20261014/private-originals-receipt.json"
    receipt_path.parent.mkdir()
    receipts = []
    pinned = []
    for i, ext in enumerate((".docx", ".doc", ".doc", ".docx"), start=1):
        uid = f"{i:032X}"
        name = f"Official document {i}{ext}"
        path = receipt_path.parent / NUMBER / f"attachment-{i:02d}{ext}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"first-party document " + str(i).encode())
        receipts.append({
            "registry_number": NUMBER,
            "original_name": name,
            "declared_bytes": path.stat().st_size,
            "actual_bytes": path.stat().st_size,
            "original_eis_notice_xml_sha256": "a" * 64,
            "status": "OFFICIAL_BINARY_SHA_SAVED",
            "sha256": _hash(path),
            "private_filename": path.name,
        })
        pinned.append({
            "source_uid": uid, "official_name": name,
            "bytes": path.stat().st_size,
            "sha256": _hash(path),
            "file_extension": ext,
            "source_role": "oct14_recovered_first_party_receipt",
            "source_root_relative_path": str(path.relative_to(root)),
        })
    receipt_path.write_text(json.dumps(receipts))
    case = {
        "registry_number": NUMBER,
        "source_role": "ORIGINAL_20_CORPUS",
        "notice_type": "epNotificationEF2020",
        "archived_version": 1,
        "archived_zip_sha256": _hash(zip_path),
        "selected_xml_sha256": "a" * 64,
        "selected_xml_attachment_references": 4,
    }
    manifest = {
        "registry_number": NUMBER,
        "source_role": "ORIGINAL_20_CORPUS",
        "original_saved_run": str(run.relative_to(root)),
        "archive_relative_path": str(zip_path.relative_to(root)),
        "archive_sha256": _hash(zip_path),
        "selected_xml_sha256": "a" * 64,
        "selected_notice_version": 1,
        "selected_notice_type": "epNotificationEF2020",
        "recovery_receipt_relative_path": str(receipt_path.relative_to(root)),
        "recovery_receipt_sha256": _hash(receipt_path),
        "attachments": pinned,
    }
    file = tmp_path / MANIFEST
    file.write_text(json.dumps(manifest))
    return root, case, file


def test_four_attested_originals_keep_two_legacy_word_files(source):
    root, case, path = source
    archive, files = resolve_recovered_legacy_word_originals(
        source_root=root, case=case, pinned_case_manifest=path,
    )
    assert archive.name == "documentation-archive.zip"
    assert [f["file_extension"] for f in files] == [".docx", ".doc", ".doc", ".docx"]
    assert len({f["uid"] for f in files}) == 4


@pytest.mark.parametrize("tamper", [
    "wrong_sha", "duplicate_uid", "different_revision", "wrong_filename",
    "unsupported_role", "unsafe_source_path",
])
def test_source_tampering_blocks_pre_model_stage(source, tamper):
    root, case, path = source
    m = json.loads(path.read_text())
    if tamper == "wrong_sha":
        m["attachments"][2]["sha256"] = "f" * 64
    elif tamper == "duplicate_uid":
        m["attachments"][1]["source_uid"] = m["attachments"][0]["source_uid"]
    elif tamper == "different_revision":
        m["selected_notice_version"] = 2
    elif tamper == "wrong_filename":
        m["attachments"][1]["official_name"] = "old different tender.doc"
    elif tamper == "unsupported_role":
        m["attachments"][0]["source_role"] = "blind_source"
    elif tamper == "unsafe_source_path":
        m["attachments"][0]["source_root_relative_path"] = "../../other.docx"
    path.write_text(json.dumps(m))
    with pytest.raises(ValueError):
        resolve_recovered_legacy_word_originals(
            source_root=root, case=case, pinned_case_manifest=path,
        )


def test_independently_recovered_receipt_mutation_refused(source):
    root, case, path = source
    m = json.loads(path.read_text())
    receipt = root / m["recovery_receipt_relative_path"]
    rows = json.loads(receipt.read_text())
    rows[0]["original_eis_notice_xml_sha256"] = "b" * 64
    receipt.write_text(json.dumps(rows))
    with pytest.raises(ValueError, match="receipt SHA mismatch"):
        resolve_recovered_legacy_word_originals(
            source_root=root, case=case, pinned_case_manifest=path,
        )


def test_another_registry_or_different_original_version_refused(source):
    root, case, path = source
    case["archived_version"] = 3
    with pytest.raises(ValueError, match="unapproved"):
        resolve_recovered_legacy_word_originals(
            source_root=root, case=case, pinned_case_manifest=path,
        )
