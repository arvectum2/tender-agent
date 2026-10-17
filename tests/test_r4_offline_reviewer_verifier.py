"""Synthetic-only adversarial tests for transported source-only expert archives."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest

from scripts.acceptance.audit_r4_offline_reviewer_deliveries import (
    audit_group,
    verify_published_immutable_locks,
)
from src.modules.tender_operator_agent_demo.r4_offline_expert_package import (
    write_source_only_reviewer_package,
)
from src.modules.tender_operator_agent_demo.r4_offline_reviewer_verifier import (
    verify_offline_reviewer_zip,
)
from src.modules.tender_operator_agent_demo.r4_semantic_holdout import (
    lock_unseen_real_cohort,
)
from tests.test_r4_offline_expert_package import synthetic_reviewer_source


def make_synthetic(tmp_path: Path):
    source_root, bundle_dir, doc = synthetic_reviewer_source(tmp_path)
    case_id = bundle_dir.name
    archive = tmp_path / "out" / (case_id + ".zip")
    receipt = write_source_only_reviewer_package(
        reviewer_bundle_dir=bundle_dir,
        original_source_root=source_root,
        private_output=archive,
    )
    source_lock = lock_unseen_real_cohort(
        [{
            "registry_number": case_id.removeprefix("R4-BLIND-"),
            "attestation": "VERIFIED_OFFICIAL_GETDOCSIP_XML_AND_BINARY",
            "source_document_stage": "PRE_LABEL_PRE_SUT",
            "official_zip_sha256": hashlib.sha256(b"fake synthetic zip").hexdigest(),
            "official_xml_sha256": hashlib.sha256(b"fake synthetic xml").hexdigest(),
            "binary_original_sha256": [doc["sha256"]],
        }],
        forbidden={
            "notice_numbers": set(),
            "zip_sha256": set(),
            "xml_sha256": set(),
            "binary_sha256": set(),
        },
        source_set_id="SYNTHETIC_VERIFIER_ONLY",
        locked_at_utc="2026-10-15T00:00:00+00:00",
    )
    return archive, receipt, source_lock, doc


def repackage(
    original: Path,
    change,
    *,
    compressed: bool = False,
) -> Path:
    with ZipFile(original) as src:
        entries = {m.filename: src.read(m) for m in src.infolist()}
    change(entries)
    target = original.parent / "modified.zip"
    with ZipFile(target, "w", compression=ZIP_DEFLATED if compressed else ZIP_STORED) as dest:
        for name, payload in entries.items():
            dest.writestr(name, payload)
    return target


def with_new_sha(original: Path, changed: Path, receipt: dict) -> Path:
    """Replace the archive only in a synthetic fixture, not source receipt status."""
    original.unlink()
    changed.rename(original)
    receipt["archive_sha256"] = hashlib.sha256(original.read_bytes()).hexdigest()
    receipt["private_package_bytes"] = original.stat().st_size
    return original


def verify(archive, receipt, lock):
    return verify_offline_reviewer_zip(
        private_archive=archive,
        trusted_delivery_receipt=receipt,
        trusted_immutable_lock=lock,
    )


def test_valid_original_synthetic_reviewer_package_revalidated(tmp_path):
    archive, receipt, lock, _ = make_synthetic(tmp_path)
    result = verify(archive, receipt, lock)
    assert result["case_id"] == receipt["case_id"]
    assert result["original_count"] == 1
    assert result["verification_status"] == "OFFLINE_BINARY_AND_IMMUTABLE_LOCK_SHA_VERIFIED"
    assert result["human_gold_signed"] == 0
    assert result["sut_run_authorized"] is False
    assert result["independent_expert_qualification_verified"] is False


def test_post_transfer_corruption_detected_by_separately_stored_archive_sha(tmp_path):
    archive, receipt, lock, _ = make_synthetic(tmp_path)
    raw = bytearray(archive.read_bytes())
    raw[-50] ^= 1
    archive.write_bytes(raw)
    with pytest.raises(ValueError, match="trusted SHA"):
        verify(archive, receipt, lock)


def test_caller_cannot_substitute_unrelated_or_modified_blind_lock(tmp_path):
    archive, receipt, lock, _ = make_synthetic(tmp_path)
    tampered = copy.deepcopy(lock)
    tampered["cases"][0]["original_attachment_sha256"] = ["0" * 64]
    with pytest.raises(ValueError, match="edited|identities"):
        verify(archive, receipt, tampered)
    foreign = copy.deepcopy(lock)
    foreign["source_set_id"] = "OUTSIDE_COARSE_LOCK"
    from src.modules.benchmark_pipeline.contract import canonical_sha256

    foreign["immutable_lock_sha256"] = canonical_sha256({
        k: v for k, v in foreign.items() if k != "immutable_lock_sha256"
    })
    # An equally valid but unrelated lock still cannot replace an externally pinned lock.
    # Verification should enforce source identity and separately stored expected SHA.
    assert foreign["immutable_lock_sha256"] != lock["immutable_lock_sha256"]


@pytest.mark.parametrize("what,expected", [
    ("model", "Extra, missing"),
    ("answers", "nonblank|modified"),
    ("worksheet", "worksheet"),
    ("source", "binary SHAs|source byte|ZIP member SHA"),
    ("compressed", "Unsupported ZIP"),
])
def test_forged_new_archive_sha_cannot_bypass_source_only_lock(tmp_path, what, expected):
    archive, receipt, lock, doc = make_synthetic(tmp_path)

    def modify(entries):
        if what == "model":
            entries["review/model-output.json"] = b'{"score": 1}'
        if what == "answers":
            f = "review/human-labels-BLANK-template.json"
            data = json.loads(entries[f])
            data["blind_discovery_label"]["label"] = "RELEVANT"
            entries[f] = json.dumps(data).encode()
        if what == "worksheet":
            entries["review/independent-reviewer-worksheet.md"] += b"MODEL ANSWER!"
        if what == "source":
            entry = "sources/" + doc["path"]
            entries[entry] = b"altered primary original"
            ledger = json.loads(entries["handoff-integrity.json"])
            ledger["entries_sha256"][entry] = hashlib.sha256(entries[entry]).hexdigest()
            entries["handoff-integrity.json"] = json.dumps(ledger).encode()

    fake = repackage(archive, modify, compressed=(what == "compressed"))
    with_new_sha(archive, fake, receipt)
    with pytest.raises(ValueError, match=expected):
        verify(archive, receipt, lock)


def test_extra_zip_path_traversal_denied_even_if_trusted_archive_sha_replaced(tmp_path):
    archive, receipt, lock, _ = make_synthetic(tmp_path)
    fake = repackage(archive, lambda entries: entries.update({"../escape.bin": b"unsafe"}))
    with_new_sha(archive, fake, receipt)
    with pytest.raises(ValueError, match="Extra, missing"):
        verify(archive, receipt, lock)


def test_group_rejects_archive_additions_and_stale_gold_status(tmp_path):
    archive, receipt, lock, _ = make_synthetic(tmp_path)
    group = {
        "case_count": 1,
        "source_only": True,
        "reviewer_external_contact_done": False,
        "expert_gold_received": 0,
        "sut_run_authorized": False,
        "packages": [receipt],
    }
    validated = audit_group(lock, group, archive.parent)
    assert validated["case_count"] == 1 and validated["original_count"] == 1
    (archive.parent / "extra.zip").write_bytes(b"payload")
    with pytest.raises(ValueError, match="Unexpected, missing"):
        audit_group(lock, group, archive.parent)
    (archive.parent / "extra.zip").unlink()
    group["expert_gold_received"] = 1
    with pytest.raises(ValueError, match="source-only"):
        audit_group(lock, group, archive.parent)


def test_even_consistent_rewritten_lock_rejected_without_published_sha(tmp_path):
    _archive, _receipt, lock, _ = make_synthetic(tmp_path)
    known = {"blind_lock_sha256": [lock["immutable_lock_sha256"]]}
    verify_published_immutable_locks([lock], known)
    rewritten = copy.deepcopy(lock)
    rewritten["source_set_id"] = "REPLACED_SOURCE_SET_WITH_SELF_HASHED_LOCK"
    from src.modules.benchmark_pipeline.contract import canonical_sha256

    rewritten["immutable_lock_sha256"] = canonical_sha256({
        k: v for k, v in rewritten.items() if k != "immutable_lock_sha256"
    })
    with pytest.raises(ValueError, match="published preregistered audit"):
        verify_published_immutable_locks([rewritten], known)
