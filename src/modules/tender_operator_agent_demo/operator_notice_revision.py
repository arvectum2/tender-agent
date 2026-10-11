"""Strict in-archive EIS notice revision identity, not live-current verification.

A selected highest version is only highest among the supplied official
notification XML files, not proof of the currently published EIS edition.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def matched_archived_eis_notification(
    text: str, expected_number: str
) -> dict[str, str | int] | None:
    """Validate an exact registry-matched EIS notification with a version number."""
    if not isinstance(text, str) or not re.fullmatch(r"(?:\d{11}|\d{19})", expected_number):
        return None
    if not text.strip().startswith("<") or len(text) > 12_000_000:
        return None
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        return None
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    notices = [
        node for node in root.iter()
        if _local_name(node.tag).startswith("epNotification")
        and not any(
            term in _local_name(node.tag).lower()
            for term in ("cancel", "protocol", "terminate")
        )
    ]
    if len(notices) != 1:
        return None
    notice = notices[0]
    common = next((node for node in notice if _local_name(node.tag) == "commonInfo"), None)
    if common is None:
        return None
    identity = {
        (node.text or "").strip()
        for node in common if _local_name(node.tag) == "purchaseNumber"
    }
    if identity != {expected_number}:
        return None
    raw_version = next(
        (
            (node.text or "").strip()
            for node in notice
            if _local_name(node.tag) == "versionNumber"
        ),
        None,
    )
    if raw_version is None:
        raw_version = next(
            (
                (node.text or "").strip()
                for node in common
                if _local_name(node.tag) == "versionNumber"
            ),
            None,
        )
    if not raw_version or not re.fullmatch(r"\d{1,4}", raw_version):
        return None
    version = int(raw_version)
    if version < 1:
        return None
    published = next(
        (
            (node.text or "").strip()
            for node in common
            if _local_name(node.tag) == "publishDTInEIS"
        ),
        "",
    )
    return {
        "purchase_number": expected_number,
        "version": version,
        "published_at": published,
    }
