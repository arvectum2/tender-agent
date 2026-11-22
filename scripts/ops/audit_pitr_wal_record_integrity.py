"""Offline PostgreSQL17 WAL record-CRC preflight, NOT seven-day PITR."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

SEGMENT_SIZE = 16 * 1024 * 1024
SEGMENT = re.compile(r"[0-9A-F]{24}\Z")
PARTIAL = re.compile(r"[0-9A-F]{24}\.partial\Z")
IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
BASE_DIR = re.compile(r"base-(\d{8}T\d{12}Z)\Z")


class WalIntegrityError(ValueError):
    """Never expose private WAL contents or paths in error messages."""


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WalIntegrityError("duplicate_receipt_fields")
        result[key] = value
    return result


def base_info(receipt: Path, system_id: str) -> tuple[datetime, str]:
    if (not receipt.is_absolute() or receipt.is_symlink() or not receipt.is_file()
            or not 0 < receipt.stat().st_size < 64000):
        raise WalIntegrityError("unsafe_backup_receipt")
    data = json.loads(receipt.read_bytes(), object_pairs_hook=_unique)
    original = receipt.parent / "data"
    m = BASE_DIR.fullmatch(receipt.parent.name)
    if not m or not original.is_dir() or original.is_symlink():
        raise WalIntegrityError("unverified_base_directory")
    if (data.get("status") != "pass"
            or data.get("source_system_identifier") != system_id
            or data.get("base_path") != str(original)
            or data.get("manifest_verified") != "backup successfully verified"
            or data.get("live_database_mutated") is not False
            or IMAGE_ID.fullmatch(str(data.get("image", ""))) is None):
        raise WalIntegrityError("backup_cluster_receipt_disagrees")
    start = datetime.strptime(m.group(1), "%Y%m%dT%H%M%S%fZ").replace(tzinfo=UTC)
    return start, data["image"]


def segment_order(name: str) -> tuple[int, int]:
    return int(name[:8], 16), int(name[8:16], 16) * 256 + int(name[16:24], 16)


def inspect_archive(folder: Path, system_id: str) -> dict:
    if (not folder.is_absolute() or folder.is_symlink() or not folder.is_dir()
            or folder.resolve() != folder or folder.name != f"wal-{system_id}"):
        raise WalIntegrityError("wrong_or_unsafe_wal_archive")
    full, partial = [], []
    for path in folder.iterdir():
        if path.is_symlink() or not path.is_file():
            raise WalIntegrityError("unsafe_archive_entry")
        if SEGMENT.fullmatch(path.name):
            if path.stat().st_size != SEGMENT_SIZE:
                raise WalIntegrityError("invalid_full_segment_size")
            full.append(path.name)
        elif PARTIAL.fullmatch(path.name):
            partial.append(path.name)
        else:
            raise WalIntegrityError("unknown_archive_entry")
    if not full or len(partial) > 1:
        raise WalIntegrityError("missing_full_segments_or_multiple_partials")
    full.sort()
    seq = [segment_order(name) for name in full]
    if len({t for t, _ in seq}) != 1:
        raise WalIntegrityError("mixed_timeline_segments")
    if any(b != a + 1 for (_, a), (_, b) in pairwise(seq)):
        raise WalIntegrityError("wal_filename_gap")
    if partial and segment_order(partial[0]) != (seq[-1][0], seq[-1][1] + 1):
        raise WalIntegrityError("unrelated_partial_segment")
    member_hash = hashlib.sha256(
        "".join(f"{name}:{SEGMENT_SIZE}\n" for name in full).encode()
    ).hexdigest()
    return {
        "full_segment_count": len(full),
        "full_bytes": len(full) * SEGMENT_SIZE,
        "first_full_segment": full[0],
        "last_full_segment": full[-1],
        "timeline_hex": full[0][:8],
        "contiguous_names_and_exact_lengths": True,
        "in_progress_partial_excluded": bool(partial),
        "membership_names_and_lengths_sha256": member_hash,
    }


def verify_pg17_records(folder: Path, image_id: str, first: str, last: str) -> None:
    """Use pinned local PG17 image, no network, no source write."""
    if (IMAGE_ID.fullmatch(image_id) is None
            or SEGMENT.fullmatch(first) is None
            or SEGMENT.fullmatch(last) is None):
        raise WalIntegrityError("decoder_identity_not_verified")
    args = [
        "docker", "run", "--rm", "--pull", "never",
        "--network", "none", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--mount", f"type=bind,src={folder},dst=/wal,readonly",
        image_id, "pg_waldump", "--quiet", "--path=/wal", first, last,
    ]
    try:
        result = subprocess.run(
            args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, check=False, timeout=1200,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WalIntegrityError("pg17_decoder_unavailable_or_timeout") from exc
    if result.returncode != 0:
        raise WalIntegrityError("pg17_wal_record_decode_failed")


def audit(
    receipt: Path, folder: Path, system_id: str, *,
    verify_records: bool = False, now: datetime | None = None,
) -> dict:
    if re.fullmatch(r"[0-9]{10,20}", system_id) is None:
        raise WalIntegrityError("invalid_system_identifier")
    base, image = base_info(receipt, system_id)
    info = inspect_archive(folder, system_id)
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise WalIntegrityError("timezone_naive_timestamp")
    now = now.astimezone(UTC)
    if now < base:
        raise WalIntegrityError("future_base_timestamp")
    if verify_records:
        verify_pg17_records(folder, image, info["first_full_segment"], info["last_full_segment"])
        after = inspect_archive(folder, system_id)
        if (after["first_full_segment"] != info["first_full_segment"]
                or after["full_segment_count"] < info["full_segment_count"]):
            raise WalIntegrityError("archived_history_removed_during_scan")
        info["archive_grew_during_scan"] = after["full_segment_count"] > info["full_segment_count"]
    else:
        info["archive_grew_during_scan"] = False
    return {
        "status": ("PASS_BOUNDED_WAL_RECORD_PREFLIGHT_NOT_SEVEN_DAY_PITR" if verify_records
                   else "PASS_FILENAME_SIZE_PREFLIGHT_NOT_RECORD_INTEGRITY"),
        "physical_system_identifier": system_id,
        "postgres_image_id": image,
        "verified_base_started_utc": base.isoformat(),
        "observed_at_utc": now.isoformat(),
        "base_age_days": round((now - base).total_seconds() / 86400, 5),
        "seven_day_base_age_condition": now - base >= timedelta(days=7),
        **info,
        "pg17_wal_record_decode_completed": verify_records,
        "source_wal_mount_readonly": verify_records,
        "decoder_network_disabled": verify_records,
        "seven_day_pitr_proven": False,
        "seven_day_historical_target_restored": False,
        "production_mutations": 0,
        "network_requests": 0,
    }


def write_private_once(path: Path, report: dict) -> None:
    if (not path.is_absolute() or path.is_symlink() or path.exists()
            or not path.parent.is_dir() or path.parent.is_symlink()):
        raise WalIntegrityError("unsafe_or_existing_private_proof")
    fd, tmp = tempfile.mkstemp(prefix=".ta-wal-pref-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(report, output, sort_keys=True, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.chmod(tmp, 0o600)
        os.link(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-receipt", required=True, type=Path)
    parser.add_argument("--wal-dir", required=True, type=Path)
    parser.add_argument("--expected-system-id", required=True)
    parser.add_argument("--verify-records", action="store_true")
    parser.add_argument("--private-proof-output", type=Path)
    args = parser.parse_args()
    try:
        report = audit(
            args.base_receipt, args.wal_dir, args.expected_system_id,
            verify_records=args.verify_records,
        )
        if args.private_proof_output:
            write_private_once(args.private_proof_output, report)
    except (WalIntegrityError, ValueError, TypeError, KeyError, OSError):
        print(json.dumps({"status": "BLOCKED_UNVERIFIED_WAL_INTEGRITY"}))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
