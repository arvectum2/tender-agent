"""Safely expand SHA-verified official EIS attachment ZIP members for MI reading.

Never extracts arbitrary paths, symlinks, executable files or unchecked archives.
Original source ZIP and its receipt remain immutable; member hashes are logged.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import stat
import tempfile
import zipfile
from pathlib import Path

ALLOWED = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt"}
NOTICE = re.compile(r"[0-9]{11}|[0-9]{19,20}")


def _digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(part)
    return sha.hexdigest()


def expand(*, source_root: Path, output_root: Path, max_cases: int = 20,
           max_files: int = 180, max_member_bytes: int = 20_000_000) -> dict:
    if (source_root.is_symlink() or output_root.is_symlink()
            or not source_root.is_dir() or not 1 <= max_cases <= 100
            or not 1 <= max_files <= 500 or not 1 <= max_member_bytes <= 30_000_000):
        raise ValueError("Invalid source or extraction budget")
    output_root.mkdir(parents=True, exist_ok=True)
    log = {"schema_version": "pq-verified-zip-members/1", "files": [], "errors": [],
           "skipped": 0}
    seen: set[tuple[str, str]] = set()
    cases = 0
    for folder in sorted(source_root.iterdir()):
        if cases >= max_cases or len(log["files"]) >= max_files:
            break
        if not folder.is_dir() or folder.is_symlink() or not NOTICE.fullmatch(folder.name):
            continue
        receipt_path = folder / "download_receipt.json"
        if not receipt_path.is_file() or receipt_path.is_symlink():
            continue
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if receipt["registry_number"] != folder.name or receipt["status"] != "downloaded":
                continue
        except (OSError, KeyError, ValueError):
            continue
        cases += 1
        for row in receipt.get("records", []):
            name = row.get("stored_name")
            if not name or Path(name).name != name or Path(name).suffix.lower() != ".zip":
                continue
            archive = folder / "source-bound-attachments" / name
            expected = row.get("document_sha256")
            if not archive.is_file() or archive.is_symlink() or not expected or _digest(archive) != expected:
                log["errors"].append({"case": folder.name, "name": name, "error": "source_zip_sha"})
                continue
            try:
                with zipfile.ZipFile(archive) as z:
                    members = z.infolist()
                    if len(members) > 200:
                        raise ValueError("Too many ZIP members")
                    for member in members:
                        if len(log["files"]) >= max_files:
                            break
                        ext = Path(member.filename).suffix.lower()
                        unix_mode = (member.external_attr >> 16) & 0xFFFF
                        if (member.is_dir() or ext not in ALLOWED or
                                (unix_mode and stat.S_ISLNK(unix_mode)) or
                                member.flag_bits & 1 or member.file_size > max_member_bytes or
                                member.file_size > 200 * max(member.compress_size, 1)):
                            log["skipped"] += 1
                            continue
                        raw = z.read(member)
                        if len(raw) > max_member_bytes:
                            raise ValueError("Expanded member exceeded limit")
                        sha = hashlib.sha256(raw).hexdigest()
                        if (folder.name, sha) in seen:
                            log["skipped"] += 1
                            continue
                        seen.add((folder.name, sha))
                        directory = output_root / folder.name
                        directory.mkdir(exist_ok=True)
                        stored = f"{expected[:10]}-{sha[:20]}{ext}"
                        target = directory / stored
                        if target.is_symlink() or (target.exists() and _digest(target) != sha):
                            raise ValueError("Output collision")
                        if not target.exists():
                            with tempfile.NamedTemporaryFile(dir=directory, prefix=".member-", delete=False) as out:
                                temp = Path(out.name)
                                out.write(raw)
                                out.flush()
                                os.fsync(out.fileno())
                            os.replace(temp, target)
                        log["files"].append({"registry_number": folder.name,
                            "source_zip_sha256": expected, "source_xml_sha256": row.get("source_xml_sha256"),
                            "member_name": member.filename, "member_sha256": sha,
                            "stored_name": stored, "bytes": len(raw)})
            except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
                log["errors"].append({"case": folder.name, "name": name, "error": type(exc).__name__})
    with tempfile.NamedTemporaryFile("w", dir=output_root, encoding="utf-8",
                                     prefix=".manifest-", delete=False) as f:
        temp = Path(f.name)
        json.dump(log, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, output_root / "source-manifest.json")
    return {"cases_checked": cases, "members_staged": len(log["files"]),
            "skipped": log["skipped"], "errors": len(log["errors"])}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--max-files", type=int, default=180)
    a = p.parse_args()
    print(json.dumps(expand(source_root=a.source_root, output_root=a.output_root,
                            max_files=a.max_files)))


if __name__ == "__main__": main()
