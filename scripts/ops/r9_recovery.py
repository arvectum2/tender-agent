"""R9 quiesced PostgreSQL plus filesystem backup and restore tooling."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from uuid import uuid4

from sqlalchemy import create_engine, text

FORMAT_VERSION = "r9-recovery-v1"
BACKUP_FILES = {"database.dump", "filesystem.tar", "manifest.json"}
BACKUP_ID_PATTERN = re.compile(r"^r9-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$")
MANIFEST_KEYS = {
    "format_version",
    "backup_id",
    "created_at",
    "quiesced",
    "exact_file_set",
    "database_sha256",
    "filesystem_sha256",
    "database_tenants",
    "filesystem_tenants",
    "tenant_scope",
}


class RecoveryError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pg_connection(database_url: str) -> tuple[str, dict[str, str]]:
    parsed = urlsplit(database_url)
    scheme = parsed.scheme.split("+", 1)[0]
    if scheme not in {"postgresql", "postgres"}:
        raise RecoveryError("PostgreSQL database URL is required")
    if not parsed.hostname or not parsed.path:
        raise RecoveryError("PostgreSQL database URL is incomplete")
    user = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    auth = f"{quote(user, safe='')}@" if user else ""
    port = f":{parsed.port}" if parsed.port else ""
    safe_url = urlunsplit(
        ("postgresql", f"{auth}{host}{port}", parsed.path, parsed.query, "")
    )
    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password
    return safe_url, env


def _fsync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _validate_data_tree(data_dir: Path) -> None:
    if not data_dir.exists() or not data_dir.is_dir() or data_dir.is_symlink():
        raise RecoveryError("Data directory must be an existing real directory")
    for item in data_dir.rglob("*"):
        if item.is_symlink():
            raise RecoveryError("Symlinks are not allowed in recovery data")
        if not item.is_dir() and not item.is_file():
            raise RecoveryError("Unsupported filesystem object in recovery data")


def _filesystem_tenants(data_dir: Path) -> list[str]:
    root = data_dir / "customer-pilot"
    if not root.exists():
        return []
    if not root.is_dir() or root.is_symlink():
        raise RecoveryError("Customer-pilot root is unsafe")
    return sorted(
        item.name for item in root.iterdir() if item.is_dir() and not item.is_symlink()
    )


def _database_tenants(database_url: str) -> list[str]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text("SELECT customer_id FROM customer_profiles ORDER BY customer_id")
            )
            return [str(row[0]) for row in rows]
    finally:
        engine.dispose()


def _database_is_empty(database_url: str) -> bool:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            count = connection.execute(
                text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema NOT IN ('pg_catalog','information_schema')"
                )
            ).scalar_one()
            return int(count) == 0
    finally:
        engine.dispose()


def _run(command: list[str], env: dict[str, str]) -> None:
    result = subprocess.run(
        command, env=env, text=True, capture_output=True, check=False
    )
    if result.returncode:
        executable = Path(command[0]).name if command else "recovery tool"
        diagnostic = (result.stderr or "").strip().splitlines()
        # pg_restore output should be actionable without echoing a DSN/password.
        redacted = []
        for line in diagnostic[-5:]:
            for part in command:
                if "://" in part:
                    line = line.replace(part, "<redacted-dsn>")
            redacted.append(line[:350])
        detail = "; ".join(redacted)
        raise RecoveryError(
            f"{executable} failed with exit code {result.returncode}"
            + (f": {detail}" if detail else "")
        )


def _valid_hash(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _valid_tenants(value: object) -> bool:
    return bool(
        isinstance(value, list)
        and all(isinstance(item, str) and item for item in value)
        and value == sorted(set(value))
    )


def create_backup(
    *,
    database_url: str,
    data_dir: Path,
    output_dir: Path,
    quiesced: bool,
) -> Path:
    if not quiesced:
        raise RecoveryError("Backup requires an explicitly quiesced application")
    if data_dir.is_symlink():
        raise RecoveryError("Data directory must be an existing real directory")
    if output_dir.is_symlink():
        raise RecoveryError("Backup output directory is invalid")
    data_dir = data_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    _validate_data_tree(data_dir)
    backup_id = (
        f"r9-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    )
    partial = output_dir / f".{backup_id}.partial"
    final = output_dir / backup_id
    if partial.exists() or final.exists():
        raise RecoveryError("Backup destination already exists")
    partial.mkdir(mode=0o700)
    try:
        database_dump = partial / "database.dump"
        filesystem_tar = partial / "filesystem.tar"
        pg_url, pg_env = _pg_connection(database_url)
        _run(
            [
                "pg_dump",
                "--format=custom",
                "--no-owner",
                "--no-privileges",
                "--file",
                str(database_dump),
                pg_url,
            ],
            pg_env,
        )
        with tarfile.open(filesystem_tar, "w") as archive:
            archive.add(data_dir, arcname="data", recursive=True)
        database_tenants = _database_tenants(database_url)
        filesystem_tenants = _filesystem_tenants(data_dir)
        manifest = {
            "format_version": FORMAT_VERSION,
            "backup_id": backup_id,
            "created_at": datetime.now(UTC).isoformat(),
            "quiesced": True,
            "exact_file_set": sorted(BACKUP_FILES),
            "database_sha256": sha256(database_dump),
            "filesystem_sha256": sha256(filesystem_tar),
            "database_tenants": database_tenants,
            "filesystem_tenants": filesystem_tenants,
            "tenant_scope": sorted(
                set(database_tenants) | set(filesystem_tenants)
            ),
        }
        (partial / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n"
        )
        for path in partial.iterdir():
            _fsync_file(path)
        _fsync_dir(partial)
        os.replace(partial, final)
        _fsync_dir(output_dir)
        return final
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        raise


def verify_backup(backup_dir: Path) -> dict[str, Any]:
    if backup_dir.is_symlink():
        raise RecoveryError("Backup directory is invalid")
    backup_dir = backup_dir.resolve()
    if not backup_dir.is_dir():
        raise RecoveryError("Backup directory is invalid")
    try:
        children = list(backup_dir.iterdir())
    except OSError as exc:
        raise RecoveryError("Backup directory is unreadable") from exc
    if any(path.is_symlink() or not path.is_file() for path in children):
        raise RecoveryError("Backup file set is invalid")
    names = {path.name for path in children}
    if names != BACKUP_FILES:
        raise RecoveryError("Backup file set is invalid")
    try:
        manifest = json.loads((backup_dir / "manifest.json").read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecoveryError("Backup manifest is invalid") from exc
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_KEYS:
        raise RecoveryError("Backup manifest schema is invalid")
    if (
        manifest.get("format_version") != FORMAT_VERSION
        or manifest.get("quiesced") is not True
        or manifest.get("exact_file_set") != sorted(BACKUP_FILES)
        or not isinstance(manifest.get("backup_id"), str)
        or not BACKUP_ID_PATTERN.fullmatch(manifest["backup_id"])
        or not _valid_hash(manifest.get("database_sha256"))
        or not _valid_hash(manifest.get("filesystem_sha256"))
        or not _valid_tenants(manifest.get("database_tenants"))
        or not _valid_tenants(manifest.get("filesystem_tenants"))
        or not _valid_tenants(manifest.get("tenant_scope"))
    ):
        raise RecoveryError("Backup manifest policy is invalid")
    try:
        created_at = datetime.fromisoformat(manifest["created_at"])
    except (TypeError, ValueError) as exc:
        raise RecoveryError("Backup manifest timestamp is invalid") from exc
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise RecoveryError("Backup manifest timestamp is invalid")
    if sha256(backup_dir / "database.dump") != manifest["database_sha256"]:
        raise RecoveryError("Database dump checksum mismatch")
    if sha256(backup_dir / "filesystem.tar") != manifest["filesystem_sha256"]:
        raise RecoveryError("Filesystem archive checksum mismatch")
    if manifest["tenant_scope"] != sorted(
        set(manifest["database_tenants"]) | set(manifest["filesystem_tenants"])
    ):
        raise RecoveryError("Backup tenant scope is invalid")
    return manifest


def _safe_extract(archive_path: Path, staging: Path) -> Path:
    staging.mkdir(mode=0o700, exist_ok=True)
    try:
        with tarfile.open(archive_path, "r") as archive:
            members = archive.getmembers()
            names: set[str] = set()
            for member in members:
                normalized_name = str(Path(member.name))
                if normalized_name in names:
                    raise RecoveryError("Duplicate archive member")
                names.add(normalized_name)
                if member.issym() or member.islnk() or member.isdev():
                    raise RecoveryError("Unsafe archive member")
                parts = Path(member.name).parts
                if (
                    not parts
                    or Path(member.name).is_absolute()
                    or parts[0] != "data"
                    or ".." in parts
                ):
                    raise RecoveryError("Archive path escapes data root")
                destination = (staging / member.name).resolve()
                if (
                    staging.resolve() not in destination.parents
                    and destination != staging.resolve()
                ):
                    raise RecoveryError("Archive path escapes staging root")
            archive.extractall(staging)
    except RecoveryError:
        raise
    except (OSError, tarfile.TarError) as exc:
        raise RecoveryError("Filesystem archive is invalid") from exc
    restored = staging / "data"
    _validate_data_tree(restored)
    return restored


def restore_database(*, database_url: str, database_dump: Path) -> None:
    if not _database_is_empty(database_url):
        raise RecoveryError("Restore target database is not empty")
    pg_url, pg_env = _pg_connection(database_url)
    _run(
        [
            "pg_restore",
            "--single-transaction",
            "--exit-on-error",
            "--no-owner",
            "--no-privileges",
            "--dbname",
            pg_url,
            str(database_dump),
        ],
        pg_env,
    )


def restore_filesystem(*, filesystem_tar: Path, data_dir: Path) -> None:
    if data_dir.is_symlink():
        raise RecoveryError("Restore target data directory is not empty")
    data_dir = data_dir.resolve()
    if data_dir.exists() and (not data_dir.is_dir() or any(data_dir.iterdir())):
        raise RecoveryError("Restore target data directory is not empty")
    parent = data_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{data_dir.name}.restore.", dir=parent)
    )
    try:
        restored = _safe_extract(filesystem_tar, staging)
        if data_dir.exists():
            data_dir.rmdir()
        os.replace(restored, data_dir)
        _fsync_dir(parent)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def restore_backup(
    *,
    database_url: str,
    data_dir: Path,
    backup_dir: Path,
    expected_tenants: set[str] | None,
    quiesced: bool,
) -> dict[str, Any]:
    if not quiesced:
        raise RecoveryError("Restore requires an explicitly quiesced application")
    if expected_tenants is None:
        raise RecoveryError("Expected tenant scope is required")
    manifest = verify_backup(backup_dir)
    if set(manifest["tenant_scope"]) != expected_tenants:
        raise RecoveryError("Backup tenant scope does not match restore target")
    if data_dir.is_symlink():
        raise RecoveryError("Restore target data directory is not empty")
    data_dir = data_dir.resolve()
    if data_dir.exists() and (not data_dir.is_dir() or any(data_dir.iterdir())):
        raise RecoveryError("Restore target data directory is not empty")
    if not _database_is_empty(database_url):
        raise RecoveryError("Restore target database is not empty")
    target_existed = data_dir.exists()
    parent = data_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{data_dir.name}.restore.", dir=parent)
    )
    try:
        restored = _safe_extract(backup_dir / "filesystem.tar", staging)
        if target_existed:
            data_dir.rmdir()
        try:
            os.replace(restored, data_dir)
            _fsync_dir(parent)
        except BaseException:
            if target_existed and not data_dir.exists():
                data_dir.mkdir()
                _fsync_dir(parent)
            raise
        try:
            restore_database(
                database_url=database_url,
                database_dump=backup_dir / "database.dump",
            )
        except BaseException:
            if data_dir.exists():
                shutil.rmtree(data_dir)
            if target_existed:
                data_dir.mkdir()
            _fsync_dir(parent)
            raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    receipt = {
        "status": "R9_RESTORE_COMPLETE",
        "backup_id": manifest["backup_id"],
        "tenant_scope": manifest["tenant_scope"],
        "database_restored": True,
        "filesystem_restored": True,
        "restored_at": datetime.now(UTC).isoformat(),
    }
    receipt_path = parent / f".r9-restore-{manifest['backup_id']}.json"
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    _fsync_file(receipt_path)
    _fsync_dir(parent)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    backup = sub.add_parser("backup")
    backup.add_argument("--database-url", required=True)
    backup.add_argument("--data-dir", type=Path, required=True)
    backup.add_argument("--output-dir", type=Path, required=True)
    backup.add_argument("--quiesced", action="store_true")
    verify = sub.add_parser("verify")
    verify.add_argument("--backup-dir", type=Path, required=True)
    restore = sub.add_parser("restore")
    restore.add_argument("--database-url", required=True)
    restore.add_argument("--data-dir", type=Path, required=True)
    restore.add_argument("--backup-dir", type=Path, required=True)
    restore.add_argument("--expected-tenants", default=None)
    restore.add_argument("--quiesced", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "backup":
            result: Any = str(
                create_backup(
                    database_url=args.database_url,
                    data_dir=args.data_dir,
                    output_dir=args.output_dir,
                    quiesced=args.quiesced,
                )
            )
        elif args.command == "verify":
            result = verify_backup(args.backup_dir)
        else:
            expected = None
            if args.expected_tenants is not None:
                expected = {
                    item.strip()
                    for item in args.expected_tenants.split(",")
                    if item.strip()
                }
            result = restore_backup(
                database_url=args.database_url,
                data_dir=args.data_dir,
                backup_dir=args.backup_dir,
                expected_tenants=expected,
                quiesced=args.quiesced,
            )
        print(json.dumps({"ok": True, "result": result}, sort_keys=True))
        return 0
    except RecoveryError as exc:
        print(
            json.dumps({"ok": False, "error": str(exc)}, sort_keys=True),
            file=sys.stderr,
        )
        return 2
    except Exception:
        print(
            json.dumps({"ok": False, "error": "Recovery command failed"}, sort_keys=True),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
