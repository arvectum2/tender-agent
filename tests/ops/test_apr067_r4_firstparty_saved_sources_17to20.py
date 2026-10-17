"""Four final real first-party EIS source UID/revision/SHA tamper guards."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts.acceptance.apr067_r4_four_notice_offline_source import (
    resolve_saved_first_party_originals,
)

CASES = (
    ("0137200001226007700", "epNotificationEZK2020", 1),
    ("0169300008226000223", "epNotificationEZK2020", 1),
    ("0169300008226000225", "epNotificationEZK2020", 1),
    ("0377100005726000128", "epNotificationEF2020", 1),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(tmp_path: Path, reg: str, notice: str, version: int):
    root = tmp_path / "source"
    old = root / "tender_operator_demo" / reg
    (old / "input").mkdir(parents=True)
    archive = old / "input/documentation-archive.zip"
    archive.write_bytes(b"saved original archived ZIP")
    files, pins = [], []
    for i, ext in [(1, ".docx"), (2, ".xls")]:
        uid = f"{i:032X}"
        name = f"original-{i}{ext}"
        path = old / "input" / name
        path.write_bytes(b"first-party original " + str(i).encode())
        files.append({
            "original_name": name, "stored_name": name, "size_bytes": path.stat().st_size,
            "source_url": f"https://zakupki.gov.ru/filestore?uid={uid}",
        })
        pins.append({
            "source_uid": uid, "official_name": name, "bytes": path.stat().st_size,
            "sha256": sha(path), "source_root_relative_path": str(path.relative_to(root)),
            "file_extension": ext, "source_role": "oct09_first_party_saved_run",
            "stored_name": name, "source_slot": i,
        })
    meta = old / "metadata.json"
    meta.write_text(json.dumps({"procurement_id": reg, "files": files}))
    case = {
        "registry_number": reg, "source_role": "ORIGINAL_20_CORPUS",
        "notice_type": notice, "archived_version": version,
        "archived_zip_sha256": sha(archive),
        "selected_xml_sha256": "a" * 64,
        "selected_xml_attachment_references": len(pins),
    }
    pin = {
        "registry_number": reg, "source_role": "ORIGINAL_20_CORPUS",
        "original_saved_run": str(old.relative_to(root)),
        "archive_relative_path": str(archive.relative_to(root)),
        "archive_sha256": sha(archive),
        "selected_xml_sha256": "a" * 64,
        "selected_notice_type": notice,
        "selected_notice_version": version,
        "saved_metadata_sha256": sha(meta),
        "attachments": pins,
    }
    path = tmp_path / f"APR067_R4_FIRST_PARTY_SAVED_{reg}_2026-10-16.json"
    path.write_text(json.dumps(pin))
    return root, case, path


@pytest.mark.parametrize("reg,notice,version", CASES)
def test_first_party_saved_originals_strict_bound(tmp_path, reg, notice, version):
    root, case, path = frozen(tmp_path, reg, notice, version)
    archive, rows = resolve_saved_first_party_originals(
        source_root=root, case=case, pinned_case_manifest=path,
    )
    assert archive.name == "documentation-archive.zip"
    assert len(rows) == 2


@pytest.mark.parametrize("reg,notice,version", CASES)
@pytest.mark.parametrize("tamper", (
    "wrong_revision", "wrong_source_sha", "duplicate_uid", "wrong_slot",
    "unsafe_path", "wrong_saved_metadata_sha", "wrong_saved_filename",
))
def test_first_party_saved_original_tamper_fails_before_model(
    tmp_path, reg, notice, version, tamper,
):
    root, case, path = frozen(tmp_path, reg, notice, version)
    manifest = json.loads(path.read_text())
    first, second = manifest["attachments"]
    if tamper == "wrong_revision":
        manifest["selected_notice_version"] = version + 1
    elif tamper == "wrong_source_sha":
        first["sha256"] = "0" * 64
    elif tamper == "duplicate_uid":
        second["source_uid"] = first["source_uid"]
    elif tamper == "wrong_slot":
        first["source_slot"] = 2
    elif tamper == "unsafe_path":
        first["source_root_relative_path"] = "../outside"
    elif tamper == "wrong_saved_metadata_sha":
        manifest["saved_metadata_sha256"] = "1" * 64
    elif tamper == "wrong_saved_filename":
        first["stored_name"] = "renamed.docx"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        resolve_saved_first_party_originals(
            source_root=root, case=case, pinned_case_manifest=path,
        )
