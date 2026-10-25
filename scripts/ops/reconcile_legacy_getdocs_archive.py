"""Restore provenance for an EXISTING archived getDocsIP ZIP, never the live edition.

Default is read-only. Explicit --apply requires both exact archive SHA256 and
original metadata SHA256, plus an external backup of the metadata/events.
No EIS network, ETP, upload, LLM or database writes.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

# Direct CLI execution must import THIS checkout, not an unrelated editable venv.
if __package__ in (None, "") and __file__ != "<stdin>":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.modules.tender_operator_agent_demo.eis_official_procedure import (
    classify_official_eis_archive,
)
from src.modules.tender_operator_agent_demo.operator_notice_revision import (
    matched_archived_eis_notification,
)
from src.modules.tender_operator_agent_demo.upload_service import (
    append_demo_run_event,
    get_demo_run_dir,
    get_demo_run_input_dir,
    load_demo_run_metadata,
)


class ProvenanceError(ValueError):
    """A historic archive cannot be safely linked to this saved run."""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _checked_path(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or name != Path(name).name:
        raise ProvenanceError("unsafe original archive or member name")
    path = root / name
    if path.is_symlink() or not path.is_file() or path.resolve().parent != root.resolve():
        raise ProvenanceError("original archive not a regular file in saved run")
    return path


def _event_receipt(run_dir: Path, *, archive_name: str, archive_size: int,
                   number: str) -> dict[str, Any]:
    path = run_dir / "events.jsonl"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ProvenanceError("historical getDocsIP event evidence missing")
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    started = [
        x for x in events if x.get("event_type") == "eis_getdocs_started"
        and (x.get("details") or x.get("metadata") or {}).get("reestr_number") == number
        and (x.get("details") or x.get("metadata") or {}).get("soap_method") == "getDocsByReestrNumber"
    ]
    links = [
        x for x in events if x.get("event_type") == "eis_archive_url_received"
        and (x.get("details") or x.get("metadata") or {}).get("archive_source_host") == "int.zakupki.gov.ru"
        and (x.get("details") or x.get("metadata") or {}).get("archive_url_present") is True
    ]
    receipt = [
        x for x in events if x.get("event_type") == "eis_archive_downloaded"
        and (x.get("details") or x.get("metadata") or {}).get("stored_name") == archive_name
        and (x.get("details") or x.get("metadata") or {}).get("size_bytes") == archive_size
    ]
    if len(started) != 1 or len(links) != 1 or len(receipt) != 1:
        raise ProvenanceError("source request/download events do not uniquely match ZIP and notice")
    return {"request_event": started[0].get("timestamp"),
            "download_event": receipt[0].get("timestamp")}


def evaluate(run_id: str, *, archive_name: str = "documentation-archive.zip") -> tuple[dict[str, Any], dict[str, Any]]:
    if not re.fullmatch(r"toa-run-[0-9A-Za-z-]{8,90}", run_id):
        raise ProvenanceError("run id is invalid")
    run_dir = get_demo_run_dir(run_id)
    source_dir = get_demo_run_input_dir(run_id)
    metadata_path = run_dir / "metadata.json"
    if metadata_path.is_symlink() or not metadata_path.is_file():
        raise ProvenanceError("run metadata is missing or unsafe")
    metadata_bytes = metadata_path.read_bytes()
    metadata = load_demo_run_metadata(run_id)
    number = metadata.get("procurement_id")
    if (metadata.get("procurement_source") != "zakupki_gov_ru_getdocs_ip"
            or not isinstance(number, str) or not re.fullmatch(r"\d{19}", number)
            or number != metadata.get("reestr_number")
            or metadata.get("archive_downloaded") is not True
            or metadata.get("getdocs_status") != "completed"
            or metadata.get("archive_source_host") != "int.zakupki.gov.ru"
            or not isinstance(metadata.get("getdocs_ref_id"), str)
            or not metadata.get("getdocs_ref_id")
            or not isinstance(metadata.get("getdocs_request_id"), str)
            or not metadata.get("getdocs_request_id")):
        raise ProvenanceError("saved run does not have a source-bound official getDocsIP receipt")

    archive = _checked_path(source_dir, archive_name)
    raw = archive.read_bytes()
    if not 0 < len(raw) <= 8_000_000:
        raise ProvenanceError("original ZIP size out of allowed bounds")
    receipt = _event_receipt(run_dir, archive_name=archive_name, archive_size=len(raw), number=number)
    classified = classify_official_eis_archive(archive, number)
    if classified.get("status") != "ATTESTED_COMPETITIVE" or classified.get("source_version") is None:
        raise ProvenanceError("archived original ZIP does not attest a competitive notice")

    selected = []
    with zipfile.ZipFile(archive) as zipped:
        for member in zipped.infolist():
            if member.is_dir() or not re.fullmatch(
                rf"epNotification(?:EF2020|EZK2020|EOK2020)_{number}_{classified['source_version']}_[A-Fa-f0-9]{{32}}\.xml",
                member.filename,
            ):
                continue
            original_xml = zipped.read(member)
            if _digest(original_xml) != classified["notice_xml_sha256"]:
                raise ProvenanceError("original XML SHA mismatch")
            revision = matched_archived_eis_notification(original_xml.decode("utf-8-sig"), number)
            if revision is None or revision["version"] != classified["source_version"]:
                raise ProvenanceError("official ZIP notice revision is not verifiable")
            for file in metadata.get("files") or []:
                if file.get("original_name") != member.filename or file.get("extension") != ".xml":
                    continue
                stored = file.get("stored_name")
                if not isinstance(stored, str) or not stored.startswith("extracted/"):
                    continue
                source = source_dir / stored
                if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(source_dir.resolve()):
                    continue
                if source.read_bytes() == original_xml and file.get("size_bytes") == len(original_xml):
                    selected.append((file, revision))
    if len(selected) != 1:
        raise ProvenanceError("saved XML does not uniquely match selected archived official ZIP revision")
    file, revision = selected[0]
    updated = copy.deepcopy(metadata)
    for key, value in (
        ("archive_stored_name", archive_name),
        ("original_getdocs_archive_sha256", classified["archive_sha256"]),
        ("official_eis_procedure", classified),
    ):
        existing = updated.get(key)
        if existing is not None and existing != value:
            raise ProvenanceError(f"existing {key} conflicts with original archive")
        updated[key] = value
    selected_revision = {
        "version": revision["version"],
        "purchase_number": number,
        "published_at": revision["published_at"],
        "file_id": file["file_id"],
        "current_live_eis_verified": False,
    }
    existing_revision = updated.get("notice_revision_selected")
    if existing_revision is not None and existing_revision != selected_revision:
        raise ProvenanceError("existing notice revision conflicts with first-party archived XML")
    updated["notice_revision_selected"] = selected_revision
    updated["notice_revision_requires_review"] = True
    updated["archived_zip_reconciliation"] = {
        "contract": "getdocs-legacy-receipt-retrospective-v1",
        "mode": "reconstructed_from_saved_zip_and_original_getdocs_event",
        "archive_sha256": classified["archive_sha256"],
        "original_notice_xml_sha256": classified["notice_xml_sha256"],
        "receipt_event_timestamp": receipt["download_event"],
        "not_original_transport_time_sha_receipt": True,
        "latest_live_eis_revision_verified": False,
    }
    if (metadata.get("archived_zip_reconciliation") is not None
            and metadata["archived_zip_reconciliation"] != updated["archived_zip_reconciliation"]):
        raise ProvenanceError("existing retrospective reconciliation conflicts")
    result = {
        "run_id": run_id,
        "procurement_number": number,
        "archive_name": archive_name,
        "archive_size": len(raw),
        "archive_sha256": classified["archive_sha256"],
        "notice_xml_sha256": classified["notice_xml_sha256"],
        "archived_notice_version": classified["source_version"],
        "notice_type": classified["notice_type"],
        "selected_file_id": file["file_id"],
        "saved_xml_identical_to_archive": True,
        "source_receipt_verified": True,
        "metadata_sha256_before": _digest(metadata_bytes),
        "already_reconciled": metadata == updated,
        "live_eis_verified": False,
        "business_go_eligible": False,
    }
    return updated, result


def apply(run_id: str, updated: dict[str, Any], report: dict[str, Any],
          *, expected_archive_sha256: str, expected_metadata_sha256: str) -> bool:
    if not re.fullmatch(r"[a-f0-9]{64}", expected_archive_sha256) or not re.fullmatch(
        r"[a-f0-9]{64}", expected_metadata_sha256
    ):
        raise ProvenanceError("two exact independent 64-hex SHA256 approvals required")
    if (report["archive_sha256"] != expected_archive_sha256
            or report["metadata_sha256_before"] != expected_metadata_sha256):
        raise ProvenanceError("source ZIP or metadata hash changed since approval")
    if report["already_reconciled"]:
        return False
    path = get_demo_run_dir(run_id) / "metadata.json"
    # Revalidate all reads for the precise current state just before writing.
    fresh, receipt = evaluate(run_id, archive_name=report["archive_name"])
    if receipt != report or fresh != updated:
        raise ProvenanceError("source file or metadata changed since preflight")
    old = path.read_bytes()
    parent = path.parent
    fd, temp = tempfile.mkstemp(prefix=".metadata-reconcile-", suffix=".tmp", dir=parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(updated, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if _digest(path.read_bytes()) != _digest(old):
            raise ProvenanceError("metadata changed during save")
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    append_demo_run_event(
        run_id, "eis_legacy_original_zip_reconciled",
        "Подтверждён сохранённый оригинальный ZIP/архивная редакция ЕИС; текущая редакция не подтверждена.",
        {
            "archive_sha256": report["archive_sha256"],
            "notice_xml_sha256": report["notice_xml_sha256"],
            "archived_notice_version": report["archived_notice_version"],
            "live_revision_verified": False,
            "historical_receipt_reconciled": True,
        },
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--archive-name", default="documentation-archive.zip")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-archive-sha256")
    parser.add_argument("--expected-metadata-sha256")
    args = parser.parse_args()
    try:
        updated, report = evaluate(args.run_id, archive_name=args.archive_name)
        report["applied"] = apply(
            args.run_id, updated, report,
            expected_archive_sha256=args.expected_archive_sha256 or "",
            expected_metadata_sha256=args.expected_metadata_sha256 or "",
        ) if args.apply else False
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except (ProvenanceError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "reason": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
