"""Verified full PostgreSQL backup to reliable APFS storage before MI DB changes.

Uses official pg_dump/pg_restore tools in the authorized data-platform container.
Only the existing arvectum_data database is allowed; never mutates the database.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DIR = Path("/Users/master/ArvectumSafe/backups/data-platform")
CONTAINER = "arvectum-postgres"
DATABASE = "arvectum_data"


def backup(output_dir: Path = DEFAULT_DIR) -> dict:
    output_dir = output_dir.expanduser()
    if output_dir.is_symlink():
        raise ValueError("Backup directory must not be a symlink")
    output_dir.mkdir(parents=True, exist_ok=True)
    base = output_dir.resolve(strict=True)
    # Reading the directory is an explicit readiness probe: external SSD on
    # macOS was mounted/writeable but scandir/getcwd returned EINTR.
    list(base.iterdir())
    lock = base / ".pq-postgres-backup.lock"
    if lock.is_symlink():
        raise ValueError("Unsafe backup lock path")
    with lock.open("a+b") as lock_fd:
        try:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another backup already running") from exc
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        name = f"data-platform-{DATABASE}-{stamp}-{os.getpid()}.dump"
        file = base / name
        tmp = base / f".{name}.partial"
        manifest = base / f"{name}.manifest.json"
        if file.exists() or tmp.exists() or manifest.exists():
            raise FileExistsError("Backup path already in use")
        try:
            os.chmod(base, 0o700)
            with tmp.open("xb") as stream:
                os.chmod(tmp, 0o600)
                cmd = [
                    "docker", "exec", CONTAINER, "sh", "-c",
                    'exec pg_dump -Fc -Z 6 -U "$POSTGRES_USER" '
                    '-d arvectum_data --no-owner --no-acl',
                ]
                result = subprocess.run(
                    cmd, stdout=stream, stderr=subprocess.PIPE,
                    timeout=70, check=False,
                )
                stream.flush()
                os.fsync(stream.fileno())
            if result.returncode:
                raise RuntimeError("pg_dump failed: " + result.stderr[-700:].decode(errors="replace"))
            size = tmp.stat().st_size
            if size < 100_000:
                raise RuntimeError("Full database dump implausibly small")
            sha = hashlib.sha256()
            with tmp.open("rb") as stream:
                for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                    sha.update(chunk)
            # Verify that PostgreSQL itself can parse the custom archive.
            with tmp.open("rb") as stream:
                check = subprocess.run(
                    ["docker", "exec", "-i", CONTAINER, "sh", "-c",
                     "exec pg_restore --list -"],
                    stdin=stream, capture_output=True, timeout=55, check=False,
                )
            if check.returncode or b"TABLE DATA" not in check.stdout:
                raise RuntimeError("pg_restore could not validate archive/table data")
            obj = {
                "schema_version": "arvectum-data-platform-full-backup/1",
                "database": DATABASE,
                "container": CONTAINER,
                "backup_file": file.name,
                "bytes": size,
                "sha256": sha.hexdigest(),
                "format": "pg_dump_custom",
                "pg_restore_list_verified": True,
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            os.replace(tmp, file)
            payload = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
            temp_manifest = base / f".{name}.manifest.partial"
            with temp_manifest.open("x", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_manifest, manifest)
            with os.open(base, os.O_RDONLY) as dir_fd:
                os.fsync(dir_fd)
            return {"manifest_path": str(manifest), **obj}
        finally:
            if tmp.exists():
                tmp.unlink()
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", type=Path, default=DEFAULT_DIR)
    args = p.parse_args()
    print(json.dumps(backup(args.output_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
