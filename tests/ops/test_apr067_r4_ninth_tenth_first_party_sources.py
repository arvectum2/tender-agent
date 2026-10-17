"""Additional distinct 44FZ originals: source provenance before real LLM."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.acceptance.apr067_r4_four_notice_offline_source import (
    resolve_recovered_legacy_word_originals,
)

CASES = (
    ("0360600005326000018", 2, (".docx", ".docx", ".doc", ".docx")),
    ("0895100000126000897", 1, (".docx",) * 6),
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frozen_source(tmp_path: Path, reg: str, version: int, exts: tuple[str, ...]):
    root = tmp_path / "ai-expert-20261012"
    run = root / "tender_operator_demo" / "first-party"
    (run / "input").mkdir(parents=True)
    archive = run / "input/documentation-archive.zip"
    archive.write_bytes(b"original archived EIS attachment " + reg.encode())
    (run / "metadata.json").write_text(json.dumps({"procurement_id": reg}))
    receipt = root / "competitive-missing-14-originals-20261014/private-originals-receipt.json"
    receipt.parent.mkdir()
    originals = []
    pins = []
    for i, ext in enumerate(exts, 1):
        uid = f"{i:032X}"
        name = f"Original document {i}{ext}"
        p = receipt.parent / reg / f"attachment-{i:02d}{ext}"
        p.parent.mkdir(exist_ok=True)
        p.write_bytes(f"source {reg} document {i}".encode())
        originals.append({
            "registry_number": reg, "original_name": name,
            "declared_bytes": p.stat().st_size, "actual_bytes": p.stat().st_size,
            "original_eis_notice_xml_sha256": "a" * 64,
            "status": "OFFICIAL_BINARY_SHA_SAVED", "sha256": _sha(p),
            "private_filename": p.name,
        })
        pins.append({
            "source_uid": uid, "official_name": name,
            "bytes": p.stat().st_size, "sha256": _sha(p),
            "source_root_relative_path": str(p.relative_to(root)),
            "file_extension": ext,
            "source_role": "oct14_recovered_first_party_receipt",
        })
    receipt.write_text(json.dumps(originals))
    case = {
        "registry_number": reg,
        "source_role": "ORIGINAL_20_CORPUS",
        "notice_type": "epNotificationEF2020",
        "archived_version": version,
        "archived_zip_sha256": _sha(archive),
        "selected_xml_sha256": "a" * 64,
        "selected_xml_attachment_references": len(pins),
    }
    pin = {
        "registry_number": reg, "source_role": "ORIGINAL_20_CORPUS",
        "original_saved_run": str(run.relative_to(root)),
        "archive_relative_path": str(archive.relative_to(root)),
        "archive_sha256": _sha(archive),
        "selected_notice_type": "epNotificationEF2020",
        "selected_notice_version": version,
        "selected_xml_sha256": "a" * 64,
        "recovery_receipt_relative_path": str(receipt.relative_to(root)),
        "recovery_receipt_sha256": _sha(receipt),
        "attachments": pins,
    }
    manifest = tmp_path / f"APR067_R4_ORIGINAL_{reg}_SHA_PINNED_SOURCES_2026-10-15.json"
    manifest.write_text(json.dumps(pin))
    return root, case, manifest


@pytest.mark.parametrize(("reg", "version", "exts"), CASES)
def test_case_sha_uid_and_every_original_firstparty_document_bound(
    tmp_path: Path, reg: str, version: int, exts: tuple[str, ...],
):
    root, case, manifest = _frozen_source(tmp_path, reg, version, exts)
    path, documents = resolve_recovered_legacy_word_originals(
        source_root=root, case=case, pinned_case_manifest=manifest,
    )
    assert path.name == "documentation-archive.zip"
    assert len(documents) == len(exts)
    assert [x["file_extension"] for x in documents] == list(exts)
    assert len({x["uid"] for x in documents}) == len(documents)


@pytest.mark.parametrize(("reg", "version", "exts"), CASES)
@pytest.mark.parametrize("tamper", [
    "wrong_sha", "duplicate_uid", "wrong_original_version",
    "unsupported_provenance", "unsafe_path", "altered_recovery_receipt",
])
def test_original_attached_file_mismatch_fails_closed_before_llm(
    tmp_path: Path, reg: str, version: int, exts: tuple[str, ...], tamper: str,
):
    root, case, manifest = _frozen_source(tmp_path, reg, version, exts)
    pin = json.loads(manifest.read_text())
    if tamper == "wrong_sha":
        pin["attachments"][0]["sha256"] = "e" * 64
    elif tamper == "duplicate_uid":
        pin["attachments"][1]["source_uid"] = pin["attachments"][0]["source_uid"]
    elif tamper == "wrong_original_version":
        pin["selected_notice_version"] = version + 1
    elif tamper == "unsupported_provenance":
        pin["attachments"][0]["source_role"] = "unverified_later_pdf"
    elif tamper == "unsafe_path":
        pin["attachments"][0]["source_root_relative_path"] = "../../other"
    elif tamper == "altered_recovery_receipt":
        receipt = root / pin["recovery_receipt_relative_path"]
        rows = json.loads(receipt.read_text())
        rows[0]["sha256"] = "e" * 64
        receipt.write_text(json.dumps(rows))
    manifest.write_text(json.dumps(pin))
    with pytest.raises(ValueError):
        resolve_recovered_legacy_word_originals(
            source_root=root, case=case, pinned_case_manifest=manifest,
        )
