"""Source-only submission deadline for the Tender Agent demo card.

Never replace a missing or unparsable application deadline with the run
creation time. Input may originate from structured EIS notice or procurement
card metadata; absence is represented as None and requires human review.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any


def parse_submission_deadline(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
        if "T" in raw or " " in raw:
            return parsed
    except ValueError:
        pass
    for fmt in (
        "%d.%m.%Y %H:%M:%S %z",
        "%d.%m.%Y %H:%M %z",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def submission_deadline_from_metadata(metadata: Mapping[str, Any]) -> str | None:
    procurement = metadata.get("procurement")
    if not isinstance(procurement, Mapping):
        procurement = {}
    for value in (
        metadata.get("deadline"),
        metadata.get("submission_deadline"),
        procurement.get("deadline"),
        procurement.get("submission_deadline"),
    ):
        parsed = parse_submission_deadline(value)
        if parsed is not None:
            return parsed.isoformat()
    return None
