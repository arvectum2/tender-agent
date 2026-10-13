"""Fail-closed offline reconciliation of archived APR06 EIS notices and attachments.

Matches downloaded documents to *archived notice* by exact filename+size only.
EIS publishedContentId is NOT recorded with extracted filenames, so this is not
an independently verified official revision/UID binding or current EIS status.
No network, no bid activity, no original blobs in outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

_REG = re.compile(r"[0-9]{19}\Z")
_RUN = re.compile(r"toa-run-[0-9]{14}-[a-f0-9]{6}\Z")
_MAX_XML_BYTES = 8_000_000
_MAX_FILES_PER_CASE = 250


def _name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _child_text(element: ET.Element, tag: str) -> str | None:
    return next((x.text.strip() for x in element if _name(x) == tag and x.text), None)


def _nested_text(element: ET.Element, tag: str) -> str | None:
    return next((x.text.strip() for x in element.iter() if _name(x) == tag and x.text), None)


def _safe_input(root: Path, relative: str) -> Path:
    if not isinstance(relative, str):
        raise TypeError("Missing relative source path")
    p = Path(relative)
    if p.is_absolute() or ".." in p.parts or not p.parts or p.parts[0] == ".":
        raise ValueError("Unsafe source path")
    target = root / p
    if not target.is_file() or target.is_symlink():
        raise ValueError("Missing or symlinked saved source")
    cursor = target.parent
    while cursor != root:
        if cursor.is_symlink():
            raise ValueError("Symlinked source directory")
        cursor = cursor.parent
    return target


def _read_receipted(root: Path, relative: str, hashes: set[tuple[str, int]]) -> bytes:
    p = _safe_input(root, relative)
    size = p.stat().st_size
    if size > _MAX_XML_BYTES:
        raise ValueError("Source file too large for notice audit")
    data = p.read_bytes()
    if (hashlib.sha256(data).hexdigest(), len(data)) not in hashes:
        raise ValueError("Source not present in original receipt digest inventory")
    return data


def _notice_from_xml(raw: bytes, expected_reg: str, sha: str) -> dict | None:
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("XML DTD or entity definition prohibited")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("Malformed original EIS XML") from exc
    if _name(root) != "export":
        return None
    notices = [n for n in root if _name(n).startswith("epNotification")]
    if not notices:
        return None
    if len(notices) != 1:
        raise ValueError("Ambiguous multiple notice nodes")
    notice = notices[0]
    version_raw = _child_text(notice, "versionNumber")
    if not version_raw or not version_raw.isdecimal() or int(version_raw) < 1:
        raise ValueError("Invalid notice versionNumber")
    info = next((n for n in notice if _name(n) == "commonInfo"), None)
    if info is None:
        raise ValueError("No EIS commonInfo")
    number = _nested_text(info, "purchaseNumber")
    if number != expected_reg:
        raise ValueError("Notice registry number conflicts with archived run")
    url = _nested_text(info, "href")
    if url is None:
        raise ValueError("Original notice has no official common-info href")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "zakupki.gov.ru":
        raise ValueError("Untrusted original notice common-info host")
    deadline = _nested_text(notice, "endDT")
    if deadline:
        try:
            dt = datetime.fromisoformat(deadline)
            if dt.tzinfo is None or dt.utcoffset() is None:
                raise ValueError("Deadline missing timezone")
        except ValueError as exc:
            raise ValueError("Invalid saved notice endDT") from exc
    # This is evidence of what this particular archived notice contained.
    attachment_pairs: list[tuple[str, int]] = []
    for item in notice.iter():
        if _name(item) != "attachmentInfo":
            continue
        filename = _child_text(item, "fileName")
        size_raw = _child_text(item, "fileSize")
        if not filename or size_raw is None or not size_raw.isdecimal():
            raise ValueError("Malformed notice attachment filename/size")
        attachment_pairs.append((filename, int(size_raw)))
    if len(attachment_pairs) != len(set(attachment_pairs)):
        raise ValueError("Ambiguous repeated attachment filename+size")
    return {
        "version": int(version_raw),
        "xml_sha256": sha,
        "notice_type": _name(notice),
        "published_at": _nested_text(info, "publishDTInEIS"),
        "archived_deadline": deadline,
        "attachments": attachment_pairs,
    }


def audit_original_notice_revisions(receipts: dict, runs_root: Path) -> dict:
    """All failures are case-local except manifest corruption, no acceptance implied."""
    if receipts.get("schema_version") != "apr06-readonly-receipts-v1":
        raise ValueError("Unexpected receipt schema")
    if not runs_root.is_dir() or runs_root.is_symlink():
        raise ValueError("Missing valid source run directory")
    seen_regs: set[str] = set()
    seen_runs: set[str] = set()
    results: list[dict] = []
    for item in receipts.get("cases", []):
        reg, run = item.get("reg_number"), item.get("run_id")
        if (not isinstance(reg, str) or not _REG.fullmatch(reg)
                or not isinstance(run, str) or not _RUN.fullmatch(run)
                or reg in seen_regs or run in seen_runs):
            raise ValueError("Invalid/duplicate registry or run")
        seen_regs.add(reg)
        seen_runs.add(run)
        source_files = item.get("document_files")
        if not isinstance(source_files, list) or len(source_files) > _MAX_FILES_PER_CASE:
            raise ValueError("Invalid receipt file inventory")
        approved_receipts = set()
        for entry in source_files:
            digest, size = entry.get("sha256"), entry.get("bytes")
            if (not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)
                    or type(size) is not int or size <= 0):
                raise ValueError("Invalid documented source checksum")
            approved_receipts.add((digest, size))
        input_root = runs_root / run / "input"
        result = {
            "reg_number": reg,
            "archived_source_file_count": len(source_files),
            "archived_notice_revisions": [],
            "latest_archived_notice_version": None,
            "latest_archived_notice_sha256": None,
            "latest_archived_deadline": None,
            "latest_notice_attachment_count": 0,
            "archive_name_size_correlated": 0,
            "archive_name_size_unmatched": 0,
            "source_state": "NO_ARCHIVED_NOTICE",
            "official_current_eis_status_verified": False,
            "official_attachment_uid_bound": False,
            "human_reviewed": False,
            "commercial_go": False,
        }
        if not source_files:
            results.append(result)
            continue
        try:
            manifest_path = runs_root / run / "procurement" / "attachments_manifest.json"
            if manifest_path.is_symlink():
                raise ValueError("Symlinked attachment inventory")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, list) or len(manifest) > _MAX_FILES_PER_CASE + 1:
                raise ValueError("Invalid archive attachment index")
            sources = defaultdict(list)
            notices = []
            for entry in manifest:
                if entry.get("status") != "saved":
                    continue
                if entry.get("source_type") not in {"getdocs_archive", "notice_xml_attachments"}:
                    continue
                name, relative = entry.get("name"), entry.get("stored_name")
                size = entry.get("size_bytes")
                if not isinstance(name, str) or not isinstance(relative, str):
                    raise TypeError("Malformed archived file metadata")
                if name.lower().endswith(".xml"):
                    raw = _read_receipted(input_root, relative, approved_receipts)
                    parsed = _notice_from_xml(raw, reg, hashlib.sha256(raw).hexdigest())
                    if parsed is not None:
                        notices.append(parsed)
                elif type(size) is int and size > 0:
                    # Count only verified file bytes from archived receipt inventory.
                    p = _safe_input(input_root, relative)
                    if p.stat().st_size != size:
                        raise ValueError("Mismatch between extracted doc and archive index")
                    if (hashlib.sha256(p.read_bytes()).hexdigest(), size) not in approved_receipts:
                        raise ValueError("Archived document not present in original receipts")
                    sources[(name, size)].append(relative)
            if not notices:
                result["source_state"] = "NO_ARCHIVED_NOTICE"
            else:
                for notice in notices:
                    if sum(x["version"] == notice["version"] for x in notices) > 1:
                        raise ValueError("Duplicate/conflicting notice version")
                latest = max(notices, key=lambda x: x["version"])
                result["archived_notice_revisions"] = sorted(x["version"] for x in notices)
                result["latest_archived_notice_version"] = latest["version"]
                result["latest_archived_notice_sha256"] = latest["xml_sha256"]
                result["latest_archived_deadline"] = latest["archived_deadline"]
                expected = latest["attachments"]
                hits = sum(len(sources.get(key, [])) == 1 for key in expected)
                result["latest_notice_attachment_count"] = len(expected)
                result["archive_name_size_correlated"] = hits
                result["archive_name_size_unmatched"] = len(expected) - hits
                if latest["archived_deadline"] is None:
                    result["source_state"] = "DEADLINE_UNKNOWN_FROM_ARCHIVED_NOTICE"
                elif hits != len(expected):
                    result["source_state"] = "ARCHIVED_LATEST_ATTACHMENTS_INCOMPLETE"
                else:
                    result["source_state"] = "ARCHIVED_NAME_SIZE_ONLY_CORRELATION"
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            result["source_state"] = "FAIL_CLOSED_ORIGINAL_SOURCE_INCONSISTENT"
            result["source_error_type"] = type(exc).__name__
        results.append(result)
    counts = Counter(x["source_state"] for x in results)
    return {
        "schema_version": "apr06-archived-notice-source-binding-v1",
        "basis": "SAVED_EIS_GETDOCS_XML_AND_ORIGINAL_EXTRACTED_BYTES_OFFLINE",
        "official_current_eis_verified": 0,
        "human_gold_labels": 0,
        "commercial_accepted": False,
        "notice_uid_or_attachment_version_link_verified": False,
        "summary": {
            "cases": len(results),
            "cases_with_archived_notices": sum(bool(x["archived_notice_revisions"]) for x in results),
            "archived_latest_attachment_count": sum(x["latest_notice_attachment_count"] for x in results),
            "archived_latest_name_size_correlations": sum(x["archive_name_size_correlated"] for x in results),
            "archived_latest_unmatched": sum(x["archive_name_size_unmatched"] for x in results),
            "states": dict(sorted(counts.items())),
        },
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--runs-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = audit_original_notice_revisions(
        json.loads(args.manifest.read_text(encoding="utf-8")), args.runs_root
    )
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
