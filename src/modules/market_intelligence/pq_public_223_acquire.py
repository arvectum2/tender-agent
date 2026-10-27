"""Download bounded originals from a verified public EIS 223-FZ notice page.

Fallback when the corresponding original SOAP ZIP is not yet in our archive.
This is weaker than XML-bound acquisition: each file is marked as publicly
observed and requiring revision review. Never infer an award from a notice.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from .eis_attachment_manifest import _public_filestore_digest
from src.modules.tender_operator_agent_demo.attachment_downloader import (
    download_procurement_attachments,
)
from src.modules.tender_operator_agent_demo.procurement_schemas import (
    ProcurementAttachment,
)
from src.tender_research.providers.public_223fz_search import (
    Public223FzSearchProvider,
)

UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent,
                                     prefix=".public223-", encoding="utf-8",
                                     delete=False) as f:
        temp = Path(f.name)
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


def _attachment_priority(name: str) -> int:
    label = " ".join(name.casefold().split())
    if "протокол" in label and ("итогов" in label or "результат" in label):
        return 0
    if "протокол" in label:
        return 1
    if "техническое задание" in label or "техзадан" in label:
        return 2
    if label.endswith(".zip"):
        return 3
    if "закупочная документация" in label:
        return 4
    if "извещен" in label or "уведомлен" in label:
        return 5
    if "договор" in label:
        return 6
    return 7


def _source_documents_url(card_url: str, number: str) -> str | None:
    """Only a real EIS source card's exact notice number and GUID authorize this URL."""
    parts = urlsplit(card_url)
    if (parts.scheme != "https" or parts.hostname != "zakupki.gov.ru"
            or parts.username or parts.password or parts.fragment
            or parts.port not in (None, 443)
            or not parts.path.startswith("/epz/order/notice/notice223/")):
        return None
    query = parse_qs(parts.query)
    num = query.get("purchaseNoticeNumber", [])
    guids = query.get("purchaseNoticeGuid", []) or query.get("noticeGuid", [])
    if len(num) != 1 or num[0] != number or len(guids) != 1:
        return None
    guid = guids[0]
    if not UUID.fullmatch(guid):
        return None
    params = urlencode({"purchaseNoticeNumber": number, "noticeGuid": guid})
    return f"https://zakupki.gov.ru/epz/order/notice/notice223/documents.html?{params}"


def acquire(*, registry_number: str, target_root: Path,
            provider: Public223FzSearchProvider | None = None,
            max_files: int = 8, max_file_bytes: int = 25 * 1024 * 1024,
            download=download_procurement_attachments, transport=None) -> dict:
    if not re.fullmatch(r"[0-9]{11}", registry_number):
        raise ValueError("Invalid 223-FZ number")
    if not 1 <= max_files <= 12 or not 1 <= max_file_bytes <= 32 * 1024 * 1024:
        raise ValueError("Invalid attachment bounds")
    if target_root.is_symlink():
        raise ValueError("Unsafe output root")
    provider = provider or Public223FzSearchProvider()
    page = provider.search(query=registry_number, page_size=10)
    if str(page.status) != "success":
        return {"registry_number": registry_number, "status": "search_unavailable",
                "source_status": str(page.status), "files_saved": 0}
    hits = [x for x in page.items if x.registry_number == registry_number]
    docs_url = next((url for x in hits if x.card_url
                     if (url := _source_documents_url(x.card_url, registry_number))), None)
    if not docs_url:
        return {"registry_number": registry_number,
                "status": "exact_guid_unavailable", "files_saved": 0}
    detail = provider.fetch_detail(card_url=docs_url, registry_number=registry_number)
    page_html = detail.common_info_html or ""
    if (str(detail.network_status) != "success"
            or registry_number not in page_html):
        return {"registry_number": registry_number,
                "status": "documents_page_unavailable_or_mismatch", "files_saved": 0}
    page_sha = hashlib.sha256(page_html.encode("utf-8")).hexdigest()
    attachments = []
    seen = set()
    for row in detail.document_links[:100]:
        digest = _public_filestore_digest(row.url or "")
        if not digest or digest in seen or not row.file_name:
            continue
        seen.add(digest)
        attachments.append(ProcurementAttachment(
            attachment_id=digest, name=row.file_name,
            url=row.url, can_download=True,
            provenance={"source_regime": "223fz",
                        "binding": "verified_public_eis_notice_page_only",
                        "source_public_html_sha256": page_sha,
                        "source_url_sha256": digest,
                        "revision_review_required": True,
                        "original_soap_xml_binding_verified": False},
        ))
    if not attachments:
        return {"registry_number": registry_number, "status": "no_allowed_links",
                "files_saved": 0, "public_page_sha256": page_sha}
    directory = target_root / registry_number
    receipt = directory / "public-page-receipt.json"
    if directory.is_symlink() or receipt.is_symlink():
        raise ValueError("Unsafe case directory")
    if receipt.exists():
        old = json.loads(receipt.read_text(encoding="utf-8"))
        return {"registry_number": registry_number, "status": "existing_receipt",
                "files_saved": 0, "previous_count": old.get("files_saved", 0)}
    if directory.exists() and any(directory.iterdir()):
        return {"registry_number": registry_number, "status": "unreceipted_files",
                "files_saved": 0}
    attachments.sort(key=lambda item: _attachment_priority(item.name))
    result = download(
        attachments, target_dir=directory, max_attachments=max_files,
        max_file_size_bytes=max_file_bytes,
        max_total_size_bytes=max_files * max_file_bytes,
        allowed_domains={"zakupki.gov.ru"}, transport=transport,
    )
    source_files = [
        {"filename": x.stored_name, "original_name": x.name,
         "sha256": x.sha256, "size_bytes": x.size_bytes,
         "source_url_sha256": hashlib.sha256((x.source_url or "").encode()).hexdigest()}
        for x in result.saved if x.stored_name and x.sha256
    ]
    payload = {
        "schema_version": "pq-223-public-page-download/1",
        "registry_number": registry_number,
        "status": "public_page_files_downloaded" if source_files else "no_files_saved",
        "source_level": "verified_public_page_not_original_soap_xml",
        "public_page_sha256": page_sha, "files_saved": len(source_files),
        "files": source_files,
        "source_links_discovered": len(attachments),
        "source_links_selected": min(len(attachments), max_files),
        "source_selection": "commission_protocol_first_then_technical",
        "coverage_incomplete": len(attachments) > max_files or bool(result.skipped),
        "skipped": [{"name": x.name, "reason": x.error} for x in result.skipped[:max_files]],
        "revision_review_required": True,
        "award_verified": False, "signed_contract_verified": False,
    }
    _atomic(receipt, payload)
    return {"registry_number": registry_number, "status": payload["status"],
            "files_saved": len(source_files), "public_page_sha256": page_sha}


def batch(*, gaps: Path, target_root: Path, journal: Path,
          max_cases: int = 3, retry_hours: int = 12, provider=None,
          download=download_procurement_attachments, transport=None) -> dict:
    if not 1 <= max_cases <= 12 or not 1 <= retry_hours <= 720:
        raise ValueError("Case or retry budget exceeded")
    cases = json.loads(gaps.read_text(encoding="utf-8"))["cases"]
    state = json.loads(journal.read_text(encoding="utf-8")) if journal.exists() else {
        "schema_version": "pq-223-public-page-attempts/1", "attempts": []}
    tried = {str(x["registry_number"]) for x in state["attempts"]
             if x.get("status") in ("public_page_files_downloaded", "existing_receipt")}
    latest = {str(x.get("registry_number")): x for x in state["attempts"]}
    now = datetime.now(timezone.utc)
    new = []
    for case in cases:
        if len(new) >= max_cases:
            break
        number = str(case.get("procedure_id") or "")
        if not re.fullmatch(r"[0-9]{11}", number) or number in tried:
            continue
        prior = latest.get(number)
        if prior:
            try:
                age = (now - datetime.fromisoformat(prior["timestamp"])).total_seconds()
                if age < retry_hours * 3600:
                    continue
            except (KeyError, TypeError, ValueError):
                pass
        try:
            result = acquire(registry_number=number, target_root=target_root,
                             provider=provider, download=download, transport=transport)
        except (OSError, ValueError, RuntimeError) as exc:
            result = {"registry_number": number, "status": "acquisition_error",
                      "error_type": type(exc).__name__, "files_saved": 0}
        record = {"timestamp": now.isoformat(), **result}
        state["attempts"].append(record)
        _atomic(journal, state)
        new.append(record)
        tried.add(number)
    return {"cases_attempted": len(new),
            "downloaded_count": sum(x.get("files_saved", 0) for x in new),
            "results": new}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--gaps", type=Path, required=True)
    p.add_argument("--target-root", type=Path, required=True)
    p.add_argument("--journal", type=Path, required=True)
    p.add_argument("--max-cases", type=int, default=3)
    p.add_argument("--retry-hours", type=int, default=12)
    a = p.parse_args()
    print(json.dumps(batch(gaps=a.gaps, target_root=a.target_root,
                           journal=a.journal, max_cases=a.max_cases, retry_hours=a.retry_hours),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
