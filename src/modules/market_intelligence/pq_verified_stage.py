"""Stage only SHA-verified official EIS originals for Data Platform / ARC review."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

EXT = {".pdf", ".docx", ".xlsx", ".doc", ".xls", ".txt"}
ID = re.compile(r"[0-9]{11}|[0-9]{19,20}")


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stage(*, source_root: Path, output_root: Path,
          max_cases: int = 30, max_files: int = 300,
          max_bytes: int = 32 * 1024 * 1024) -> dict:
    if not 1 <= max_cases <= 100 or not 1 <= max_files <= 1000:
        raise ValueError("Invalid staging budget")
    if source_root.is_symlink() or not source_root.is_dir() or output_root.is_symlink():
        raise ValueError("Invalid source/destination")
    report = {"schema_version": "pq-verified-originals/1",
              "source_root": str(source_root), "records": [],
              "skipped": [], "errors": []}
    output_root.mkdir(parents=True, exist_ok=True)
    cases = 0
    for folder in sorted(source_root.iterdir()):
        if cases >= max_cases or len(report["records"]) >= max_files:
            break
        if not folder.is_dir() or folder.is_symlink() or not ID.fullmatch(folder.name):
            continue
        receipt = folder / "download_receipt.json"
        if not receipt.is_file() or receipt.is_symlink():
            continue
        cases += 1
        try:
            original = json.loads(receipt.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            report["errors"].append({"case": folder.name, "reason": "invalid_receipt"})
            continue
        if original.get("registry_number") != folder.name or original.get("status") != "downloaded":
            report["errors"].append({"case": folder.name, "reason": "untrusted_receipt"})
            continue
        for row in original.get("records", []):
            if len(report["records"]) >= max_files:
                break
            name = row.get("stored_name")
            if row.get("status") != "saved" or not isinstance(name, str) or Path(name).name != name:
                continue
            src = folder / "source-bound-attachments" / name
            if src.suffix.lower() not in EXT:
                report["skipped"].append({"case": folder.name, "name": name, "reason": "unsupported_format"})
                continue
            if row.get("format_mismatch_requires_review"):
                report["skipped"].append({"case": folder.name, "name": name, "reason": "format_mismatch"})
                continue
            expected = row.get("document_sha256")
            if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
                report["errors"].append({"case": folder.name, "name": name, "reason": "missing_sha"})
                continue
            if not src.is_file() or src.is_symlink() or src.stat().st_size > max_bytes or _sha(src) != expected:
                report["errors"].append({"case": folder.name, "name": name, "reason": "source_sha_failed"})
                continue
            target = output_root / folder.name
            target.mkdir(exist_ok=True)
            dest = target / name
            if dest.exists():
                if dest.is_symlink() or _sha(dest) != expected:
                    report["errors"].append({"case": folder.name, "name": name, "reason": "staged_conflict"})
                    continue
            else:
                with tempfile.NamedTemporaryFile(dir=target, prefix=".source-", delete=False) as out:
                    tmp = Path(out.name)
                    with src.open("rb") as inp:
                        shutil.copyfileobj(inp, out, length=1024 * 1024)
                    out.flush()
                    os.fsync(out.fileno())
                if _sha(tmp) != expected:
                    tmp.unlink()
                    raise ValueError("Unexpected copy checksum")
                os.replace(tmp, dest)
            report["records"].append({"registry_number": folder.name, "stored_name": name,
                                      "sha256": expected, "source_receipt": str(receipt),
                                      "source_xml_sha256": row.get("source_xml_sha256"),
                                      "revision_requires_review": row.get("revision_requires_review")})
    manifest = output_root / "source-manifest.json"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output_root,
                                     prefix=".manifest-", delete=False) as f:
        tmp = Path(f.name)
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, manifest)
    return {"cases_checked": cases, "files_staged": len(report["records"]),
            "unsupported": len(report["skipped"]), "errors": len(report["errors"])}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(stage(source_root=args.source_root, output_root=args.output_root)))


if __name__ == "__main__": main()
