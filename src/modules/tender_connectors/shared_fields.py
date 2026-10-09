"""Shared field access and date parsing for Russian portal connectors."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def pick_nested(raw: dict[str, Any], paths: list[str]) -> str | None:
    for path in paths:
        current: Any = raw
        ok = True
        for chunk in path.split("."):
            if isinstance(current, list):
                if not chunk.isdigit():
                    ok = False
                    break
                idx = int(chunk)
                if idx >= len(current):
                    ok = False
                    break
                current = current[idx]
                continue
            if not isinstance(current, dict):
                ok = False
                break
            current = current.get(chunk)
            if current is None:
                ok = False
                break
        if not ok or current is None:
            continue
        text = str(current).strip()
        if text:
            return text
    return None


def parse_portal_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)  # noqa: DTZ007 - preserve portal-local naive time
        except ValueError:
            continue
    return None
