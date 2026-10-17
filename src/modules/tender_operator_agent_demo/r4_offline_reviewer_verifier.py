"""Fail-closed verification of offline source-only expert ZIPs after transfer.

The external archive SHA and immutable EIS lock MUST be obtained through a
separate trusted channel. An integrity JSON contained INSIDE the archive is
not a signature, cannot establish independence and cannot attest expertise.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_STORED, BadZipFile, ZipFile

from src.modules.benchmark_pipeline.contract import (
    canonical_sha256,
    validate_case_manifest_consistency,
)
from src.modules.benchmark_pipeline.workflow import assert_blind_evaluator_bundle
from src.modules.tender_operator_agent_demo.r4_blind_reviewer_assignment import (
    build_source_only_assignment,
    human_label_input_template,
)
from src.modules.tender_operator_agent_demo.r4_offline_expert_package import (
    _ALLOWED_METADATA,
    _ZIP_UNCOMPRESSED_LIMIT,
    _safe_relative_source,
)
from src.modules.tender_operator_agent_demo.r4_semantic_holdout import (
    verify_cohort_lock,
)

_PURPOSE = "INDEPENDENT_HUMAN_BLIND_REVIEW_ONLY_NO_MODEL_GOLD"


def verify_offline_reviewer_zip(
    *, private_archive: Path,
    trusted_delivery_receipt: dict,
    trusted_immutable_lock: dict,
) -> dict:
    """Independently re-read exact packaged bytes without running SUT."""
    if private_archive.is_symlink() or not private_archive.is_file():
        raise ValueError("Reviewer package must be a real, non-symlink archive")
    if private_archive.stat().st_size > _ZIP_UNCOMPRESSED_LIMIT + 5_000_000:
        raise ValueError("Reviewer archive exceeds permitted transport size")
    if trusted_delivery_receipt.get("sut_run_authorized") is not False or (
        trusted_delivery_receipt.get("signed_expert_gold_count") != 0
    ):
        raise ValueError("Receipt is not an original unsigned source-only handoff")
    case_id = trusted_delivery_receipt.get("case_id")
    if not isinstance(case_id, str) or not case_id.startswith("R4-BLIND-"):
        raise ValueError("Invalid reviewer source case ID")
    if private_archive.name != case_id + ".zip":
        raise ValueError("Reviewer transport filename and case identity differ")
    digest = hashlib.sha256(private_archive.read_bytes()).hexdigest()
    if digest != trusted_delivery_receipt.get("archive_sha256"):
        raise ValueError("Offline reviewer archive does not match separate trusted SHA receipt")
    if private_archive.stat().st_size != trusted_delivery_receipt.get("private_package_bytes"):
        raise ValueError("Archive transport size differs from trusted receipt")
    verify_cohort_lock(trusted_immutable_lock)
    if trusted_immutable_lock.get("bid_ready") is not False:
        raise ValueError("Reviewer source lock cannot authorize bids")
    matches = [
        case for case in trusted_immutable_lock.get("cases", [])
        if "R4-BLIND-" + case["registry_number"] == case_id
    ]
    if len(matches) != 1:
        raise ValueError("Packaged case is not in supplied immutable EIS lock")
    try:
        with ZipFile(private_archive) as archive:
            members = archive.infolist()
            names = [item.filename for item in members]
            if len(names) != len(set(names)):
                raise ValueError("Duplicate ZIP member names are forbidden")
            if len(members) > 65 or sum(item.file_size for item in members) > _ZIP_UNCOMPRESSED_LIMIT:
                raise ValueError("Unbounded ZIP member count or uncompressed bytes")
            for member in members:
                if (
                    member.is_dir()
                    or member.compress_type != ZIP_STORED
                    or (member.external_attr >> 16) & 0o170000 == 0o120000
                    or member.file_size <= 0
                ):
                    raise ValueError("Unsupported ZIP member, symlink or compression")
            fixed = {"review/" + name for name in _ALLOWED_METADATA}
            fixed.add("handoff-integrity.json")
            if not fixed.issubset(names):
                raise ValueError("Missing immutable reviewer metadata in offline package")
            bundle = json.loads(archive.read("review/evaluator_bundle.json"))
            manifest = json.loads(archive.read("review/case_manifest.json"))
            blanks = json.loads(archive.read("review/human-labels-BLANK-template.json"))
            proof = json.loads(archive.read("handoff-integrity.json"))
            assert_blind_evaluator_bundle(bundle)
            validate_case_manifest_consistency(manifest)
            if bundle["case_id"] != case_id or manifest["case_id"] != case_id:
                raise ValueError("Reviewer bundle case identity changed in transport")
            if bundle["case_manifest_sha256"] != canonical_sha256(manifest):
                raise ValueError("Source manifest changed after evaluator bundle")
            if bundle["documents"] != manifest["documents"] or not bundle["documents"]:
                raise ValueError("Documents differ between evaluator and manifest")
            if bundle["source_bundle_sha256"] != trusted_delivery_receipt.get("source_bundle_sha256"):
                raise ValueError("Package source bundle differs from separately trusted receipt")
            orig = matches[0]["original_attachment_sha256"]
            if sorted(doc["sha256"] for doc in manifest["documents"]) != sorted(orig):
                raise ValueError("Original EIS binary SHAs do not match immutable blind lock")
            if len(orig) != trusted_delivery_receipt.get("original_count"):
                raise ValueError("Packaged source document count differs from trusted lock")
            if blanks != human_label_input_template(bundle):
                raise ValueError("Package contains nonblank or modified reviewer answers")
            worksheet = archive.read("review/independent-reviewer-worksheet.md")
            if worksheet != build_source_only_assignment(bundle).encode("utf8"):
                raise ValueError("Reviewer worksheet was replaced with untrusted content")
            raw_source_names = []
            for doc in manifest["documents"]:
                path = _safe_relative_source(doc["path"])
                name = "sources/" + path.as_posix()
                raw_source_names.append(name)
            expected = fixed | set(raw_source_names)
            if len(raw_source_names) != len(set(raw_source_names)) or set(names) != expected:
                raise ValueError("Extra, missing or colliding source-only ZIP files")
            if (
                proof.get("purpose") != _PURPOSE
                or proof.get("case_id") != case_id
                or proof.get("source_bundle_sha256") != bundle["source_bundle_sha256"]
                or proof.get("original_count") != len(raw_source_names)
                or proof.get("requires_independent_human_gold_before_sut") is not True
            ):
                raise ValueError("Source-only handoff integrity receipt has wrong intent")
            sha_ledger = proof.get("entries_sha256")
            if not isinstance(sha_ledger, dict) or set(sha_ledger) != set(names) - {"handoff-integrity.json"}:
                raise ValueError("Embedded integrity ledger does not cover all exact source-only entries")
            for name in sorted(sha_ledger):
                if hashlib.sha256(archive.read(name)).hexdigest() != sha_ledger[name]:
                    raise ValueError("ZIP member SHA changed since source-only packaging")
            for doc, name in zip(manifest["documents"], raw_source_names):
                if hashlib.sha256(archive.read(name)).hexdigest() != doc["sha256"]:
                    raise ValueError("Original EIS source byte SHA differs from frozen manifest")
    except (BadZipFile, EOFError, UnicodeError, KeyError, TypeError) as exc:
        raise ValueError("Damaged or invalid source-only reviewer archive") from exc
    return {
        "case_id": case_id,
        "archive_sha256": digest,
        "original_count": len(orig),
        "verification_status": "OFFLINE_BINARY_AND_IMMUTABLE_LOCK_SHA_VERIFIED",
        "human_gold_signed": 0,
        "sut_run_authorized": False,
        "independent_expert_qualification_verified": False,
    }
