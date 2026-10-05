from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.shared.document_processing import EXTRACTED_STATUS, process_document_bytes


@dataclass(frozen=True)
class ExtractionDecision:
    accepted: bool
    reason: str
    text: str | None


_MIN_LEN = 24


def extract_attachment_text_with_quality_gate(
    *,
    raw_payload: dict[str, Any],
    downloader: Callable[[str], bytes] | None,
    source: str,
) -> str | None:
    existing = _first_existing_text(raw_payload)
    if existing:
        decision = quality_gate_text(existing)
        return decision.text

    attachment_urls = extract_attachment_urls(raw_payload)
    if not attachment_urls or downloader is None:
        return None

    extracted_texts: list[str] = []
    for attachment_url in attachment_urls:
        try:
            content = downloader(attachment_url)
            if not content:
                continue
            text = extract_text_from_attachment_bytes(url=attachment_url, content=content)
            if text:
                extracted_texts.append(text)
        except Exception:
            continue

    if not extracted_texts:
        return None

    combined = "\n\n".join(extracted_texts)
    decision = quality_gate_text(combined)
    return decision.text


def quality_gate_text(text: str | None) -> ExtractionDecision:
    if not text:
        return ExtractionDecision(accepted=False, reason="empty", text=None)

    normalized = re.sub(r"\s+", " ", str(text)).strip()
    if len(normalized) < _MIN_LEN:
        return ExtractionDecision(accepted=False, reason="too_short", text=None)

    letters = sum(1 for ch in normalized if ch.isalpha())
    digits = sum(1 for ch in normalized if ch.isdigit())
    alnum = letters + digits
    if alnum == 0:
        return ExtractionDecision(accepted=False, reason="noise_only", text=None)

    symbol_count = sum(1 for ch in normalized if not ch.isalnum() and not ch.isspace())
    if symbol_count > alnum * 1.3:
        return ExtractionDecision(accepted=False, reason="symbol_noise", text=None)

    tokens = re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", normalized)
    if len(tokens) < 4:
        return ExtractionDecision(accepted=False, reason="insufficient_tokens", text=None)

    unique_ratio = len({tok.lower() for tok in tokens}) / max(len(tokens), 1)
    if unique_ratio < 0.22:
        return ExtractionDecision(accepted=False, reason="repetitive_noise", text=None)

    return ExtractionDecision(accepted=True, reason="accepted", text=normalized)


def _first_existing_text(raw_payload: dict[str, Any]) -> str | None:
    for key in (
        "tz_text_extracted",
        "technicalSpecification",
        "tz_text",
        "tzText",
        "specification",
        "itemDescription",
    ):
        value = raw_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def extract_attachment_urls(raw_payload: dict[str, Any]) -> list[str]:
    found_urls: list[str] = []

    def _collect(value: Any, key_hint: str | None = None) -> None:
        if isinstance(value, str):
            text = value.strip()
            if text and key_hint and key_hint.lower() in {"url", "href", "link", "downloadurl", "fileurl", "attachmenturl"}:
                found_urls.append(text)
            found_urls.extend(re.findall(r"https?://[^\s\"'<>]+", text))
            return
        if isinstance(value, list):
            for item in value:
                _collect(item)
            return
        if isinstance(value, dict):
            for nested_key, nested_value in value.items():
                _collect(nested_value, nested_key)

    for key in (
        "attachments",
        "files",
        "documents",
        "docs",
        "technicalSpecificationFiles",
        "purchaseDocuments",
        "items",
        "positions",
        "lotItems",
    ):
        _collect(raw_payload.get(key), key)
    _collect(raw_payload)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in found_urls:
        normalized = candidate.strip().rstrip(".,;")
        if not normalized.lower().startswith(("http://", "https://")):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def extract_text_from_attachment_bytes(url: str, content: bytes) -> str | None:
    filename = Path(urlparse(url).path).name or "attachment.bin"
    processed = process_document_bytes(
        content=content,
        filename=filename,
        collection_id="tender-agent:connector-processing",
        canonical_uri=url if url.startswith(("http://", "https://")) else None,
        min_chunk_chars=1,
    )
    if processed.extraction_status != EXTRACTED_STATUS:
        return None
    return processed.text.strip() or None
