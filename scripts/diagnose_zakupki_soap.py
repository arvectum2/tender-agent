from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import ssl
import sys
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.modules.tender_operator_agent_demo.attachment_downloader import (
    download_procurement_attachments,
)
from src.modules.tender_operator_agent_demo.procurement_schemas import (
    ProcurementAttachment,
)
from src.modules.tender_operator_agent_demo.settings import ZakupkiSoapSettings
from src.modules.tender_operator_agent_demo.zakupki_soap_client import ZakupkiSoapClient


def diagnostics_dir() -> Path:
    return Path("company_agent_runs/zakupki_soap_diagnostics")


def _target_host_allowed(settings: ZakupkiSoapSettings) -> bool:
    hostname = (urlparse(settings.individual_base_url).hostname or "").lower()
    for host in settings.allowed_hosts:
        normalized = host.lstrip(".").lower()
        if hostname == normalized or hostname.endswith(f".{normalized}"):
            return True
    return False


def _base_payload(settings: ZakupkiSoapSettings, owner: str, method: str, reestr_number: str) -> dict[str, Any]:
    return {
        "token_owner": owner,
        "token_present": settings.token_configured,
        "endpoint": settings.individual_base_url,
        "xsd_url": settings.individual_xsd_url,
        "method": method,
        "reestr_number": reestr_number,
        "xsd_status": "not_checked",
        "soap_post_status": "not_called",
        "response_kind": "not_called",
        "archive_url_present": False,
        "download_status": "not_requested",
        "sanitized_error": "",
        "system_proxy_detected": bool(
            os.getenv("HTTP_PROXY")
            or os.getenv("http_proxy")
            or os.getenv("HTTPS_PROXY")
            or os.getenv("https_proxy")
            or os.getenv("ALL_PROXY")
            or os.getenv("all_proxy")
        ),
        "env_proxy_detected": bool(
            os.getenv("HTTP_PROXY")
            or os.getenv("http_proxy")
            or os.getenv("HTTPS_PROXY")
            or os.getenv("https_proxy")
            or os.getenv("ALL_PROXY")
            or os.getenv("all_proxy")
        ),
        "client_trust_env": False if settings.disable_proxy_for_eis else settings.trust_env_proxy,
        "eis_proxy_disabled": settings.disable_proxy_for_eis,
        "target_host": urlparse(settings.individual_base_url).hostname or "",
        "target_host_allowed": _target_host_allowed(settings),
        "no_proxy_contains_zakupki": "zakupki.gov.ru" in ((os.getenv("NO_PROXY") or os.getenv("no_proxy") or "").lower()),
        "route_mode": "direct_for_eis" if settings.disable_proxy_for_eis else ("env_proxy" if settings.trust_env_proxy else "unknown"),
    }


def _run_method(client: ZakupkiSoapClient, method: str, reestr_number: str, *, subsystem_type: str = "PRIZ", org_region: str = "72", exact_date: str = "2024-12-24", document_type: str = "epNotificationEF2020") -> dict[str, Any]:
    if method == "getDocsByReestrNumber":
        result = (client.get_docs_by_reestr_number(reestr_number) if subsystem_type == "PRIZ" else client.get_docs_by_reestr_number(reestr_number, subsystem_type=subsystem_type))
    elif method == "getDocsByOrgRegion":
        result = client.get_docs_by_org_region(org_region, exact_date, document_type, subsystem_type=subsystem_type)
    elif method == "getNsi":
        result = client.get_nsi()
    else:
        raise ValueError(f"Unsupported method: {method}")
    payload = {
        "soap_post_status": "ok",
        "response_kind": result.status,
        "archive_url_present": bool(result.archive_url),
        "archive_urls_count": len(result.archive_urls),
        "ref_id_present": bool(result.ref_id),
        "warnings": result.warnings,
        "safe_diagnostic": result.safe_diagnostic,
    }
    if result.warnings:
        payload["sanitized_error"] = " ".join(result.warnings)
    if result.archive_url:
        parsed = urlparse(result.archive_url)
        payload["_archive_url"] = result.archive_url
        payload["archive_url_summary"] = {
            "host": parsed.hostname or "",
            "path": parsed.path or "/",
        }
    else:
        payload["download_status"] = "no_archive_url"
    return payload


def _run_route_check(settings: ZakupkiSoapSettings) -> dict[str, Any]:
    parsed = urlparse(settings.individual_base_url)
    host = parsed.hostname or ""
    port = parsed.port or 443
    payload: dict[str, Any] = {
        "dns_status": "not_checked",
        "tcp_status": "not_checked",
        "tls_status": "not_checked",
        "http_get_status": "not_checked",
    }
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        payload["dns_status"] = "ok"
        payload["dns_addresses"] = sorted({item[4][0] for item in addresses})[:4]
    except Exception as exc:  # noqa: BLE001
        payload["dns_status"] = "error"
        payload["sanitized_error"] = str(exc)
        return payload

    try:
        with socket.create_connection((host, port), timeout=settings.timeout_seconds):
            pass
        payload["tcp_status"] = "ok"
    except Exception as exc:  # noqa: BLE001
        payload["tcp_status"] = "error"
        payload["sanitized_error"] = str(exc)
        return payload

    try:
        context = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=settings.timeout_seconds) as sock:
            with context.wrap_socket(sock, server_hostname=host):
                pass
        payload["tls_status"] = "ok"
    except Exception as exc:  # noqa: BLE001
        payload["tls_status"] = "error"
        payload["sanitized_error"] = str(exc)
        return payload

    try:
        client = ZakupkiSoapClient(settings)
        xsd_probe = client.probe_xsd()
        payload["http_get_status"] = xsd_probe.get("status", "unknown")
        if xsd_probe.get("status") == "error":
            payload["sanitized_error"] = str(xsd_probe.get("error", ""))
    except Exception as exc:  # noqa: BLE001
        payload["http_get_status"] = "error"
        payload["sanitized_error"] = str(exc)
    return payload


def run_diagnostics(
    *,
    settings: ZakupkiSoapSettings,
    reestr_number: str,
    owner: str = "individual",
    method: str = "getDocsByReestrNumber",
    check_xsd: bool = False,
    download_archive: bool = False,
    route_check: bool = False,
    subsystem_type: str = "PRIZ",
    org_region: str = "72",
    exact_date: str = "2024-12-24",
    document_type: str = "epNotificationEF2020",
) -> dict[str, Any]:
    payload = _base_payload(settings, owner, method, reestr_number)
    payload["selection"] = {"subsystem_type": subsystem_type, "org_region": org_region, "exact_date": exact_date, "document_type": document_type}
    if not settings.configured:
        payload["soap_post_status"] = "not_configured"
        return payload

    client = ZakupkiSoapClient(settings)
    if route_check:
        payload["route_check"] = _run_route_check(settings)
    if check_xsd:
        xsd_probe = client.probe_xsd()
        payload["xsd_status"] = xsd_probe.get("status", "unknown")
        if xsd_probe.get("status") == "error":
            payload["sanitized_error"] = str(xsd_probe.get("error", ""))

    methods = ["getNsi", "getDocsByReestrNumber", "getDocsByOrgRegion"] if method == "all" else [method]
    payload["methods"] = {}
    for item in methods:
        try:
            method_payload = _run_method(client, item, reestr_number, subsystem_type=subsystem_type, org_region=org_region, exact_date=exact_date, document_type=document_type)
        except RuntimeError as exc:
            method_payload = {
                "soap_post_status": "transport_error",
                "response_kind": "transport_error",
                "sanitized_error": str(exc),
                "archive_url_present": False,
            }
        payload["methods"][item] = method_payload

    primary = payload["methods"].get("getDocsByReestrNumber") or next(iter(payload["methods"].values()))
    payload["soap_post_status"] = primary.get("soap_post_status", "unknown")
    payload["response_kind"] = primary.get("response_kind", "unknown")
    payload["archive_url_present"] = primary.get("archive_url_present", False)
    if primary.get("sanitized_error"):
        payload["sanitized_error"] = primary["sanitized_error"]

    if download_archive and primary.get("archive_url_present") and primary.get("archive_url_summary"):
        archive_url = primary.get("_archive_url") or (
            "https://" + primary["archive_url_summary"]["host"] + primary["archive_url_summary"]["path"]
        )
        try:
            target_dir = diagnostics_dir() / "downloads"
            downloaded = client.download_archive(archive_url, target_dir)
            binary_result = download_xml_referenced_attachments(
                target_dir / downloaded.stored_name, target_dir / "attachments"
            )
            payload["binary_attachments"] = binary_result
            payload["download_status"] = (
                "downloaded_review_required"
                if binary_result["complete"] and binary_result.get("requires_manual_review")
                else "downloaded" if binary_result["complete"] else "incomplete_attachments"
            )
            payload["downloaded_size_bytes"] = downloaded.size_bytes
            payload["archive_url_summary"] = {
                "host": downloaded.source_url_host,
                "path": downloaded.source_url_path,
            }
        except RuntimeError as exc:
            payload["download_status"] = "download_error"
            payload["sanitized_error"] = str(exc)
    elif primary.get("archive_url_present"):
        payload["archive_url_summary"] = primary.get("archive_url_summary", {})
    elif payload["download_status"] == "not_requested":
        payload["download_status"] = "no_archive_url"

    for method_payload in payload.get("methods", {}).values():
        method_payload.pop("_archive_url", None)

    return payload



def download_xml_referenced_attachments(archive: Path, target_dir: Path) -> dict[str, Any]:
    """Download EIS notice attachmentInfo binaries; an XML ZIP is not a document bundle."""
    attachments: list[ProcurementAttachment] = []
    archive_sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            if not member.filename.lower().endswith(".xml"):
                continue
            if member.file_size > 20 * 1024 * 1024:
                raise RuntimeError("EIS notice XML exceeds safe size")
            xml_bytes = bundle.read(member)
            root = ET.fromstring(xml_bytes)
            is_ri223 = root.tag in {
                "{http://zakupki.gov.ru/223fz/purchase/1}purchaseNotice",
                "{http://zakupki.gov.ru/223fz/purchase/1}purchaseProtocol",
            }
            xml_sha256 = hashlib.sha256(xml_bytes).hexdigest()
            for item in root.iter():
                local = item.tag.rsplit("}", 1)[-1]
                if local not in {"attachmentInfo", "attachments"}:
                    continue
                items = [item] if local == "attachmentInfo" else [x for x in item if x.tag.rsplit("}", 1)[-1] == "document"]
                for entry in items:
                    fields = {child.tag.rsplit("}", 1)[-1]: (child.text or "").strip() for child in entry}
                    if not fields.get("fileName"):
                        continue
                    uid = fields.get("publishedContentId") or fields.get("contentUid") or fields.get("guid") or str(len(attachments) + 1)
                    if any(existing.attachment_id == uid for existing in attachments):
                        continue
                    attachments.append(ProcurementAttachment(
                        attachment_id=uid,
                        name=fields["fileName"], url=fields.get("url"),
                        size_bytes=int(fields["fileSize"]) if fields.get("fileSize", "").isdigit() else None,
                        can_download=bool(fields.get("url")),
                        provenance={
                            "source_regime": "223fz",
                            "archive_sha256": archive_sha256,
                            "xml_member": member.filename,
                            "xml_sha256": xml_sha256,
                            "source_attachment_uid": uid,
                        } if is_ri223 else None,
                    ))
    if not attachments:
        return {"expected": 0, "downloaded": 0, "complete": False, "errors": ["no_attachment_info"]}
    result = download_procurement_attachments(
        attachments, target_dir=target_dir, max_attachments=100,
        max_file_size_bytes=200 * 1024 * 1024, max_total_size_bytes=500 * 1024 * 1024,
    )
    size_mismatches = [
        entry.name for entry in result.saved for source in attachments
        if entry.name == source.name and source.size_bytes is not None and entry.size_bytes != source.size_bytes
    ]
    opaque = [entry for entry in result.saved if getattr(entry, "content_inspection_status", None) == "UNINSPECTED_OPAQUE"]
    return {"expected": len(attachments), "downloaded": len(result.saved),
            "complete": len(result.saved) == len(attachments) and not size_mismatches,
            "requires_manual_review": bool(opaque),
            "opaque_unparsed_count": len(opaque),
            "content_analysis_complete": False if opaque else None,
            "size_mismatches": size_mismatches,
            "errors": [{"file": x.name, "reason": x.error} for x in result.skipped]}


def save_diagnostics(payload: dict[str, Any]) -> Path:
    target_dir = diagnostics_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "last_cli_diagnostics.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only диагностика getDocsIP для токена физлица")
    parser.add_argument("--owner", default="individual")
    parser.add_argument("--subsystem-type", default="PRIZ", choices=["PRIZ", "RI223"])
    parser.add_argument("--org-region", default="72")
    parser.add_argument("--exact-date", default="2024-12-24")
    parser.add_argument("--document-type", default="epNotificationEF2020")
    parser.add_argument("--method", default="getDocsByReestrNumber", choices=["xsd", "getNsi", "getDocsByReestrNumber", "getDocsByOrgRegion", "all"])
    parser.add_argument("--reestr-number", required=True)
    parser.add_argument("--check-xsd", action="store_true")
    parser.add_argument("--download-archive", action="store_true")
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--route-check", action="store_true")
    parser.add_argument("--disable-proxy", action="store_true")
    parser.add_argument("--save-sanitized", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = ZakupkiSoapSettings.from_env()
    if args.disable_proxy:
        settings = replace(settings, disable_proxy_for_eis=True, trust_env_proxy=False)
    method = args.method
    payload = run_diagnostics(
        settings=settings,
        reestr_number=args.reestr_number,
        owner=args.owner,
        method=("getDocsByReestrNumber" if method == "xsd" else method),
        check_xsd=args.check_xsd or method in {"xsd", "all"},
        download_archive=args.download_archive and not args.no_download,
        route_check=args.route_check,
        subsystem_type=args.subsystem_type,
        org_region=args.org_region,
        exact_date=args.exact_date,
        document_type=args.document_type,
    )
    if args.save_sanitized:
        save_diagnostics(payload)
    else:
        save_diagnostics(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
