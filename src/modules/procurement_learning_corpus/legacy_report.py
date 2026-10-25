"""Build immutable *unlinked* metadata-only candidates for original legacy reports.

The full MD remains on the existing ArvectumSSD filesystem; no model/run IDs,
human labels, submitted claims, or copied full text are generated.
"""
from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path

from src.modules.procurement_learning_corpus.service import digest, validate_candidate

CANONICAL_REPORT_ROOT = Path("/Volumes/ArvectumSSD/Arvectum/data/rag/reports")
_REPORT = re.compile(r"analyze_tender_(\d{19})_(\d{8}T\d{12}Z)_[a-f0-9]{8}\.md\Z")
_SHA256 = re.compile(r"[a-f0-9]{64}\Z")
_MAX_REPORT_BYTES = 20 * 1024 * 1024


def make_unlinked_legacy_report_candidate(
    path: Path, *, expected_sha256: str, reports_root: Path = CANONICAL_REPORT_ROOT
) -> dict:
    """Refuse unverified paths/content; never read or store report text in metadata."""
    if not _SHA256.fullmatch(expected_sha256):
        raise ValueError("Expected a 64-digit SHA256 receipt")
    if reports_root.is_symlink() or not reports_root.is_dir():
        raise ValueError("A real existing canonical report root is required")
    if not path.is_file() or path.is_symlink():
        raise ValueError("Report source missing or symlinked")
    if path.parent.resolve(strict=True) != reports_root.resolve(strict=True):
        raise ValueError("Legacy report must reside directly in the existing report root")
    m = _REPORT.fullmatch(path.name)
    if not m:
        raise ValueError("Unsupported historical report basename")
    size = path.stat().st_size
    if not 0 < size <= _MAX_REPORT_BYTES:
        raise ValueError("Invalid original report size")
    h = sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    actual = h.hexdigest()
    if actual != expected_sha256:
        raise ValueError("Report SHA256 does not match independent source receipt")

    reg = m.group(1)
    payload = {
        "registry_number": reg,
        "report_path": str(path.resolve(strict=True)),
        "report_file_name": path.name,
        "report_sha256": actual,
        "report_bytes": size,
        "historical_saved_run_id": None,
        "historical_run_identity_verified": False,
        "source_role": "development_exposed",
        "source_receipt": "sha256_original_legacy_report",
        "original_full_report_copied_to_db": False,
        "training_label_approved": False,
        "participation_evidence": None,
    }
    row = {
        "observation_id": digest({"kind": "legacy_report_artifact", "ref": reg, "sha256": actual}),
        "event_kind": "legacy_report_artifact",
        "procurement_ref": reg,
        "source_ref": "canonical_legacy_report:" + path.name,
        "provenance_sha256": digest(payload),
        "participation": "unknown",
        "review_state": "system_recorded",
        "training_status": "candidate_unreviewed",
        "candidate_split": "development_exposed",
        "visibility_scope": "owner_internal",
        "customer_id": None,
        "payload_json": payload,
    }
    validate_candidate(row)
    return row
