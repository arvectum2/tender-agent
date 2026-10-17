"""Fail-closed, read-only qualification criterion extraction from original EIS XML and DOCX.

Accept only a previously independently SHA-pinned original getDocsIP archive
and an independently SHA-pinned assessment document. No digital signature is
validated here. This parser supports one unambiguous price/qualification-only
44-FZ scoring table; other schemes must return an error, never guessed weights.
"""
from __future__ import annotations

import hashlib
import io
import re
import stat
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime, timedelta
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import Field, model_validator

from src.modules.company_profile_store.qualification_references import (
    QualificationCriterion,
)
from src.shared.types.common import APIModel

_ARCHIVE_MAX = 16 * 1024 * 1024
_DOCX_MAX = 10 * 1024 * 1024
_UNCOMPRESSED_MAX = 30 * 1024 * 1024
_UID = re.compile(r"[0-9A-F]{32}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class OriginalScoringEvidence(APIModel):
    schema_version: Literal["eis-original-scoring-receipt-v1"]
    procurement_number: str = Field(pattern=r"^[0-9]{19}$")
    procurement_law: Literal["44fz"]
    notice_version: int = Field(ge=1)
    original_soap_archive_sha256: str
    original_notice_xml_sha256: str
    scoring_document_uid: str
    scoring_document_sha256: str

    @model_validator(mode="after")
    def check_hashes(self):
        if not (_SHA.fullmatch(self.original_soap_archive_sha256)
                and _SHA.fullmatch(self.original_notice_xml_sha256)
                and _SHA.fullmatch(self.scoring_document_sha256)
                and _UID.fullmatch(self.scoring_document_uid)):
            raise ValueError("Invalid independently pinned original source checksum or UID")
        return self


def _safe_zip(data: bytes, *, xml_archive: bool) -> zipfile.ZipFile:
    limit = _ARCHIVE_MAX if xml_archive else _DOCX_MAX
    if len(data) > limit or not data.startswith(b"PK"):
        raise ValueError("Invalid original evidence ZIP, missing signature or excessive size")
    archive = zipfile.ZipFile(io.BytesIO(data))
    members = archive.infolist()
    if not members or len(members) > 120 or sum(m.file_size for m in members) > _UNCOMPRESSED_MAX:
        archive.close()
        raise ValueError("Unsafe source ZIP content size")
    seen: set[str] = set()
    for member in members:
        name = PurePosixPath(member.filename)
        if (member.filename in seen or name.is_absolute() or ".." in name.parts
            or member.flag_bits & 1 or stat.S_ISLNK(member.external_attr >> 16)
            or not member.filename or member.file_size > 4 * 1024 * 1024):
            archive.close()
            raise ValueError("Unsafe ZIP member")
        if xml_archive and (member.is_dir() or len(name.parts) != 1 or name.suffix.lower() != ".xml"):
            archive.close()
            raise ValueError("Expected original flat EIS SOAP XML archive")
        seen.add(member.filename)
    return archive


def _xml(data: bytes) -> ET.Element:
    if len(data) > 4 * 1024 * 1024 or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("Unsafe XML")
    return ET.fromstring(data)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first(node: ET.Element, key: str) -> str | None:
    return next(
        (x.text.strip() for x in node.iter() if _local_name(x.tag) == key and x.text),
        None,
    )


def _original_current_notice(
    data: bytes, receipt: OriginalScoringEvidence,
) -> tuple[ET.Element, str]:
    if hashlib.sha256(data).hexdigest() != receipt.original_soap_archive_sha256:
        raise ValueError("Original SOAP archive checksum mismatch")
    notices: dict[int, tuple[ET.Element, str]] = {}
    with _safe_zip(data, xml_archive=True) as archive:
        for member in archive.infolist():
            raw = archive.read(member)
            root = _xml(raw)
            detected = [x for x in root if _local_name(x.tag).startswith("epNotification")]
            if len(detected) > 1:
                raise ValueError("Multiple EIS notices in one XML")
            if not detected:
                continue
            node = detected[0]
            if _first(node, "purchaseNumber") != receipt.procurement_number:
                raise ValueError("Original purchase number mismatch")
            raw_ver = _first(node, "versionNumber")
            if not raw_ver or not raw_ver.isdecimal() or int(raw_ver) in notices:
                raise ValueError("Duplicate or invalid original revision number")
            notices[int(raw_ver)] = node, hashlib.sha256(raw).hexdigest()
    if not notices or max(notices) != receipt.notice_version:
        raise ValueError("Receipt uses stale/unknown original EIS notice revision")
    node, digest = notices[max(notices)]
    if digest != receipt.original_notice_xml_sha256:
        raise ValueError("Original EIS notice XML revision checksum mismatch")
    if _local_name(node.tag) != "epNotificationEOK2020":
        raise ValueError("Only EOK2020 EIS notice original is supported")
    return node, digest


def _original_scoring_attachment(
    node: ET.Element, receipt: OriginalScoringEvidence, docx_bytes: bytes,
) -> tuple[str, int]:
    if hashlib.sha256(docx_bytes).hexdigest() != receipt.scoring_document_sha256:
        raise ValueError("Original evaluation DOCX checksum mismatch")
    matches = []
    seen = set()
    for attachment in node.iter():
        if _local_name(attachment.tag) != "attachmentInfo":
            continue
        uid = _first(attachment, "publishedContentId")
        name = _first(attachment, "fileName")
        size = _first(attachment, "fileSize")
        source_url = _first(attachment, "url")
        if uid in seen or not uid or not _UID.fullmatch(uid):
            raise ValueError("Duplicate/invalid original EIS attachment UID")
        seen.add(uid)
        if not name or not size or not size.isdecimal():
            raise ValueError("Invalid original EIS attachment name/size")
        url = urlsplit(source_url or "")
        if (
            url.scheme != "https"
            or url.hostname != "zakupki.gov.ru"
            or url.port is not None
            or url.path != "/44fz/filestore/public/1.0/download/priz/file.html"
            or parse_qs(url.query) != {"uid": [uid]}
        ):
            raise ValueError("Original EIS attachment HTTPS source URL/UID mismatch")
        if uid == receipt.scoring_document_uid:
            matches.append((name, int(size)))
    if len(matches) != 1:
        raise ValueError("Scoring document UID absent from latest original EIS revision")
    name, size = matches[0]
    if not name.lower().endswith(".docx") or size != len(docx_bytes):
        raise ValueError("Original EIS evaluation document size/type mismatch")
    return name, size


def _docx_rows(data: bytes) -> list[list[list[str]]]:
    with _safe_zip(data, xml_archive=False) as document:
        names = {x.filename for x in document.infolist()}
        if "word/document.xml" not in names:
            raise ValueError("Original DOCX document.xml missing")
        if any("vbaProject" in x or x.lower().endswith(".bin") for x in names):
            raise ValueError("Macro/binary DOCX refused")
        root = _xml(document.read("word/document.xml"))
    tables: list[list[list[str]]] = []
    for table in root.iter(_W + "tbl"):
        rows = []
        for row in table.findall(_W + "tr"):
            cells = [
                " ".join(t.text or "" for t in cell.iter(_W + "t")).strip()
                for cell in row.findall(_W + "tc")
            ]
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def _parse_percent(value: str) -> int:
    text = value.replace("\u00a0", "").replace(" ", "").strip()
    if not re.fullmatch(r"(?:100|[0-9]{1,2})(?:[,.]0{1,2})?", text):
        raise ValueError("Unsupported non-integer scoring percentage")
    return int(text.replace(",", ".").split(".")[0])


def _score_table(tables: list[list[list[str]]]) -> tuple[int, int]:
    candidate_scores: list[tuple[int, int]] = []
    for rows in tables:
        if len(rows[0]) < 3 or "Значимость критерия оценки" not in rows[0][2]:
            continue
        weights: dict[str, int] = {}
        for row in rows[1:]:
            if len(row) < 3:
                raise ValueError("Malformed scoring table row")
            label = row[1].lower()
            if label.startswith("цена контракта"):
                key = "price"
            elif label.startswith("квалификация участников закупки"):
                key = "qualification"
            else:
                raise ValueError("Unrecognized scoring criterion; manual assessment required")
            if key in weights:
                raise ValueError("Duplicate price/qualification criteria")
            weights[key] = _parse_percent(row[2])
        if set(weights) != {"price", "qualification"} or sum(weights.values()) != 100:
            raise ValueError("Scoring weights incomplete/ambiguous")
        candidate_scores.append((weights["price"], weights["qualification"]))
    if len(candidate_scores) != 1:
        raise ValueError("No unique primary EIS price/qualification scoring table")
    return candidate_scores[0]


def _contract_rules(tables: list[list[list[str]]]) -> tuple[list[str], int]:
    candidates = []
    for rows in tables:
        for row in rows:
            if len(row) < 3:
                continue
            label = row[1].lower()
            text = row[2].lower()
            if "детализирующий показатель" not in label or "общее количество исполненных" not in label:
                continue
            if not ("чат-бот" in text and "исполненн" in text
                    and "последний акт" in text and "до даты окончания срока подачи заявок" in text
                    and all(word in text for word in ("сайт", "веб-портал", "информационн", "модул"))):
                raise ValueError("Unsupported detail qualification rule")
            laws = []
            for law in ("44", "223"):
                if re.search(rf"(?:№\s*)?{law}\s*[-‑]?\s*фз", text):
                    laws.append(f"{law}fz")
            years = re.findall(r"не ранее чем за\s*(\d+)\s*лет до даты окончания срока подачи заявок", text)
            if len(laws) != 2 or len(years) != 1 or int(years[0]) < 1:
                raise ValueError("Cannot safely prove accepted contract laws and recency")
            if "незавершенн" not in text or "акт" not in text:
                raise ValueError("Unfinished contracts must be explicitly excluded")
            candidates.append((laws, int(years[0])))
    if len(candidates) != 1:
        raise ValueError("No unique signed-contract experience scoring definition")
    return candidates[0]


def extract_official_qualification_criterion(
    *,
    original_archive_bytes: bytes,
    original_scoring_docx_bytes: bytes,
    trusted_receipt: OriginalScoringEvidence,
    analysis_date: date,
) -> QualificationCriterion:
    """Source-derived scoring. Weights and chatbot rule are parsed, not supplied."""
    notice, _ = _original_current_notice(original_archive_bytes, trusted_receipt)
    _original_scoring_attachment(notice, trusted_receipt, original_scoring_docx_bytes)
    cutoff_text = _first(notice, "endDT")
    if not cutoff_text:
        raise ValueError("Official application deadline missing")
    cutoff = datetime.fromisoformat(cutoff_text)
    if cutoff.utcoffset() != timedelta(hours=3):
        raise ValueError("Expected source original EIS MSK +03:00 deadline")
    tables = _docx_rows(original_scoring_docx_bytes)
    price, qualification = _score_table(tables)
    laws, lookback = _contract_rules(tables)
    return QualificationCriterion(
        procurement_number=trusted_receipt.procurement_number,
        procurement_law=trusted_receipt.procurement_law,
        procurement_notice_version=trusted_receipt.notice_version,
        source_document_uid=trusted_receipt.scoring_document_uid,
        source_document_sha256=trusted_receipt.scoring_document_sha256,
        qualification_weight_percent=qualification,
        price_weight_percent=price,
        accepted_contract_laws=laws,
        accepted_subjects=["website", "web_portal", "information_system", "module"],
        requires_chatbot=True,
        lookback_years=lookback,
        analysis_date=analysis_date,
        application_deadline_date=cutoff.date(),
    )
