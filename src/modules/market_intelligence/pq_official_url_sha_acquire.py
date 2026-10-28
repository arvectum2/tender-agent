"""Recover exact official EIS filestore documents with supplied original SHA-256.

Only explicit official URLs already present in the verified 101-case research
corpus are admitted. No guessed EIS UIDs, no winner/contract inference, and
no unverified downloaded bytes are promoted into canonical sources.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from src.modules.tender_operator_agent_demo.attachment_downloader import (
    download_procurement_attachments,
)
from src.modules.tender_operator_agent_demo.procurement_schemas import ProcurementAttachment
from .eis_attachment_manifest import _public_filestore_digest

EXTENSION = re.compile(r"_(DOCX|DOC|PDF|XLSX|XLS)_sha256_verified", re.IGNORECASE)
SHA = re.compile(r"[0-9a-f]{64}")


def _atomic(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     prefix=".official-", delete=False) as f:
        tmp = Path(f.name)
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def extract_links(case: dict) -> list[dict]:
    number = str(case.get("procedure_id") or "")
    if not re.fullmatch(r"\d{11}", number):
        return []
    links = []
    seen = set()
    for e in case.get("evidence") or []:
        url = e.get("url")
        expected = e.get("sha256")
        tier = e.get("source_tier") or ""
        extension = EXTENSION.search(str(tier))
        digest = _public_filestore_digest(url)
        if (not digest or not extension or not isinstance(expected, str)
                or not SHA.fullmatch(expected) or (digest, expected) in seen):
            continue
        seen.add((digest, expected))
        links.append({"number": number, "url": url,
                      "url_sha256": digest, "sha256": expected,
                      "extension": "." + extension.group(1).lower(),
                      "source_tier": "official_eis_filestore_exact_source_sha"})
    return links


def acquire(*, case: dict, root: Path, download=download_procurement_attachments,
            transport=None, max_files: int = 6) -> dict:
    if not 1 <= max_files <= 12 or root.is_symlink():
        raise ValueError("Invalid attachment budget/root")
    source = extract_links(case)
    number = str(case.get("procedure_id") or "")
    if not source:
        return {"registry_number": number, "status": "no_exact_primary_filestore_sha_links",
                "files_verified": 0}
    directory = root / number
    receipt_file = directory / "official-sha-receipt.json"
    if directory.is_symlink() or receipt_file.is_symlink():
        raise ValueError("Unsafe official original folder")
    if receipt_file.exists():
        previous = json.loads(receipt_file.read_text(encoding="utf-8"))
        if previous.get("registry_number") != number:
            raise ValueError("Existing official SHA receipt mismatched identity")
        for row in previous.get("verified", []):
            doc = directory / row["stored_name"]
            if doc.is_symlink() or not doc.is_file() or hashlib.sha256(doc.read_bytes()).hexdigest() != row["sha256"]:
                raise ValueError("Previously saved official original changed")
        return {"registry_number": number, "status": "existing_receipt",
                "files_verified": len(previous.get("verified", []))}
    directory.mkdir(parents=True, exist_ok=True)
    selected = source[:max_files]
    attachments = [
        ProcurementAttachment(
            attachment_id=x["url_sha256"], name=f"original-{x['sha256'][:18]}{x['extension']}",
            url=x["url"], can_download=True,
            provenance={"source_regime": "223fz",
                        "source_tier": "explicit_original_eis_url_and_exact_sha256",
                        "expected_source_sha256": x["sha256"],
                        "source_url_sha256": x["url_sha256"]},
        )
        for x in selected
    ]
    records = []
    rejected = []
    with tempfile.TemporaryDirectory(prefix=".official-eis-", dir=directory) as folder:
        staging = Path(folder)
        response = download(
            attachments, target_dir=staging, max_attachments=max_files,
            max_file_size_bytes=15 * 1024 * 1024,
            max_total_size_bytes=max_files * 15 * 1024 * 1024,
            allowed_domains={"zakupki.gov.ru"}, transport=transport,
        )
        for saved in response.saved:
            expected = next((x for x in selected
                             if x["url_sha256"] == hashlib.sha256(
                                 (saved.source_url or "").encode("utf-8")).hexdigest()
                             and x["sha256"] == saved.sha256), None)
            if expected is None:
                rejected.append({"status": "sha256_mismatch",
                                 "downloaded_sha256": saved.sha256})
                continue
            original = staging / str(saved.stored_name)
            target_name = expected["sha256"] + expected["extension"]
            target = directory / target_name
            if target.is_symlink() or not original.is_file():
                raise ValueError("Unsafe downloaded original")
            if hashlib.sha256(original.read_bytes()).hexdigest() != expected["sha256"]:
                raise ValueError("Downloaded original payload changed")
            if target.exists():
                if hashlib.sha256(target.read_bytes()).hexdigest() != expected["sha256"]:
                    raise ValueError("Existing official source SHA collision")
            else:
                os.replace(original, target)
                target.chmod(0o600)
            records.append({
                "stored_name": target_name, "sha256": expected["sha256"],
                "source_url_sha256": expected["url_sha256"],
                "source_tier": expected["source_tier"],
                "size_bytes": target.stat().st_size,
            })
        rejected.extend({"status": x.error or "download_unavailable"}
                        for x in response.skipped[:max_files])
    receipt = {
        "schema_version": "pq-official-filestore-sha-receipt/1",
        "registry_number": number,
        "status": "verified_originals" if records else "no_verified_originals",
        "verified": records,
        "rejected": rejected,
        "source_links_from_corpus": len(source),
        "selected_source_links": len(selected),
        "signed_contract_verified": False,
        "winner_verified": False,
    }
    _atomic(receipt_file, receipt)
    return {"registry_number": number, "status": receipt["status"],
            "files_verified": len(records), "rejected_count": len(rejected)}


def batch(*, leads: Path, root: Path, journal: Path, max_cases: int = 4,
          download=download_procurement_attachments, transport=None) -> dict:
    if not 1 <= max_cases <= 20:
        raise ValueError("Invalid EIS exact-source case budget")
    leads_data = json.loads(leads.read_text(encoding="utf-8"))["records"]
    journal_data = json.loads(journal.read_text(encoding="utf-8")) if journal.is_file() else {
        "schema_version": "pq-official-filestore-sha-attempts/1", "attempts": []}
    already = {x["registry_number"] for x in journal_data["attempts"]
               if x.get("status") in ("verified_originals", "existing_receipt")}
    new = []
    for case in leads_data:
        if len(new) >= max_cases:
            break
        number = str(case.get("procedure_id") or "")
        if number in already or not extract_links(case):
            continue
        try:
            result = acquire(case=case, root=root, download=download,
                             transport=transport)
        except (OSError, ValueError, RuntimeError, urllib.error.URLError) as exc:
            result = {"registry_number": number, "status": "source_error",
                      "error_type": type(exc).__name__, "files_verified": 0}
        new.append(result)
        journal_data["attempts"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(), **result,
        })
        _atomic(journal, journal_data)
        already.add(number)
    return {"cases_attempted": len(new),
            "original_files_sha_verified": sum(x["files_verified"] for x in new),
            "results": new}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--leads", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--journal", type=Path, required=True)
    p.add_argument("--max-cases", type=int, default=4)
    args = p.parse_args()
    print(json.dumps(batch(leads=args.leads, root=args.root,
                           journal=args.journal, max_cases=args.max_cases),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
