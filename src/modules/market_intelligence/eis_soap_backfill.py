"""Resumable, read-only EIS getDocsIP collection for Market Intelligence.

Bounded source discovery only: XML keyword hits are candidates, never proof of
equipment supplied, completed contracts, manufacturers, or winners.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import zipfile
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import yaml

from src.modules.market_intelligence.technical_matching import _matching_terms
from src.modules.tender_operator_agent_demo.settings import ZakupkiSoapSettings
from src.modules.tender_operator_agent_demo.zakupki_soap_client import ZakupkiSoapClient

MAX_ZIP_BYTES = 200 * 1024 * 1024
MAX_MEMBERS = 10000
MAX_XML_BYTES = 40 * 1024 * 1024  # Actual 44-FZ XML reaches 32.82 MiB; hard security cap.
MAX_TOTAL_UNCOMPRESSED = 500 * 1024 * 1024


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _iterate_xml_candidates(root: ET.Element) -> Iterator[tuple[str, str]]:
    """Restrict matching to procurement object/work description, not contacts."""
    targets = {
        "purchaseName", "purchaseNoticeName", "subject", "lotName",
        "lotDescription", "description", "itemName", "itemDescription",
        "lotItemName", "purchaseObject", "subjectOfContract", "subjectName",
    }
    for parent in root.iter():
        for node in parent:
            tag = _local_name(node.tag)
            p = _local_name(parent.tag)
            relevant = (tag in targets or (tag == "name" and p in {
                "lotItem", "lot", "purchaseNoticeData", "item", "purchaseObject",
            }))
            if relevant and node.text and node.text.strip():
                yield f"{p}/{tag}", node.text.strip()


def scan_archive(zip_path: Path, ontology: dict[str, Any]) -> dict[str, Any]:
    """Inspect SOAP ZIP bytes without extracting files to disk or promoting facts."""
    if zip_path.stat().st_size > MAX_ZIP_BYTES:
        raise ValueError("ZIP exceeds compressed-size limit")
    archive_sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    matches = []
    total_members = 0
    total_xml = 0
    with zipfile.ZipFile(zip_path) as bundle:
        members = bundle.infolist()
        if len(members) > MAX_MEMBERS:
            raise ValueError("ZIP member count exceeds limit")
        if sum(m.file_size for m in members) > MAX_TOTAL_UNCOMPRESSED:
            raise ValueError("ZIP exceeds cumulative uncompressed-size limit")
        for member in members:
            if not member.filename.lower().endswith(".xml") or member.is_dir():
                continue
            total_members += 1
            if member.file_size > MAX_XML_BYTES:
                raise ValueError("XML member exceeds size limit")
            data = bundle.read(member)
            total_xml += 1
            if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
                raise ValueError("DTD/entities forbidden in SOAP XML")
            root = ET.fromstring(data)
            notice_number = None
            # EIS 223-FZ uses 11 digits; 44-FZ uses 19-20 digits.
            # Do not mistake internal short purchaseNumber fields for registry IDs.
            for node in root.iter():
                tag = _local_name(node.tag)
                candidate = (node.text or "").strip()
                if ((tag in {"registrationNumber", "purchaseNoticeNumber"}
                     and re.fullmatch(r"[0-9]{11}", candidate))
                    or (tag == "purchaseNumber"
                        and re.fullmatch(r"[0-9]{19,20}", candidate))):
                    notice_number = candidate
                    break
            for locator, text in _iterate_xml_candidates(root):
                for hit in _matching_terms(text, ontology):
                    matches.append({
                        "number": notice_number,
                        "family": hit["family"],
                        "matched_terms": hit["terms"],
                        "source": {
                            "archive_sha256": archive_sha,
                            "xml_member": member.filename,
                            "xml_sha256": hashlib.sha256(data).hexdigest(),
                            "xml_locator": locator,
                        },
                        "excerpt": text[:250],
                        "classification": "lexical_candidate_not_verified",
                    })
    return {
        "archive_sha256": archive_sha,
        "xml_documents_inspected": total_xml,
        "matches": matches,
        "candidate_numbers": sorted({m["number"] for m in matches if m["number"]}),
    }


def _safe_error(error: Exception, token: str) -> str:
    message = str(error)
    if token:
        message = message.replace(token, "[redacted]")
    return message[:240]


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    ) as f:
        tmp_name = f.name
        json.dump(value, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp_name, path)


def _tasks(regions: list[str], first: date, last: date, max_requests: int) -> list[tuple[str, str]]:
    if not regions or any(not region.isdigit() or len(region) != 2 for region in regions):
        raise ValueError("regions must be two-digit codes")
    if first > last or max_requests < 1 or max_requests > 200:
        raise ValueError("invalid date range or max_requests")
    # Explicitly bounded to avoid accidental nationwide polling in one run.
    if (last - first).days > 90:
        raise ValueError("date interval >90 days requires separate runs")
    result = []
    day = first
    while day <= last:
        for region in regions:
            result.append((region, day.isoformat()))
            if len(result) >= max_requests:
                return result
        day += timedelta(days=1)
    return result


def _classify_transport(error: Exception) -> str:
    message = str(error).lower()
    if any(item in message for item in (
        "connection reset", "eof occurred", "ssl", "handshake", "tls", "http 502",
        "http 503", "http 504", "timed out", "timeout",
    )):
        return "retryable_network_failure"
    if "http 401" in message or "http 403" in message:
        return "authentication_or_access_failure"
    if "http 434" in message:
        return "provider_access_failure"
    return "unclassified_error_requires_review"


def collect(
    *,
    regions: list[str], first: date, last: date,
    root: Path, ontology: dict[str, Any], max_requests: int = 1,
    subsystem: str = "RI223", document_type: str = "purchaseNotice",
    download_archives: bool = False,
    client: ZakupkiSoapClient | None = None,
    force_retry: bool = False,
) -> list[dict[str, Any]]:
    """One bounded invocation: persist each task before advancing to next."""
    if subsystem not in {"RI223", "PRIZ"}:
        raise ValueError("unsupported EIS subsystem")
    if (root / "UNTRUSTED_REGION_COLLISION.json").exists():
        raise ValueError("unsafe legacy EIS archive root; use region-isolated root")
    if client is None:
        settings = replace(
            ZakupkiSoapSettings.from_env(),
            disable_proxy_for_eis=True,
            trust_env_proxy=False,
        )
        if not settings.configured:
            raise RuntimeError("EIS SOAP not configured; check secure token loader")
        client = ZakupkiSoapClient(settings, runtime_status_enabled=False)
    results = []
    for region, day in _tasks(regions, first, last, max_requests):
        receipt_path = (
            root / subsystem / document_type / day / f"region-{region}.json"
        )
        old = json.loads(receipt_path.read_text()) if receipt_path.is_file() else {}
        if (old.get("status") in {"complete", "complete_with_archive_scan"}
                and (not download_archives or old.get("archive_scan_complete"))):
            results.append(old)
            continue
        if old.get("status") == "retryable_network_failure" and not force_retry:
            results.append(old)
            continue
        receipt: dict[str, Any] = {
            "schema_version": "mi-eis-soap-receipt/0.1",
            "subsystem": subsystem, "document_type": document_type,
            "region": region, "exact_date": day,
            "attempt_utc": datetime.now(UTC).isoformat(),
            "status": "pending", "archive_count": None,
            "archive_scan_complete": False,
            "candidate_numbers": [],
        }
        try:
            r = client.get_docs_by_org_region(
                region, day, document_type, subsystem_type=subsystem
            )
            receipt["soap_status"] = r.status
            receipt["archive_count"] = len(r.archive_urls)
            receipt["status"] = "complete" if r.status == "completed" else "provider_response_review"
            if download_archives and r.status == "completed":
                archives = []
                for index, archive_url in enumerate(r.archive_urls, 1):
                    # The underlying client enforces the EIS archive host allowlist.
                    # Receipts are region-specific files, but both Moscow (77)
                    # and St Petersburg (78) share a date directory. Archive
                    # storage MUST also carry region to avoid silent overwrite.
                    archive_dir = (
                        receipt_path.parent / f"region-{region}" / f"archive-{index:03d}"
                    )
                    downloaded = client.download_archive(archive_url, archive_dir)
                    zip_path = archive_dir / downloaded.stored_name
                    scan = scan_archive(zip_path, ontology)
                    archives.append({
                        "index": index,
                        "archive_sha256": scan["archive_sha256"],
                        "xml_documents_inspected": scan["xml_documents_inspected"],
                        "candidate_numbers": scan["candidate_numbers"],
                        "matches": scan["matches"],
                    })
                receipt["archives"] = archives
                receipt["archive_scan_complete"] = True
                receipt["status"] = "complete_with_archive_scan"
                receipt["candidate_numbers"] = sorted({
                    number for archive in archives for number in archive["candidate_numbers"]
                })
            # Do not save expiring archive URLs or token-bearing request envelopes.
        except Exception as exc:  # noqa: BLE001
            receipt["status"] = _classify_transport(exc)
            receipt["error_type"] = type(exc).__name__
            receipt["error"] = _safe_error(exc, client.settings.token)
        _atomic_write_json(receipt_path, receipt)
        results.append(receipt)
        if receipt["status"] == "retryable_network_failure":
            # Circuit breaker: a scheduled upstream outage is not zero results.
            break
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded resumable EIS SOAP regional source collection")
    parser.add_argument("--region", action="append", required=True)
    parser.add_argument("--date-from", type=date.fromisoformat, required=True)
    parser.add_argument("--date-to", type=date.fromisoformat, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--ontology", type=Path, required=True)
    parser.add_argument("--subsystem", choices=["RI223", "PRIZ"], default="RI223")
    parser.add_argument("--document-type", default="purchaseNotice")
    parser.add_argument("--max-requests", type=int, default=1)
    parser.add_argument("--download-archives", action="store_true")
    parser.add_argument("--force-retry", action="store_true")
    parser.add_argument("--execute", action="store_true",
                        help="Required to send real SOAP calls and optionally download archives")
    args = parser.parse_args()
    tasks = _tasks(args.region, args.date_from, args.date_to, args.max_requests)
    if not args.execute:
        print(json.dumps({"dry_run": True, "tasks": tasks}, ensure_ascii=False))
        return
    ontology = yaml.safe_load(args.ontology.read_text(encoding="utf-8"))
    receipts = collect(
        regions=args.region, first=args.date_from, last=args.date_to,
        root=args.root, ontology=ontology, max_requests=args.max_requests,
        subsystem=args.subsystem, document_type=args.document_type,
        download_archives=args.download_archives,
        force_retry=args.force_retry,
    )
    # Emit only operational metadata; lead evidence stays in local receipts.
    for row in receipts:
        print(json.dumps({
            key: row.get(key) for key in (
                "region", "exact_date", "status", "soap_status", "archive_count",
                "archive_scan_complete", "candidate_numbers", "error_type", "error"
            )
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
