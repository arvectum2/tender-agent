"""Fail-closed original file paths for operator run metadata references."""
from __future__ import annotations

import re
from pathlib import Path

_SAFE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,150}\Z')
def checked_original_input_path(input_dir: Path, stored_name: object) -> Path:
    if not isinstance(stored_name,str) or not _SAFE.fullmatch(stored_name):
        raise ValueError('Unsafe stored procurement document reference')
    if input_dir.is_symlink():
        raise ValueError('Unsafe procurement input directory')
    directory = input_dir.resolve(strict=True)
    candidate = directory / stored_name
    if candidate.is_symlink():
        raise ValueError('Unsafe symlink procurement document reference')
    actual = candidate.resolve(strict=True)
    if actual.parent != directory or not actual.is_file():
        raise ValueError('Procurement document is not an original regular file')
    return actual
