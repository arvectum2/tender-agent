"""Content-addressed unique Data Platform input from public EIS ZIP staging.

Retains SHA lineage while preventing duplicate ZIP revisions from inflating the
number of original documents extracted or analysed by ChatGPT.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path


def canonicalize(*, staged: Path, output: Path, max_files: int = 150) -> dict:
    if (staged.is_symlink() or not staged.is_dir() or output.is_symlink()
            or not 1 <= max_files <= 500):
        raise ValueError("Invalid canonical source scope")
    manifest_file = staged / "public-members-manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "pq-public-eis-zip-members/1":
        raise ValueError("Invalid public ZIP manifest")
    stageable = sum(
        child.get("status") == "staged_sha256_verified_not_yet_indexed"
        for child in manifest.get("records", []))
    if stageable > max_files:
        raise ValueError("Canonical file budget would truncate verified source manifests")
    records = []
    seen = set()
    for child in manifest["records"]:
        if len(records) >= max_files:
            break
        if child.get("status") != "staged_sha256_verified_not_yet_indexed":
            continue
        number = str(child.get("registry_number") or "")
        filename = child.get("stored_name")
        digest = child.get("member_sha256")
        if (not re.fullmatch(r"[0-9]{11}", number) or not filename
                or Path(filename).name != filename
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("Unsafe manifest source entry")
        key = (number, digest)
        if key in seen:
            continue
        seen.add(key)
        origin = staged / number / filename
        if origin.is_symlink() or not origin.is_file() or origin.stat().st_size > 50_000_000:
            raise ValueError("Missing verified staged member")
        actual = hashlib.sha256(origin.read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError("Staged source member checksum mismatch")
        destination = output / number
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / (digest + origin.suffix.lower())
        if target.is_symlink():
            raise ValueError("Unsafe canonical target")
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError("Canonical source collision")
        else:
            with tempfile.NamedTemporaryFile(dir=destination, prefix=".dedup-", delete=False) as f:
                temp = Path(f.name)
                with origin.open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        f.write(chunk)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, target)
        records.append({
            "registry_number": number, "member_sha256": digest,
            "source_page_sha256": child.get("source_page_sha256"),
            "source_archive_sha256": child.get("source_archive_sha256"),
            "canonical_stored_name": target.name,
            "original_xml_binding_verified": False,
        })
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=output, encoding="utf-8",
                                     prefix=".canonical-", delete=False) as f:
        temp = Path(f.name)
        json.dump({"schema_version": "pq-public-canonical/1",
                   "source_level": "verified_public_page_no_soap_xml",
                   "records": records}, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, output / "canonical-manifest.json")
    return {"unique_files": len(records), "original_xml_binding_verified": False}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--staged", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(canonicalize(staged=a.staged, output=a.output),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
