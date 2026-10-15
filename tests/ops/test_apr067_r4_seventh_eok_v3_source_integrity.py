"""Fail-closed source binder: EOK2020 v3 7 official original UID/SHA files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.acceptance.apr067_r4_four_notice_offline_source import (
    resolve_original_eok_v3,
)

NUMBER = "0348100024426000039"
MANIFEST = "APR067_R4_SEVENTH_EOK_V3_SHA_PINNED_SOURCES_2026-10-15.json"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture()
def frozen(tmp_path: Path) -> tuple[Path, dict, Path]:
    root = tmp_path / "ai-expert-20261012"
    saved = root / "tender_operator_demo/toa-run-20261009052425-d20f58"
    source = saved / "input"
    source.mkdir(parents=True)
    archive = source / "documentation-archive.zip"
    archive.write_bytes(b"original first-party getdocs archive bytes")
    original_rows = []
    pinned_rows = []
    recovered = []
    receipt_path = (
        root / "competitive-missing-11-originals-20261014/private-source-receipt.json"
    )
    receipt_path.parent.mkdir(parents=True)
    for i in range(1, 8):
        uid = f"{i:032X}"
        name = f"Official document {i}.docx"
        if i == 5:
            path = receipt_path.parent / NUMBER / "attachment-05.zip"
            role = "oct14_recovered_first_party_receipt"
            recovered.append({
                "registry_number": NUMBER,
                "slot_in_original_notice": i,
                "name_in_original_notice": name,
                "declared_bytes": len(f"original-data-{i}".encode()),
                "sha256": hashlib.sha256(f"original-data-{i}".encode()).hexdigest(),
                "notice_xml_sha256": "x" * 64,
                "state": "VERIFIED_FIRST_PARTY_BINARY",
                "file": "attachment-05.zip",
            })
        else:
            path = source / f"{uid}.docx"
            role = "oct09_first_party_saved_run"
            original_rows.append({
                "original_name": name, "size_bytes": len(f"original-data-{i}".encode()),
                "stored_name": path.name,
                "source_url": "https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid=" + uid,
            })
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"original-data-{i}".encode())
        pinned_rows.append({
            "source_uid": uid,
            "official_name": name,
            "bytes": path.stat().st_size,
            "sha256": sha(path),
            "source_root_relative_path": str(path.relative_to(root)),
            "file_extension": path.suffix,
            "source_role": role,
        })
    (saved / "metadata.json").write_text(json.dumps({
        "procurement_id": NUMBER, "files": original_rows,
    }))
    receipt_path.write_text(json.dumps(recovered))
    case = {
        "registry_number": NUMBER, "source_role": "ORIGINAL_20_CORPUS",
        "archived_version": 3, "notice_type": "epNotificationEOK2020",
        "archived_zip_sha256": sha(archive),
        "selected_xml_sha256": "x" * 64,
        "selected_xml_attachment_references": 7,
    }
    manifest = {
        "registry_number": NUMBER, "source_role": "ORIGINAL_20_CORPUS",
        "original_saved_run": str(saved.relative_to(root)),
        "archive_relative_path": str(archive.relative_to(root)),
        "archive_sha256": sha(archive),
        "selected_xml_sha256": "x" * 64,
        "selected_notice_version": 3,
        "selected_notice_type": "epNotificationEOK2020",
        "recovery_receipt_relative_path": str(receipt_path.relative_to(root)),
        "recovery_receipt_sha256": sha(receipt_path),
        "attachments": pinned_rows,
    }
    path = tmp_path / MANIFEST
    path.write_text(json.dumps(manifest))
    return root, case, path


def test_seventh_source_seven_originals_are_sha_uid_and_version_bound(frozen):
    root, case, manifest = frozen
    archive, rows = resolve_original_eok_v3(
        source_root=root, case=case, pinned_case_manifest=manifest,
    )
    assert archive.name == "documentation-archive.zip"
    assert len(rows) == 7
    assert len({row["uid"] for row in rows}) == 7
    assert sum(row["file_extension"] == ".zip" for row in rows) == 1


@pytest.mark.parametrize("change", [
    "wrong_sha", "repeated_uid", "path_escape", "v2_instead_of_v3",
    "wrong_original_name", "unknown_provenance",
])
def test_seventh_tampered_source_fails_before_model(frozen, change):
    root, case, path = frozen
    pin = json.loads(path.read_text())
    if change == "wrong_sha":
        pin["attachments"][0]["sha256"] = "0" * 64
    elif change == "repeated_uid":
        pin["attachments"][1]["source_uid"] = pin["attachments"][0]["source_uid"]
    elif change == "path_escape":
        pin["attachments"][0]["source_root_relative_path"] = "../secret.docx"
    elif change == "v2_instead_of_v3":
        pin["selected_notice_version"] = 2
    elif change == "wrong_original_name":
        pin["attachments"][0]["official_name"] = "Newer different edition.docx"
    elif change == "unknown_provenance":
        pin["attachments"][0]["source_role"] = "human_unverified"
    path.write_text(json.dumps(pin))
    with pytest.raises(ValueError):
        resolve_original_eok_v3(
            source_root=root, case=case, pinned_case_manifest=path,
        )


def test_recovered_source_receipt_replacement_fails(frozen):
    root, case, path = frozen
    pin = json.loads(path.read_text())
    receipt = root / pin["recovery_receipt_relative_path"]
    data = json.loads(receipt.read_text())
    data[0]["sha256"] = "0" * 64
    receipt.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="receipt changed"):
        resolve_original_eok_v3(
            source_root=root, case=case, pinned_case_manifest=path,
        )


def test_cross_case_or_wrong_manifest_filename_not_accepted(frozen):
    root, case, path = frozen
    case["registry_number"] = "0348100024426000021"
    with pytest.raises(ValueError, match="unapproved"):
        resolve_original_eok_v3(source_root=root, case=case, pinned_case_manifest=path)
