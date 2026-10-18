"""Offline owner-local capture of one external ChatGPT procurement research note.

Only one EXISTING canonical PostgreSQL 'arvectum' DB, explicit apply. All text
and originals remain owner-private on ArvectumSSD, not copied into the learning
table. Public source URL != original attestation; a verified source requires
a separately available immutable local source file with matching SHA256.

This command is intended to be called after *each* externally executed tender
analysis by an authorized agent; it does not subscribe to arbitrary chats.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import stat
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from scripts.procurement_llm.import_candidates import _engine_url
from src.modules.procurement_learning_corpus.models import (
    ProcurementLearningObservation,
)
from src.modules.procurement_learning_corpus.service import (
    append_candidate,
    make_manual_candidate,
    validate_candidate,
)

OWNER_PRIVATE = Path("/Volumes/ArvectumSSD/Arvectum/private/tender-agent")
SCHEMA = "external_chatgpt_procurement_research_v1"
_ALLOWED_PLATFORM = {"eis", "workspace", "b2bcenter", "other_public"}
_ALLOWED_SOURCE_STATUS = {"ORIGINAL_SHA_VERIFIED", "PUBLIC_URL_UNVERIFIED"}
_HEX = re.compile(r"[a-f0-9]{64}\Z")
_REF = re.compile(r"[a-zA-Z0-9:._-]{5,120}\Z")
_BASENAME = re.compile(r"[a-zA-Z0-9_.-]{1,128}\Z")
_FILE_MAX_BYTES = 8 * 1024 * 1024
_MANIFEST_MAX_BYTES = 24 * 1024


class ExternalCaptureError(ValueError):
    """Reject anything not demonstrably within the owner-only provenance scope."""


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _private_file(path: object, *, root: Path, max_bytes: int) -> tuple[str, bytes]:
    if not isinstance(path, str):
        raise ExternalCaptureError("missing owner-private artifact")
    p = Path(path)
    if (not p.is_absolute() or p.is_symlink() or not p.is_file()
            or not _BASENAME.fullmatch(p.name)):
        raise ExternalCaptureError("missing/unsafe owner-private file")
    if (root.is_symlink() or not root.is_dir() or root.resolve() not in p.resolve().parents):
        raise ExternalCaptureError("artifact outside the owner-only storage")
    if stat.S_IMODE(p.stat().st_mode) & 0o077:
        raise ExternalCaptureError("artifact owner-only permissions must be 0600")
    # Reject symlinked ancestors between root and file, not just the file.
    current = p.parent
    while current != root:
        if current.is_symlink():
            raise ExternalCaptureError("owner file parent must not be symlink")
        current = current.parent
        if current == current.parent:
            raise ExternalCaptureError("owner-private ancestor not found")
    size = p.stat().st_size
    if not 0 < size <= max_bytes:
        raise ExternalCaptureError("missing or oversized private artifact")
    raw = p.read_bytes()
    if len(raw) != size:
        raise ExternalCaptureError("mutable artifact during read")
    return str(p), raw


def _original_public_url(value: object, platform: str, ref: str) -> tuple[str, str]:
    if not isinstance(value, str) or len(value) > 1500:
        raise ExternalCaptureError("invalid public source URL")
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ExternalCaptureError("invalid source URL port") from exc
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or not host or not host.isascii() or len(host) > 253
            or port not in (None, 443) or parsed.fragment):
        raise ExternalCaptureError("untrusted or private source URL")
    host = host.lower()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ExternalCaptureError("IP origin source refused")
    if (not re.fullmatch(r"[a-z0-9.-]+", host) or "." not in host
            or host.endswith((".local", ".internal", ".invalid", ".test"))
            or ".." in host):
        raise ExternalCaptureError("private or invalid source domain")
    if platform == "eis":
        if host != "zakupki.gov.ru" and not host.endswith(".zakupki.gov.ru"):
            raise ExternalCaptureError("EIS provider must use official domain")
        if not re.fullmatch(r"\d{19}", ref):
            raise ExternalCaptureError("official notice requires 19-digit number")
        query = parse_qsl(parsed.query, keep_blank_values=True)
        if query and query != [("regNumber", ref)]:
            raise ExternalCaptureError("only public exact regNumber is permitted")
    else:
        if parsed.query:
            raise ExternalCaptureError("non-EIS source query may contain private data")
        if platform == "workspace" and (
            host != "workspace.ru"
            or not re.search(
                r"/tenders/[a-z0-9-]+-" + re.escape(ref) + r"/$", parsed.path
            )
        ):
            raise ExternalCaptureError("different Workspace source identity")
        if platform == "b2bcenter" and (
            host != "www.b2b-center.ru"
            or not re.search(r"/tender-" + re.escape(ref) + r"/$", parsed.path)
        ):
            raise ExternalCaptureError("different B2B Center source identity")
    return host, sha(value.encode("utf8"))


def build_candidate(manifest: dict, *, private_root: Path | None = None) -> dict:
    if private_root is None:
        private_root = OWNER_PRIVATE
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema", "procurement_ref", "source_platform", "original_source_url",
        "original_source_status", "original_source_path", "original_source_sha256",
        "analysis_artifact_path", "analyst", "model_label", "observed_at_utc",
        "standalone_sanitized_analysis",
    }:
        raise ExternalCaptureError("strict source research manifest required")
    if manifest["schema"] != SCHEMA or manifest["analyst"] != "chatgpt":
        raise ExternalCaptureError("wrong bounded ChatGPT provenance contract")
    platform = manifest["source_platform"]
    if platform not in _ALLOWED_PLATFORM:
        raise ExternalCaptureError("unrecognized original platform")
    ref = manifest["procurement_ref"]
    if not isinstance(ref, str) or not _REF.fullmatch(ref):
        raise ExternalCaptureError("invalid procurement reference")
    if platform in {"workspace", "b2bcenter"}:
        prefix = platform + ":"
        if not ref.startswith(prefix):
            raise ExternalCaptureError("missing platform-scoped original ref")
        original_ref = ref[len(prefix):]
        if not original_ref.isdigit():
            raise ExternalCaptureError("wrong platform notice number")
    else:
        original_ref = ref
    host, source_url_sha = _original_public_url(
        manifest["original_source_url"], platform, original_ref
    )
    try:
        timestamp = datetime.fromisoformat(manifest["observed_at_utc"])
    except (TypeError, ValueError) as exc:
        raise ExternalCaptureError("malformed observed timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ExternalCaptureError("observation time must have a UTC offset")
    label = manifest["model_label"]
    if not isinstance(label, str) or not 2 <= len(label) <= 120:
        raise ExternalCaptureError("missing actual reviewer model label")
    if manifest["standalone_sanitized_analysis"] is not True:
        raise ExternalCaptureError("raw unreviewed conversation transcript not allowed")
    artifact_path, analysis_raw = _private_file(
        manifest["analysis_artifact_path"], root=private_root,
        max_bytes=250_000
    )
    if Path(artifact_path).suffix not in {".md", ".txt"}:
        raise ExternalCaptureError("analysis must be standalone Markdown/text")
    try:
        analysis_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExternalCaptureError("analysis artifact must be UTF-8") from exc
    analysis_sha = sha(analysis_raw)
    status = manifest["original_source_status"]
    if status not in _ALLOWED_SOURCE_STATUS:
        raise ExternalCaptureError("unknown original source evidence status")
    source_sha = manifest["original_source_sha256"]
    original_path = manifest["original_source_path"]
    if status == "ORIGINAL_SHA_VERIFIED":
        if not isinstance(source_sha, str) or not _HEX.fullmatch(source_sha):
            raise ExternalCaptureError("SHA-bound original proof required")
        if not original_path:
            raise ExternalCaptureError("original source must exist locally")
        _, raw_original = _private_file(
            original_path, root=private_root, max_bytes=_FILE_MAX_BYTES
        )
        if sha(raw_original) != source_sha:
            raise ExternalCaptureError("source file does not match claimed SHA")
        gate = "PRIVATE_ORIGINAL_BYTES_SHA_ATTESTED_NOT_LEGAL_GOLD"
        review_state = "source_documented"
    else:
        if source_sha is not None or original_path is not None:
            raise ExternalCaptureError("cannot claim partial original proof")
        gate = "PUBLIC_URL_ONLY_ORIGINAL_NOT_VERIFIED"
        review_state = "unverified_chat_recall"
    identity = sha(
        (ref + ":" + source_url_sha + ":" + (source_sha or "UNVERIFIED") +
         ":" + analysis_sha).encode()
    )
    event = {
        "event_id": "ta-chatgpt-research:" + identity[:40],
        "procurement_ref": ref,
        "participation": "reviewed_only",
        "review_state": review_state,
        "source_role": "development_exposed",
        "event_type": "external_chatgpt_tender_analysis",
        "analyst": "chatgpt",
        "model_label": label,
        "analysis_artifact_private_path": artifact_path,
        "analysis_artifact_sha256": analysis_sha,
        "source_platform": platform,
        "source_host": host,
        "original_source_url_sha256": source_url_sha,
        "original_source_bytes_sha256": source_sha,
        "original_verification_gate": gate,
        "observed_at_utc": timestamp.isoformat(),
        "source_payload_is_metadata_only": True,
        "raw_chat_transcript_copied": False,
        "analysis_raw_text_copied": False,
        "human_verified_interpretation": False,
        "owner_bid_go": False,
        "training_labels": "NOT_REVIEWED",
        "blind_holdout": False,
    }
    candidate = make_manual_candidate(event)
    validate_candidate(candidate)
    return candidate


def _manifest_file(path: Path, *, root: Path) -> dict:
    _, raw = _private_file(str(path), root=root, max_bytes=_MANIFEST_MAX_BYTES)
    def unique(pairs):
        mapping = {}
        for key, val in pairs:
            if key in mapping:
                raise ExternalCaptureError("duplicate manifest key")
            mapping[key] = val
        return mapping
    result = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(result, dict):
        raise ExternalCaptureError("manifest must be JSON object")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-database", choices=["arvectum"])
    args = parser.parse_args()
    if args.apply and args.confirm_database != "arvectum":
        parser.error("live import requires explicit --confirm-database arvectum")
    candidate = build_candidate(_manifest_file(args.manifest, root=OWNER_PRIVATE))
    if not args.apply:
        print(json.dumps({
            "mode": "dry_run",
            "candidate_count": 1,
            "observation_sha256": candidate["observation_id"],
            "training_status": "candidate_unreviewed",
            "database_mutations": 0,
        }))
        return 0
    engine = create_engine(_engine_url(), future=True)
    try:
        if not inspect(engine).has_table(ProcurementLearningObservation.__tablename__):
            raise RuntimeError("Canonical migration 107 missing. Refusing write.")
        with Session(engine) as session, session.begin():
            inserted = append_candidate(session, candidate)
        print(json.dumps({
            "mode": "canonical_applied",
            "target": "arvectum.procurement_learning_observations",
            "inserted": 1 if inserted else 0,
            "existing": 0 if inserted else 1,
            "training_promotions": 0,
        }))
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
