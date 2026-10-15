"""Verify real official ZIP and original bytes before preregistering unseen holdout.

The candidate receipt MUST originate from a source-acquisition stage BEFORE
any legal text, model prediction or expert label is seen. This script never
creates gold labels or returns semantic accuracy metrics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from scripts.acceptance.audit_r5_official_sources import audit_archive
from scripts.acceptance.build_r4_official_current_freshness import notice_attachments
from src.modules.tender_operator_agent_demo.r4_semantic_holdout import (
    forbid_reuse_of_prior_blind_cohorts,
    forbidden_development_sources,
    lock_unseen_real_cohort,
    verify_cohort_lock,
)

COMPETITIVE_TYPES = frozenset({
    "epNotificationEF2020", "epNotificationEOK2020", "epNotificationEZK2020",
})
SHA = re.compile(r"[0-9a-f]{64}\Z")


def _safe_file(root: Path, name: str) -> Path:
    candidate = Path(name)
    if candidate.is_absolute() or not candidate.parts or ".." in candidate.parts:
        raise ValueError("Original file must be a safe root-relative path")
    try:
        path = (root / candidate).resolve()
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("Original path escapes private source root") from exc
    if not path.is_file():
        raise ValueError("Original source binary not supplied")
    return path


def prepare_real_holdout(
    candidate_receipts: list[dict],
    *,
    source_root: Path,
    development_audit: dict,
    source_set_id: str,
    frozen_at_utc: str,
    prior_blind_locks: list[dict] | None = None,
) -> dict:
    if not candidate_receipts:
        raise ValueError("No previously unseen official cases available; do not invent a holdout")
    baseline = forbid_reuse_of_prior_blind_cohorts(
        forbidden_development_sources(development_audit),
        prior_blind_locks or [],
    )
    verified = []
    for candidate in candidate_receipts:
        number = candidate["registry_number"]
        if candidate.get("retrieval_provenance") != "OFFICIAL_GETDOCSIP_TLS_VERIFIED":
            raise ValueError("Source receipt is not independently attested official EIS")
        source_zip = _safe_file(source_root, candidate["official_archive_relpath"])
        audited = audit_archive(source_zip, number)
        if audited["highest"]["notice_type"] not in COMPETITIVE_TYPES:
            raise ValueError("Holdout must contain genuinely competitive 44-FZ notices")
        if audited["zip_sha256"] != candidate["official_zip_sha256"]:
            raise ValueError("Official ZIP SHA mismatch in candidate source receipt")
        if audited["highest"]["xml_sha256"] != candidate["official_xml_sha256"]:
            raise ValueError("Official XML SHA mismatch in candidate source receipt")
        original_docs = candidate["documents"]
        if not isinstance(original_docs, list) or not original_docs:
            raise ValueError("Holdout requires at least one original official attachment")
        inventory = notice_attachments(source_zip, number, audited["highest"]["version"])
        if not inventory or len(original_docs) != len(inventory):
            raise ValueError("Incomplete original attachment inventory; every official XML UID required")
        linked_uids = set()
        shas = []
        for document in original_docs:
            path = _safe_file(source_root, document["relative_path"])
            expected = document["sha256"]
            if not isinstance(expected, str) or SHA.fullmatch(expected) is None:
                raise ValueError("Candidate original document SHA absent or malformed")
            raw_bytes = path.read_bytes()
            if hashlib.sha256(raw_bytes).hexdigest() != expected:
                raise ValueError("Original attachment bytes not attested by source receipt")
            linked = [
                uid for uid, meta in inventory.items()
                if path.name == uid + Path(meta["fileName"]).suffix.lower()
                and int(meta["fileSize"]) == len(raw_bytes)
            ]
            if len(linked) != 1 or linked[0] in linked_uids:
                raise ValueError("Original attachment UID, filename or XML size mismatch")
            linked_uids.add(linked[0])
            shas.append(expected)
        if linked_uids != set(inventory):
            raise ValueError("Incomplete EIS original attachment UID coverage")
        verified.append({
            "registry_number": number,
            "attestation": "VERIFIED_OFFICIAL_GETDOCSIP_XML_AND_BINARY",
            "source_document_stage": "PRE_LABEL_PRE_SUT",
            "official_zip_sha256": audited["zip_sha256"],
            "official_xml_sha256": audited["highest"]["xml_sha256"],
            "binary_original_sha256": shas,
        })
    result = lock_unseen_real_cohort(
        verified, forbidden=baseline, source_set_id=source_set_id,
        locked_at_utc=frozen_at_utc,
    )
    verify_cohort_lock(result)
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--candidate-receipt", type=Path, required=True)
    p.add_argument("--development-audit", type=Path, required=True)
    p.add_argument("--source-set-id", required=True)
    p.add_argument(
        "--prior-holdout-lock", type=Path, action="append", required=True,
        help="Include every earlier immutable pilot holdout lock to prevent reuse",
    )
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    candidates = json.loads(args.candidate_receipt.read_text(encoding="utf8"))
    audit = json.loads(args.development_audit.read_text(encoding="utf8"))
    lock = prepare_real_holdout(
        candidates, source_root=args.source_root,
        development_audit=audit, source_set_id=args.source_set_id,
        frozen_at_utc=datetime.now(UTC).isoformat(timespec="seconds"),
        prior_blind_locks=[
            json.loads(path.read_text(encoding="utf8"))
            for path in args.prior_holdout_lock
        ],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", "utf8")
    print("REAL_HOLDOUT_LOCKED",lock["case_count"],lock["immutable_lock_sha256"])


if __name__ == "__main__":
    main()
