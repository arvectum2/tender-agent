"""Fail-closed stored original file paths for operator run metadata.

Original uploads live directly under input/, while getDocsIP extracted originals
live only under input/extracted/. Never resolve arbitrary nested metadata paths.
"""
from __future__ import annotations

import re
from pathlib import Path

_SAFE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,150}\Z")


def checked_original_input_path(input_dir: Path, stored_name: object) -> Path:
    if not isinstance(stored_name, str):
        raise ValueError("Unsafe stored procurement document reference")
    segments = stored_name.split("/")
    if len(segments) == 1:
        component = segments[0]
        subdirectory = None
    elif len(segments) == 2 and segments[0] == "extracted":
        component = segments[1]
        subdirectory = "extracted"
    else:
        raise ValueError("Unsafe stored procurement document reference")
    if not _SAFE.fullmatch(component) or component in {".", ".."}:
        raise ValueError("Unsafe stored procurement document reference")
    if input_dir.is_symlink():
        raise ValueError("Unsafe procurement input directory")
    directory = input_dir.resolve(strict=True)
    if subdirectory is not None:
        nested = directory / subdirectory
        if nested.is_symlink() or not nested.is_dir():
            raise ValueError("Unsafe procurement extracted directory")
        directory = nested.resolve(strict=True)
    candidate = directory / component
    if candidate.is_symlink():
        raise ValueError("Unsafe symlink procurement document reference")
    actual = candidate.resolve(strict=True)
    if actual.parent != directory or not actual.is_file():
        raise ValueError("Procurement document is not an original regular file")
    return actual
