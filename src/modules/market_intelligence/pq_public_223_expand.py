"""Stage safe source-SHA-linked ZIP members from public EIS 223 document pages.

Uses existing hardened ZIP member extraction; maintains the weaker public-page
provenance tier (never mislabels files as SOAP-XML-bound originals).
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from .eis_zip_members import stage_official_zip_children


def _atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8",
                                     prefix=".publiczip-", delete=False) as f:
        t = Path(f.name)
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(t, path)


def expand(*, source_root: Path, output_root: Path,
           max_cases: int = 12, max_archives: int = 20) -> dict:
    if (not 1 <= max_cases <= 30 or not 1 <= max_archives <= 60
            or source_root.is_symlink() or output_root.is_symlink()
            or not source_root.is_dir()):
        raise ValueError("Invalid source or extraction scope")
    manifest = {"schema_version": "pq-public-eis-zip-members/1",
                "source_level": "verified_public_eis_page_not_original_soap_xml",
                "records": [], "errors": []}
    unique = set()
    cases = 0
    archives = 0
    for case in sorted(source_root.iterdir()):
        if cases >= max_cases or archives >= max_archives:
            break
        if not case.is_dir() or case.is_symlink() or not re.fullmatch(r"[0-9]{11}", case.name):
            continue
        receipt_file = case / "public-page-receipt.json"
        if not receipt_file.is_file() or receipt_file.is_symlink():
            continue
        receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
        if (receipt.get("schema_version") != "pq-223-public-page-download/1"
                or receipt.get("registry_number") != case.name):
            continue
        cases += 1
        for file in receipt.get("files", []):
            if archives >= max_archives:
                break
            filename = file.get("filename")
            expected_sha = file.get("sha256")
            if (not isinstance(filename, str) or Path(filename).name != filename
                    or not filename.lower().endswith(".zip")
                    or not isinstance(expected_sha, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", expected_sha)):
                continue
            archive = case / filename
            archives += 1
            try:
                extracted = stage_official_zip_children(
                    archive, expected_parent_sha256=expected_sha,
                    target_dir=output_root / case.name,
                    max_members=100, max_total_bytes=80 * 1024 * 1024)
                for child in extracted["records"]:
                    child_sha = child.get("member_sha256")
                    if child_sha and (case.name, child_sha) in unique:
                        continue
                    if child_sha:
                        unique.add((case.name, child_sha))
                    manifest["records"].append({
                        "registry_number": case.name,
                        "source_page_sha256": receipt.get("public_page_sha256"),
                        "source_archive_sha256": expected_sha,
                        "source_archive_filename": filename,
                        "member_original_path_sha256": child["original_member_path_sha256"],
                        "member_sha256": child_sha,
                        "stored_name": child.get("local_stored_name"),
                        "member_extension": child["member_extension"],
                        "status": child["status"],
                        "original_xml_binding_verified": False,
                    })
            except (ValueError, OSError, RuntimeError) as exc:
                manifest["errors"].append({"registry_number": case.name,
                                          "archive_sha256": expected_sha,
                                          "error_type": type(exc).__name__})
    _atomic(output_root / "public-members-manifest.json", manifest)
    return {"cases_checked": cases, "archives_checked": archives,
            "members_indexed": len(manifest["records"]),
            "members_staged": sum(x["status"] == "staged_sha256_verified_not_yet_indexed"
                                  for x in manifest["records"]),
            "errors": len(manifest["errors"])}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(expand(source_root=args.source_root, output_root=args.output_root),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
