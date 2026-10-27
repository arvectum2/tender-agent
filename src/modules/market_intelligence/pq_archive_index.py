"""Build an exact-number index of SHA-verified EIS XML archives.

Indexes only procurement numbers explicitly present in XML. No fuzzy matches,
no guessed filestore IDs, and no award inference. Designed for bounded reuse
by the recovery runner instead of repeatedly scanning every ZIP.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .eis_coverage import SUBSYSTEM_DOCUMENTS
from .eis_source_ledger import _first, _local, _text

MAX_MEMBERS = 10000
MAX_XML_BYTES = 8 * 1024 * 1024


def index(root: Path, *, max_archives: int = 200) -> dict:
    if not 1 <= max_archives <= 2000:
        raise ValueError("Invalid archive budget")
    base = root / "RI223" / SUBSYSTEM_DOCUMENTS["RI223"]
    matches: dict[str, list[dict]] = {}
    inspected = 0
    failures = []
    for receipt_path in sorted(base.glob("*/region-*.json")) if base.is_dir() else []:
        if inspected >= max_archives:
            break
        if receipt_path.is_symlink():
            continue
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            failures.append({"receipt": str(receipt_path), "reason": "unreadable_receipt"})
            continue
        day = receipt_path.parent.name
        region = receipt_path.stem.removeprefix("region-")
        for entry in receipt.get("archives", []):
            if inspected >= max_archives:
                break
            archive = (receipt_path.parent / f"region-{region}" /
                       f"archive-{int(entry['index']):03d}" / "documentation-archive.zip")
            if not archive.is_file() or archive.is_symlink():
                continue
            inspected += 1
            try:
                expected = entry["archive_sha256"]
                if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
                    raise ValueError("archive_sha_mismatch")
                with zipfile.ZipFile(archive) as z:
                    infos = z.infolist()
                    if len(infos) > MAX_MEMBERS:
                        raise ValueError("member_budget_exceeded")
                    for info in infos:
                        if not info.filename.endswith(".xml") or info.file_size > MAX_XML_BYTES:
                            continue
                        node = ET.fromstring(z.read(info))
                        kind = _local(node.tag)
                        data = _first(node, f"body/item/{kind}Data")
                        if data is None:
                            continue
                        number = (_text(data, "registrationNumber") if kind.startswith("purchaseNotice")
                                  else _text(data, "purchaseInfo/purchaseNoticeNumber"))
                        if not number or not re.fullmatch(r"[0-9]{11}", number):
                            continue
                        row = {"archive": str(archive), "sha256": expected,
                               "region": region, "date": day, "xml_member": info.filename,
                               "xml_sha256": hashlib.sha256(z.read(info)).hexdigest(),
                               "kind": kind}
                        if row not in matches.setdefault(number, []):
                            matches[number].append(row)
            except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError, KeyError) as exc:
                failures.append({"archive": str(archive), "reason": type(exc).__name__})
    return {"schema_version": "pq-official-archive-index/1",
            "archives_inspected": inspected, "procurements_indexed": len(matches),
            "records": matches, "failures": failures}


def save(payload: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent,
                                     prefix=".index-", delete=False) as f:
        tmp = Path(f.name)
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, output)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-archives", type=int, default=200)
    a = p.parse_args()
    result = index(a.root, max_archives=a.max_archives)
    save(result, a.output)
    print(json.dumps({"archives_inspected": result["archives_inspected"],
                      "procurements_indexed": result["procurements_indexed"],
                      "failures": len(result["failures"])}))


if __name__ == "__main__":
    main()
