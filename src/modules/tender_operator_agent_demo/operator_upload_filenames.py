"""Bounded filename policy for files received by the tender operator.

No filesystem writes; preserve existing allowed suffixes and storage key layout.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".xlsx", ".xls", ".txt", ".csv", ".zip", ".xml", ".html", ".htm"}


def sanitize_demo_filename(name: str, index: int) -> tuple[str, str]:
    original = Path(name or f"file-{index}").name
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext or 'unknown'}")

    stem = Path(original).stem.lower()
    stem = re.sub(r"[^a-z0-9._-]+", "-", stem).strip("._-")
    if not stem:
        stem = f"file-{index}"
    stem = stem[:60]
    stored_name = f"{index:02d}-{stem}{ext}"
    return original, stored_name
