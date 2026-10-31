"""Audit original Roseltorg 223-FZ cancellation/technical 7z with review SHA.

This module proves publication and a source-based cancellation decision. It
does NOT prove a 6–35 kV equipment sale, a winner, or a signed contract.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

MAX_PAGE = 1_000_000
MAX_ARCHIVE = 20_000_000
MAX_MEMBER = 2_000_000
MEMBERS = {
    "cancellation-protocol.docx": (
        "cancellation.7z", "Протокол отмены 26-1149.docx"),
    "original-technical-system.docx": (
        "documentation.7z", "Приложение 2 - Техническое задание/Приложение 2.docx"),
    "original-supply-specification.docx": (
        "documentation.7z", "Приложение 2 - Техническое задание/ТЗ на поставку.docx"),
    "original-notice.docx": (
        "documentation.7z", "Извещение о закупке МСП 26-1149.docx"),
}
CANCELLATION = (
    "Решили: отказаться от проведения конкурса в электронной форме № 26-1149"
)
SUBJECT = "батарей статических конденсаторов"


def _hash(path: Path, budget: int) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > budget:
        raise ValueError("Unsafe first-party Roseltorg source file")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_member(archive: Path, member: str) -> bytes:
    if not archive.is_file() or archive.is_symlink():
        raise ValueError("Missing original archive")
    if member not in {x[1] for x in MEMBERS.values()}:
        raise ValueError("Unallowlisted original archive member")
    p = subprocess.Popen(
        ["bsdtar", "-xOf", str(archive), member],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert p.stdout is not None
    content = p.stdout.read(MAX_MEMBER + 1)
    if len(content) > MAX_MEMBER:
        p.kill()
        p.communicate(timeout=3)
        raise ValueError("Archive member exceeds size budget")
    p.communicate(timeout=16)
    if p.returncode != 0 or not content.startswith(b"PK\x03\x04"):
        raise ValueError("Cannot extract original Word member from archive")
    return content


def verify(*, root: Path, queue: Path, extractor=_extract_member,
           max_cases: int = 20) -> dict:
    if root.is_symlink() or not root.is_dir() or not 1 <= max_cases <= 100:
        raise ValueError("Invalid primary Roseltorg originals scope")
    cases = sorted(x for x in root.iterdir()
                   if x.is_dir() and not x.is_symlink()
                   and re.fullmatch(r"\d{11}", x.name)
                   and (x / "source-manifest.json").is_file())
    if len(cases) > max_cases:
        raise ValueError("Roseltorg first-party source budget exceeded")
    results = []
    for case in cases:
        manifest_file = case / "source-manifest.json"
        if manifest_file.is_symlink():
            raise ValueError("Symlinked first-party source manifest")
        m = json.loads(manifest_file.read_text(encoding="utf-8"))
        if (m.get("schema_version") != "pq-roseltorg-223-originals/1"
                or m.get("registry_number") != case.name):
            raise ValueError("First-party 223 registry identity mismatch")
        source_page_url = f"https://www.roseltorg.ru/procedure/{case.name}"
        if m.get("source_page_url") != source_page_url:
            raise ValueError("Roseltorg primary notice URL mismatch")
        page = case / "original-page.html"
        if _hash(page, MAX_PAGE) != m.get("source_page_sha256"):
            raise ValueError("First-party Roseltorg HTML SHA mismatch")
        content = page.read_bytes()
        if case.name.encode() not in content:
            raise ValueError("Official original page does not bind notice number")
        docs = m.get("first_party_documents")
        if not isinstance(docs, list) or len(docs) != 2:
            raise ValueError("Expected original technical and cancellation archives")
        originals = {}
        for item in docs:
            name = item.get("filename")
            url = item.get("source_url") or ""
            parsed = urlsplit(url)
            if (name not in {"cancellation.7z", "documentation.7z"}
                    or name in originals
                    or parsed.scheme != "https"
                    or parsed.netloc != "corp.roseltorg.ru"
                    or not re.fullmatch(
                        r"/api/v1/documents/[0-9a-f-]{36}", parsed.path)
                    or parsed.query or parsed.fragment
                    or url.encode() not in content):
                raise ValueError("Non-original Roseltorg attachment or unsafe URL")
            f = case / name
            if (_hash(f, MAX_ARCHIVE) != item.get("sha256")
                    or f.stat().st_size != item.get("bytes")
                    or not f.open("rb").read(8).startswith(
                        bytes.fromhex("377abcaf271c0004"))):
                raise ValueError("First-party 223 source archive SHA mismatch")
            originals[name] = item
        if set(originals) != {"cancellation.7z", "documentation.7z"}:
            raise ValueError("Incomplete original Roseltorg publication")
        extracted = {}
        for alias, (archive_name, member) in MEMBERS.items():
            data = extractor(case / archive_name, member)
            if len(data) > MAX_MEMBER:
                raise ValueError("Unbounded original technical member")
            extracted[alias] = hashlib.sha256(data).hexdigest()
        reviewed = False
        review_id = None
        cancellation = case.name + "-"
        for path in sorted(queue.glob(cancellation + "*.json")):
            if path.is_symlink():
                continue
            d = json.loads(path.read_text(encoding="utf-8"))
            if (d.get("schema_version") != "pq-review-queue/1"
                    or d.get("state") != "reviewed"
                    or d.get("packet", {}).get("registry_number") != case.name):
                continue
            members = {x.get("filename"): x
                       for x in d["packet"].get("documents", [])}
            if any(alias not in members
                   or members[alias].get("sha256") != sha
                   for alias, sha in extracted.items()):
                continue
            quotes = [
                x for x in d.get("review", {}).get("evidence", [])
                if isinstance(x, dict)
                and x.get("sha256") in extracted.values()
            ]
            if not quotes or any(
                " ".join(str(x.get("quote", "")).split()) not in
                " ".join(members[alias].get("text", "").split())
                for x in quotes for alias in extracted
                if extracted[alias] == x.get("sha256")
            ):
                continue
            cancellation_text = " ".join(
                members["cancellation-protocol.docx"].get("text", "").split())
            if CANCELLATION not in cancellation_text or SUBJECT not in cancellation_text:
                continue
            technical_text = " ".join(
                members["original-technical-system.docx"].get("text", "").split())
            if not ("Номинальное напряжение, кВ | 110" in technical_text
                    and "Тип МПУ | МПУ-30000/10 УХЛ1" in technical_text
                    and "Номинальное напряжение, кВ | 10" in technical_text):
                continue
            reviewed = True
            review_id = d.get("id")
            break
        if not reviewed:
            raise ValueError("Missing source-SHA reviewed original cancellation/110-10 kV facts")
        results.append({
            "procedure_id": case.name,
            "source_url": source_page_url,
            "original_page_sha256": m["source_page_sha256"],
            "archive_sha256s": {name: item["sha256"]
                                for name, item in originals.items()},
            "original_member_sha256s": extracted,
            "review_queue_id": review_id,
            "commission_cancellation_source_verified": True,
            "scope_hypothesis": "110kv_reactive_power_system_with_10kv_converter",
            "price_kind": "initial_maximum_price_not_contract",
            "signed_contract_verified": False,
            "equipment_only_6_35kv_price_verified": False,
            "source_level": "original_roseltorg_223_documents_and_technical_protocol_shas",
        })
    return {
        "schema_version": "pq-primary-roseltorg-223-audit/1",
        "first_party_original_223_cases": len(results),
        "reviewed_commission_cancellation_cases": len(results),
        "verified_signed_contracts": 0,
        "records": results,
    }
