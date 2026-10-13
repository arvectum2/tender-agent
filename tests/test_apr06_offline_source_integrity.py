"""Adversarial local-byte integrity tests; all sample procurements are synthetic."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from src.modules.commercial_acceptance.acceptance import AcceptanceError, freeze_manifest
from src.modules.commercial_acceptance.source_integrity import (
    _regular_file_hash,
    verify_offline_bytes,
)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _synthetic_frozen(tmp_path: Path) -> tuple[dict, Path]:
    root = tmp_path / "originals"
    root.mkdir()
    cases = []
    for idx in range(28):
        reg = f"{idx + 1:019d}" if idx < 20 else f"{32600000001 + idx:011d}"
        law = "44fz" if idx < 20 else "223fz"
        location = root / reg
        attachments = location / "attachments"
        attachments.mkdir(parents=True)
        notice_bytes = f"<test-only><purchaseNumber>{reg}</purchaseNumber></test-only>".encode()
        attachment_bytes = f"synthetic test attachment for {reg}".encode()
        doc_hash = _sha(attachment_bytes)
        (location / "notice.bin").write_bytes(notice_bytes)
        (attachments / doc_hash).write_bytes(attachment_bytes)
        cases.append({
            "reg_number": reg,
            "law": law,
            "procedure": "TEST ONLY",
            "subject": f"Synthetic review {reg}",
            "listing_source_url": "https://zakupki.gov.ru/epz/order/",
            "verification": {
                "state": "eis_verified",
                "eis_source_url": "https://zakupki.gov.ru/epz/order/",
                "notice_sha256": _sha(notice_bytes),
                "document_sha256": [doc_hash],
                "verified_at": "2026-10-13T10:00:00+03:00",
            },
        })
    manifest = freeze_manifest({
        "schema_version": "apr06-corpus-v1",
        "cases": cases,
    }, frozen_at="2026-10-13T10:05:00+03:00")
    return manifest, root


def test_matching_bytes_do_not_claim_original_eis_or_human_provenance(tmp_path):
    manifest, root = _synthetic_frozen(tmp_path)
    report = verify_offline_bytes(manifest, root)
    assert report["cases_checked"] == 28
    assert report["files_checked"] == 56
    assert report["bytes_checked"] > 0
    assert report["status"] == "BYTES_MATCH_MANIFEST_ORIGIN_UNVERIFIED"
    assert report["official_eis_provenance_verified"] is False
    assert report["current_notice_revision_verified"] is False
    assert report["human_expert_review_verified"] is False
    assert report["commercial_acceptance"].startswith("BLOCKED")


def test_changed_attachment_does_not_pass_its_old_digest(tmp_path):
    manifest, root = _synthetic_frozen(tmp_path)
    reg = manifest["cases"][0]["reg_number"]
    name = manifest["cases"][0]["verification"]["document_sha256"][0]
    (root / reg / "attachments" / name).write_bytes(b"swapped after freeze")
    with pytest.raises(AcceptanceError, match="attachment byte digest mismatch"):
        verify_offline_bytes(manifest, root)


def test_swapped_notice_bytes_do_not_pass(tmp_path):
    manifest, root = _synthetic_frozen(tmp_path)
    a, b = manifest["cases"][:2]
    (root / a["reg_number"] / "notice.bin").write_bytes(
        (root / b["reg_number"] / "notice.bin").read_bytes()
    )
    with pytest.raises(AcceptanceError, match="notice byte digest mismatch"):
        verify_offline_bytes(manifest, root)


def test_missing_attachment_rejects_claimed_inventory(tmp_path):
    manifest, root = _synthetic_frozen(tmp_path)
    first = manifest["cases"][0]
    (root / first["reg_number"] / "attachments"
     / first["verification"]["document_sha256"][0]).unlink()
    with pytest.raises(AcceptanceError, match="Missing"):
        verify_offline_bytes(manifest, root)


def test_symlinked_original_and_directory_are_rejected(tmp_path):
    manifest, root = _synthetic_frozen(tmp_path)
    first = manifest["cases"][0]
    orig = root / first["reg_number"] / "notice.bin"
    moved = root / first["reg_number"] / "other.bin"
    orig.rename(moved)
    orig.symlink_to(moved)
    with pytest.raises(AcceptanceError, match="symlinked"):
        verify_offline_bytes(manifest, root)
    other = tmp_path / "linked-root"
    other.symlink_to(root, target_is_directory=True)
    with pytest.raises(AcceptanceError, match="symlinked"):
        verify_offline_bytes(manifest, other)


def test_manifest_freeze_digest_is_independently_validated(tmp_path):
    manifest, root = _synthetic_frozen(tmp_path)
    corrupt = copy.deepcopy(manifest)
    corrupt["cases"][0]["verification"]["notice_sha256"] = "f" * 64
    with pytest.raises(AcceptanceError, match="digest"):
        verify_offline_bytes(corrupt, root)


def test_corpus_with_syntactic_hashes_but_no_real_bytes_fails(tmp_path):
    manifest, _ = _synthetic_frozen(tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(AcceptanceError, match="directory"):
        verify_offline_bytes(manifest, empty)


def test_oversized_file_rejected_before_hashing(tmp_path):
    path = tmp_path / "too-large.bin"
    path.write_bytes(b"0123456789")
    with pytest.raises(AcceptanceError, match="oversized"):
        _regular_file_hash(path, size_limit=4)


def test_duplicate_sha_attestations_in_same_procurement_fail(tmp_path):
    manifest, root = _synthetic_frozen(tmp_path)
    corrupt = copy.deepcopy(manifest)
    first = corrupt["cases"][0]["verification"]
    first["document_sha256"] *= 2
    from src.modules.commercial_acceptance.acceptance import sha256

    corrupt.pop("freeze")
    corrupt = freeze_manifest(corrupt, frozen_at="2026-10-13T10:05:00+03:00")
    with pytest.raises(AcceptanceError, match="duplicate attachment digests"):
        verify_offline_bytes(corrupt, root)
