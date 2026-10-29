"""Fail-fast preflight for the Tender Agent MI research writer on internal APFS.

Reports immutable source capture, backup hash, actual live DB counts, and
write/read/rename/scan health. This does NOT mutate PostgreSQL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from scripts.market_intelligence.append_pq_delta_20261029 import (
    ROOT,
    snapshot,
    verified_backup,
)
from scripts.market_intelligence.pq_corpus_kpis import collect

BACKUPS = Path("/Users/master/ArvectumSafe/backups/data-platform")
INTERNAL = Path("/Users/master/ArvectumSafe")


def probe_directory(path: Path) -> dict:
    path = path.resolve(strict=True)
    if INTERNAL not in path.parents:
        raise ValueError(f"Writer path must reside on trusted internal APFS: {path}")
    # Listability matters: external USB-APFS returned EINTR while stat worked.
    list(path.iterdir())
    with tempfile.NamedTemporaryFile(dir=path, prefix=".mi-probe-", delete=False) as fh:
        file = Path(fh.name)
        try:
            body = os.urandom(128)
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        except BaseException:
            file.unlink(missing_ok=True)
            raise
    renamed = file.with_name(file.name + ".ok")
    try:
        os.replace(file, renamed)
        if renamed.read_bytes() != body:
            raise RuntimeError("APFS write/read/rename mismatch")
    finally:
        renamed.unlink(missing_ok=True)
        file.unlink(missing_ok=True)
    return {"path": str(path), "scandir": "ok", "fsync_rename_readback": "ok"}


def newest_verified_backup(root: Path) -> dict:
    manifests = sorted(root.glob("data-platform-arvectum_data-*.dump.manifest.json"))
    if not manifests:
        raise RuntimeError("No verified backup on stable internal APFS")
    manifest = manifests[-1]
    obj = verified_backup(manifest)
    if not obj.get("pg_restore_list_verified"):
        raise RuntimeError("Backup lacks pg_restore archive format check")
    return {"manifest": str(manifest), "sha256": obj["sha256"], "bytes": obj["bytes"]}


def newest_capture(root: Path) -> dict:
    manifests = sorted(root.glob("captures/*/*.bin.json"),
                       key=lambda p: p.stat().st_mtime)
    if not manifests:
        raise RuntimeError("No immutable first-party source capture")
    receipt_file = manifests[-1]
    receipt = json.loads(receipt_file.read_text(encoding="utf8"))
    file = root / receipt["relative_file"]
    if (file.is_symlink() or not file.is_file()
            or file.stat().st_size != receipt["bytes"]):
        raise RuntimeError("Source receipt path/size mismatch")
    sha = hashlib.sha256()
    with file.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(data)
    if sha.hexdigest() != receipt["sha256"] or receipt["database_mutated"] is not False:
        raise RuntimeError("Source source-of-truth content/receipt drift")
    return {"receipt": str(receipt_file), "sha256": sha.hexdigest(),
            "bytes": receipt["bytes"]}


def verify(repo: Path, runtime: Path = ROOT, backups: Path = BACKUPS) -> dict:
    repo = repo.resolve(strict=True)
    if INTERNAL not in repo.parents:
        raise ValueError("Research Git repo must be on internal APFS")
    git = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        capture_output=True, text=True, timeout=15, check=True,
    )
    if git.stdout.strip():
        raise RuntimeError("Git tree dirty; reconcile before scheduled research writes")
    sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=12, check=True,
    ).stdout.strip()
    runtime_status = probe_directory(runtime)
    backup_status = probe_directory(backups)
    current = snapshot()
    if current["owner"] != "tender-agent" or current["rows"] != current["unique"]:
        raise RuntimeError("PQ PostgreSQL collection owner or unique identity drift")
    kpis = collect()["counts"]
    if kpis["unique_lots"] != current["rows"]:
        raise RuntimeError("DB KPI disagrees with direct independent snapshot")
    return {
        "schema_version": "pq-live-internal-apfs-acceptance/1",
        "verified_at_utc": datetime.now(UTC).isoformat(),
        "status": "pass",
        "git_head": sha,
        "repo": str(repo),
        "runtime": runtime_status,
        "backup_storage": backup_status,
        "backup": newest_verified_backup(backups),
        "original_capture": newest_capture(runtime),
        "postgresql": {
            "database": kpis["database"],
            "unique_lots": kpis["unique_lots"],
            "distinct_procedures": kpis["distinct_procedure_tokens"],
            "eis_223_notices": kpis["eis_223_notices"],
            "research_not_market_population": kpis[
                "rows_marked_research_not_market_population"
            ],
        },
        "postgresql_mutated_by_preflight": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument("--runtime", type=Path, default=ROOT)
    p.add_argument("--backups", type=Path, default=BACKUPS)
    args = p.parse_args()
    print(json.dumps(verify(args.repo, args.runtime, args.backups),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
