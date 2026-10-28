"""Bounded SHA-bound extraction of original public EIS 7z attachments.

Only regular PDF/Office files are emitted, under digest filenames. Archive
member paths never become output paths. No source originals are modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import select
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

MAX_ARCHIVE = 5 * 1024 * 1024
MAX_MEMBER = 4 * 1024 * 1024
MAX_TOTAL = 25 * 1024 * 1024
MAX_FILES = 32
EXTENSIONS = {".pdf", ".doc", ".docx", ".xlsx"}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _checked_entries(listing: str) -> list[dict]:
    if "\n----------\n" not in listing:
        raise ValueError("Missing 7z member listing")
    entries = []
    for block in listing.split("\n----------\n", 1)[1].strip().split("\n\n"):
        item = dict(line.split(" = ", 1) for line in block.splitlines() if " = " in line)
        if item:
            entries.append(item)
    if not entries or len(entries) > MAX_FILES:
        raise ValueError("7z member count outside limit")
    total = 0
    for entry in entries:
        name = entry.get("Path", "")
        if (not name or name in {".", ".."} or "/" in name or "\\" in name
                or ":" in name or name.startswith(".")
                or Path(name).suffix.lower() not in EXTENSIONS):
            raise ValueError("Unsafe 7z member path/type")
        if entry.get("Encrypted") != "-" or entry.get("Attributes") != "A":
            raise ValueError("Encrypted, linked or non-file 7z member")
        try:
            size = int(entry["Size"])
        except (ValueError, KeyError) as exc:
            raise ValueError("Missing 7z member size") from exc
        if size < 1 or size > MAX_MEMBER:
            raise ValueError("7z member size outside limit")
        total += size
        if total > MAX_TOTAL:
            raise ValueError("7z expanded size outside limit")
        entry["declared_size"] = size
    return entries


def _member_bytes(executable: str, archive: Path, name: str, size_limit: int) -> bytes:
    proc = subprocess.Popen([executable, "e", "-so", str(archive), name],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    chunks = []
    count = 0
    deadline = time.monotonic() + 15
    try:
        assert proc.stdout is not None
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError("7z extraction timeout")
            ready, _, _ = select.select([proc.stdout], [], [], min(remaining, 0.5))
            if not ready:
                continue
            part = os.read(proc.stdout.fileno(), 65536)
            if not part:
                break
            count += len(part)
            if count > size_limit or count > MAX_MEMBER:
                raise ValueError("7z exceeded declared size")
            chunks.append(part)
        if proc.wait(timeout=2) != 0 or count != size_limit:
            raise ValueError("7z failed or size mismatch")
        return b"".join(chunks)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2)
        if proc.stdout is not None:
            proc.stdout.close()


def _valid_signature(data: bytes, suffix: str) -> bool:
    if suffix == ".pdf":
        return data.startswith(b"%PDF-")
    if suffix in {".docx", ".xlsx"}:
        return data.startswith(b"PK\x03\x04")
    if suffix == ".doc":
        return data.startswith(bytes.fromhex("d0cf11e0a1b11ae1"))
    return False


def stage_case(source_dir: Path, output_root: Path, *, executable: str = "7z") -> dict:
    if (not re.fullmatch(r"\d{11}", source_dir.name)
            or source_dir.is_symlink() or output_root.is_symlink()
            or not source_dir.is_dir()):
        raise ValueError("Unsafe source/output path")
    receipt = json.loads((source_dir / "public-page-receipt.json").read_text())
    if receipt.get("registry_number") != source_dir.name:
        raise ValueError("Mismatched notice receipt")
    files = receipt.get("files", [])
    if len(files) > MAX_FILES:
        raise ValueError("Too many source archives")
    if shutil.which(executable) is None:
        raise ValueError("7z binary unavailable")
    case_output = output_root / source_dir.name
    staged, refused = [], []
    for item in files:
        if item.get("observed_file_format") != "opaque_7z":
            continue
        filename = item.get("filename", "")
        if not filename or Path(filename).name != filename or not filename.endswith(".7z"):
            refused.append({"filename": filename, "reason": "unsafe_filename"})
            continue
        archive = source_dir / filename
        try:
            if archive.is_symlink() or archive.stat().st_size > MAX_ARCHIVE:
                raise ValueError("Unsafe archive path/size")
            data = archive.read_bytes()
            if _sha(data) != item["sha256"] or not data.startswith(b"7z\xbc\xaf\x27\x1c"):
                raise ValueError("Original archive SHA/signature mismatch")
            listed = subprocess.run([executable, "l", "-slt", str(archive)],
                                    capture_output=True, timeout=10, check=True)
            if len(listed.stdout) > 512 * 1024:
                raise ValueError("Oversized 7z listing")
            entries = _checked_entries(listed.stdout.decode("utf-8"))
            for entry in entries:
                name = entry["Path"]
                content = _member_bytes(executable, archive, name, entry["declared_size"])
                suffix = Path(name).suffix.lower()
                if not _valid_signature(content, suffix):
                    raise ValueError("Member signature mismatch")
                digest = _sha(content)
                destination = case_output / (digest + suffix)
                case_output.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    if destination.is_symlink() or _sha(destination.read_bytes()) != digest:
                        raise ValueError("Existing child SHA mismatch")
                else:
                    with tempfile.NamedTemporaryFile(dir=case_output, delete=False) as tmp:
                        tmp.write(content)
                        tmp.flush()
                        os.fsync(tmp.fileno())
                        temporary = tmp.name
                    os.replace(temporary, destination)
                staged.append({"archive_sha256": item["sha256"], "member": name,
                               "sha256": digest, "filename": destination.name,
                               "size_bytes": len(content),
                               "source_url_sha256": item.get("source_url_sha256")})
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            refused.append({"filename": filename, "reason": str(exc)[:180]})
    manifest = {"schema_version": "pq-verified-7z/1", "registry_number": source_dir.name,
                "source_tier": receipt.get("source_level"),
                "public_page_sha256": receipt.get("public_page_sha256"),
                "staged": staged, "refused": refused}
    if staged:
        case_output.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=case_output,
                                         delete=False) as tmp:
            json.dump(manifest, tmp, ensure_ascii=False, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
            temporary = tmp.name
        os.replace(temporary, case_output / "verified-7z-manifest.json")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    result = stage_case(args.source_dir, args.output_root)
    print(json.dumps({"registry_number": result["registry_number"],
                      "staged": len(result["staged"]), "refused": result["refused"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
