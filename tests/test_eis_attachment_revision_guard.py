"""Previously unused synthetic EIS inventories test the universal amendment rule.

No examples from manually curated 20 tender passages are needed for these.
These are deterministic *synthetic* challenges, not held-out real EIS gold.
"""
from __future__ import annotations

import hashlib

import pytest

from src.modules.tender_operator_agent_demo.eis_attachment_revision_guard import (
    compare_official_attachment_manifests,
    matching_payload_groups,
    prior_clause_evidence_applicability,
    verify_new_original_binary,
)


def attachment(uid: str, name: str = "contract.docx", size: int = 211) -> dict:
    return {"publishedContentId": uid, "fileName": name, "fileSize": str(size)}


@pytest.mark.parametrize(
    ("old", "new", "added", "removed", "retained"),
    [
        ({}, {"new-A": attachment("new-A")}, ["new-A"], [], []),
        ({"old-A": attachment("old-A")}, {}, [], ["old-A"], []),
        (
            {"keep-A": attachment("keep-A"), "old-B": attachment("old-B")},
            {"keep-A": attachment("keep-A"), "new-C": attachment("new-C"),
             "new-D": attachment("new-D")},
            ["new-C", "new-D"], ["old-B"], ["keep-A"],
        ),
        (
            {"same-A": attachment("same-A")},
            {"same-A": attachment("same-A")},
            [], [], ["same-A"],
        ),
        (
            {"prior-A": attachment("prior-A"), "prior-B": attachment("prior-B")},
            {"survive-C": attachment("survive-C")},
            ["survive-C"], ["prior-A", "prior-B"], [],
        ),
    ],
)
def test_generic_manifest_cardinalities(old, new, added, removed, retained):
    found = compare_official_attachment_manifests(old, new)
    assert found["added_ids"] == added
    assert found["removed_ids"] == removed
    assert found["retained_ids"] == retained
    assert found["requires_fresh_clause_review"] == bool(added or removed)
    assert not found["full_legal_review_signed"]


def test_reused_uid_rewritten_size_is_not_reused_document():
    before = {"kept-X": attachment("kept-X", "specification.pdf", 132)}
    after = {"kept-X": attachment("kept-X", "specification.pdf", 195)}
    found = compare_official_attachment_manifests(before, after)
    assert found["same_uid_metadata_conflicts"] == ["kept-X"]
    assert found["retained_ids"] == []
    assert found["requires_fresh_clause_review"]
    with pytest.raises(ValueError, match="UID"):
        compare_official_attachment_manifests(
            {"key-A": attachment("other-uid")}, {}
        )


def test_attested_new_binary_requires_name_size_uid_and_hash(tmp_path):
    uid = "unseen-UID-9"
    raw = b"a different public procurement attachment"
    target = tmp_path / "new.docx"
    target.write_bytes(raw)
    sha = hashlib.sha256(raw).hexdigest()
    source = attachment(uid, "new.docx", len(raw))
    receipt = {
        "source_uid": uid, "file_name": "new.docx",
        "file_size": len(raw), "sha256": sha,
        "status": "FIRST_PARTY_BINARY_VERIFIED",
    }
    proof = verify_new_original_binary(uid, source, receipt, target)
    assert proof["binary_verified"] and not proof["full_legal_scope_review_signed"]
    assert proof["sha256"] == sha
    for key, changed in [
        ("source_uid", "swapped-UID"),
        ("file_name", "another.docx"),
        ("file_size", len(raw) + 1),
        ("sha256", "a" * 64),
        ("status", "UNVERIFIED"),
    ]:
        with pytest.raises(ValueError):
            verify_new_original_binary(uid, source, receipt | {key: changed}, target)
    target.write_bytes(raw + b"!")
    with pytest.raises(ValueError):
        verify_new_original_binary(uid, source, receipt, target)


def test_per_clause_applicability_is_individual_and_remains_nonlegal():
    old_hash = hashlib.sha256(b"old independent source").hexdigest()
    other_hash = hashlib.sha256(b"current revision changed bytes").hexdigest()
    manifest = {
        "untouched-1": attachment("untouched-1"),
        "changed-2": attachment("changed-2"),
        "added-3": attachment("added-3"),
    }
    assert prior_clause_evidence_applicability(
        original_uid="removed-4", original_sha256=old_hash,
        current_manifest=manifest, independently_verified_current_sha256={}
    ) == "STALE_SOURCE_REFERENCE"
    assert prior_clause_evidence_applicability(
        original_uid="untouched-1", original_sha256=old_hash,
        current_manifest=manifest, independently_verified_current_sha256={}
    ) == "UNKNOWN_CURRENT_BINARY_NOT_VERIFIED"
    assert prior_clause_evidence_applicability(
        original_uid="changed-2", original_sha256=old_hash,
        current_manifest=manifest, independently_verified_current_sha256={"changed-2": other_hash}
    ) == "STALE_SOURCE_BINARY_CHANGED"
    assert prior_clause_evidence_applicability(
        original_uid="untouched-1", original_sha256=old_hash,
        current_manifest=manifest, independently_verified_current_sha256={"untouched-1": old_hash}
    ) == "CURRENT_BINARY_EXACT_MATCH_LEGAL_MEANING_NOT_SIGNED"


def test_invalid_original_attestation_never_becomes_current():
    valid = {"x": attachment("x")}
    with pytest.raises(ValueError):
        prior_clause_evidence_applicability(
            original_uid="x", original_sha256="bad",
            current_manifest=valid, independently_verified_current_sha256={}
        )
    with pytest.raises(ValueError):
        prior_clause_evidence_applicability(
            original_uid="x", original_sha256="b" * 64,
            current_manifest=valid, independently_verified_current_sha256={"x": "UNKNOWN"}
        )



def test_unrelated_zip_wrapper_and_direct_pdf_share_one_evidence_identity(tmp_path):
    import zipfile

    payload = b"%PDF fake binary content for byte-level equality only"
    direct = tmp_path / "direct.pdf"
    nested = tmp_path / "copy.zip"
    other = tmp_path / "other.docx"
    direct.write_bytes(payload)
    with zipfile.ZipFile(nested, "w") as z:
        z.writestr("appendix.pdf", payload)
    other.write_bytes(b"some other unrelated source")
    duplicates = matching_payload_groups({
        "first original": direct, "second original": nested, "third original": other,
    })
    assert len(duplicates) == 1
    assert duplicates[0]["sha256"] == hashlib.sha256(payload).hexdigest()
    assert len(duplicates[0]["source_locations"]) == 2
    assert not matching_payload_groups({"one": direct, "three": other})


def test_duplicate_content_gate_rejects_missing_files_and_zip_bombs(tmp_path):
    import zipfile

    file = tmp_path / "missing.pdf"
    with pytest.raises(ValueError, match="Missing original"):
        matching_payload_groups({"absent": file})
    zipfile_path = tmp_path / "oversized.zip"
    with zipfile.ZipFile(zipfile_path, "w") as archive:
        archive.writestr("member.txt", b"0" * 21000000)
    with pytest.raises(ValueError, match="Unsafe official ZIP"):
        matching_payload_groups({"oversized": zipfile_path})
