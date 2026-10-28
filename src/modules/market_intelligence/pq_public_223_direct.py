"""Augment canonical EIS public evidence with receipt-SHA-verified direct attachments.

ZIP members and direct attachment bytes share one content-addressed manifest.
No invented XML binding, no unverified supplier/award inference.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

ALLOWED = frozenset({".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt"})


def merge_direct(*, source_root: Path, canonical: Path,
                 max_cases: int = 80, max_files: int = 500) -> dict:
    if (source_root.is_symlink() or canonical.is_symlink()
            or not source_root.is_dir()
            or not 1 <= max_cases <= 100 or not 1 <= max_files <= 500):
        raise ValueError("Invalid public EIS receipt staging scope")
    eligible = [
        p for p in source_root.iterdir()
        if p.is_dir() and not p.is_symlink()
        and re.fullmatch(r"[0-9]{11}", p.name)
        and (p / "public-page-receipt.json").is_file()
    ]
    if len(eligible) > max_cases:
        raise ValueError("Source-case budget would truncate direct EIS evidence")
    maximum_direct = 0
    for case in eligible:
        receipt = json.loads((case / "public-page-receipt.json").read_text(encoding="utf-8"))
        maximum_direct += sum(
            Path(str(x.get("filename") or "")).suffix.lower() in ALLOWED
            for x in receipt.get("files", []))
    if maximum_direct > max_files:
        raise ValueError("File budget would truncate original direct EIS receipts")
    manifest_file = canonical / "canonical-manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "pq-public-canonical/1":
        raise ValueError("Unexpected canonical source manifest")
    seen = {(r["registry_number"], r["member_sha256"]) for r in manifest["records"]}
    added = 0
    skipped = 0
    checked = 0
    errors = []
    for folder in sorted(source_root.iterdir()):
        if checked >= max_cases or added >= max_files:
            break
        if not folder.is_dir() or folder.is_symlink() or not re.fullmatch(r"[0-9]{11}", folder.name):
            continue
        receipt_file = folder / "public-page-receipt.json"
        if not receipt_file.is_file() or receipt_file.is_symlink():
            continue
        checked += 1
        receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
        if (receipt.get("schema_version") != "pq-223-public-page-download/1"
                or receipt.get("registry_number") != folder.name):
            errors.append({"registry_number": folder.name, "status": "receipt_mismatch"})
            continue
        for doc in receipt.get("files", [])[:100]:
            if added >= max_files:
                break
            filename = doc.get("filename")
            sha = doc.get("sha256")
            if (not isinstance(filename, str) or Path(filename).name != filename
                    or not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{64}", sha)):
                errors.append({"registry_number": folder.name, "status": "invalid_receipt_entry"})
                continue
            ext = Path(filename).suffix.lower()
            if ext not in ALLOWED:
                skipped += 1
                continue
            if (folder.name, sha) in seen:
                skipped += 1
                continue
            source = folder / filename
            if (source.is_symlink() or not source.is_file()
                    or source.stat().st_size > 50_000_000
                    or hashlib.sha256(source.read_bytes()).hexdigest() != sha):
                errors.append({"registry_number": folder.name, "status": "source_sha_mismatch"})
                continue
            directory = canonical / folder.name
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / (sha + ext)
            if target.is_symlink():
                raise ValueError("Symlinked canonical document")
            if target.exists():
                if hashlib.sha256(target.read_bytes()).hexdigest() != sha:
                    raise ValueError("Canonical member collision")
            else:
                with tempfile.NamedTemporaryFile(dir=directory, prefix=".direct-",
                                                 delete=False) as stream:
                    temp = Path(stream.name)
                    with source.open("rb") as input_stream:
                        for block in iter(lambda: input_stream.read(1024 * 1024), b""):
                            stream.write(block)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp, target)
            manifest["records"].append({
                "registry_number": folder.name,
                "member_sha256": sha,
                "canonical_stored_name": target.name,
                "source_page_sha256": receipt.get("public_page_sha256"),
                "source_archive_sha256": None,
                "source_kind": "public_eis_direct_attachment",
                "original_xml_binding_verified": False,
            })
            seen.add((folder.name, sha))
            added += 1
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=canonical,
                                     prefix=".direct-manifest-", delete=False) as stream:
        temp = Path(stream.name)
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, manifest_file)
    return {"cases_checked": checked, "direct_files_added": added,
            "same_sha_skipped_or_unsupported": skipped,
            "source_count": len(manifest["records"]),
            "errors": errors}
