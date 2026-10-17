"""Portable offline original-source-only human reviewer handoff.

No agent output, human gold, signing keys or prefilled legal conclusions may
enter an archive. Packaging preserves original byte identity but does not
authenticate human qualifications or authorize SUT analysis.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from src.modules.benchmark_pipeline.contract import (
    canonical_sha256,
    validate_case_manifest_consistency,
    verify_manifest_source_files,
)
from src.modules.benchmark_pipeline.workflow import assert_blind_evaluator_bundle

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ALLOWED_METADATA = (
    "case_manifest.json",
    "evaluator_bundle.json",
    "independent-reviewer-worksheet.md",
    "human-labels-BLANK-template.json",
)
_ZIP_UNCOMPRESSED_LIMIT = 100_000_000


def _safe_relative_source(path: str) -> PurePosixPath:
    if not isinstance(path, str) or "\\" in path:
        raise ValueError("Source archive path must be portable and relative")
    p = PurePosixPath(path)
    if p.is_absolute() or not p.parts or any(part in {"..", ".", ""} for part in p.parts):
        raise ValueError("Unsafe original source path in reviewer handoff")
    if p.parts[0] in {"review", "handoff-integrity.json"}:
        raise ValueError("Original path collides with reserved archive metadata")
    return p


def _add_exact_file(z: ZipFile, name: str, content: bytes) -> None:
    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_STORED
    info.external_attr = 0o600 << 16
    z.writestr(info, content)


def write_source_only_reviewer_package(
    *, reviewer_bundle_dir: Path,
    original_source_root: Path,
    private_output: Path,
) -> dict:
    """Validate all binary source bytes; atomically write and re-read a private ZIP."""
    if private_output.exists() or private_output.with_suffix(".partial").exists():
        raise ValueError("Reviewer handoff cannot overwrite existing archives")
    bundle_file = reviewer_bundle_dir / "evaluator_bundle.json"
    manifest_file = reviewer_bundle_dir / "case_manifest.json"
    bundle = json.loads(bundle_file.read_text(encoding="utf8"))
    manifest = json.loads(manifest_file.read_text(encoding="utf8"))
    assert_blind_evaluator_bundle(bundle)
    validate_case_manifest_consistency(manifest)
    if bundle["case_manifest_sha256"] != canonical_sha256(manifest):
        raise ValueError("Reviewer bundle no longer matches frozen case manifest")
    if bundle["case_id"] != manifest["case_id"]:
        raise ValueError("Reviewer case identity mismatch")
    if bundle["documents"] != manifest["documents"] or not bundle["documents"]:
        raise ValueError("Reviewer docs do not match original manifest")
    verify_manifest_source_files(manifest, original_source_root)
    blanks = json.loads((reviewer_bundle_dir / _ALLOWED_METADATA[3]).read_text("utf8"))
    if (
        blanks.get("draft_status") != "TEMPLATE_ONLY_NOT_HUMAN_GOLD"
        or blanks.get("sut_inference_allowed") is not False
        or blanks.get("case_id") != bundle["case_id"]
        or blanks.get("blind_discovery_label", {}).get("label") is not None
        or blanks.get("blind_document_truth", {}).get("facts") != []
        or blanks.get("external_human_reviewer_attestation", {}).get("ed25519_signature_b64") is not None
    ):
        raise ValueError("Handoff may contain only unsigned, blank reviewer templates")
    entries: dict[str, bytes] = {}
    for name in _ALLOWED_METADATA:
        item = reviewer_bundle_dir / name
        if item.is_symlink() or not item.is_file():
            raise ValueError("Reviewer source-only metadata missing or symlinked")
        entries["review/" + name] = item.read_bytes()
    original_count = 0
    root = original_source_root.resolve()
    for item in bundle["documents"]:
        rel = _safe_relative_source(item["path"])
        source = root.joinpath(*rel.parts)
        if source.is_symlink():
            raise ValueError("Source original may not be symlinked")
        if not source.resolve().is_relative_to(root) or not source.is_file():
            raise ValueError("Source original escapes verified source root")
        raw = source.read_bytes()
        if len(raw) == 0 or hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("Original source byte receipt mismatch")
        entry_name = "sources/" + rel.as_posix()
        if entry_name in entries:
            raise ValueError("Duplicate source entry in reviewer pack")
        entries[entry_name] = raw
        original_count += 1
    if sum(len(payload) for payload in entries.values()) > _ZIP_UNCOMPRESSED_LIMIT:
        raise ValueError("Reviewer package source bytes exceed bounded size")
    payload_manifest = {
        "case_id": bundle["case_id"],
        "source_bundle_sha256": bundle["source_bundle_sha256"],
        "purpose": "INDEPENDENT_HUMAN_BLIND_REVIEW_ONLY_NO_MODEL_GOLD",
        "original_count": original_count,
        "entries_sha256": {
            name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(entries.items())
        },
        "requires_independent_human_gold_before_sut": True,
    }
    entries["handoff-integrity.json"] = (
        json.dumps(payload_manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf8")
    private_output.parent.mkdir(parents=True, exist_ok=True)
    partial = private_output.with_suffix(".partial")
    try:
        with ZipFile(partial, "w", allowZip64=False) as archive:
            for name, payload in sorted(entries.items()):
                _add_exact_file(archive, name, payload)
        with ZipFile(partial, "r") as archive:
            if set(archive.namelist()) != set(entries):
                raise ValueError("Archive file membership changed")
            if any(archive.read(name) != payload for name, payload in entries.items()):
                raise ValueError("Offline reviewer package verification failed")
        partial.rename(private_output)
    finally:
        partial.unlink(missing_ok=True)
    digest = hashlib.sha256(private_output.read_bytes()).hexdigest()
    assert _SHA.fullmatch(digest)
    return {
        "case_id": bundle["case_id"],
        "archive_sha256": digest,
        "source_bundle_sha256": bundle["source_bundle_sha256"],
        "original_count": original_count,
        "private_package_bytes": private_output.stat().st_size,
        "signed_expert_gold_count": 0,
        "sut_run_authorized": False,
    }
