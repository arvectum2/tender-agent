"""Safe bounded ZIP intake for procurement uploads.

This module owns archive traversal only. Generic PDF/DOCX/XML decoding stays
in Data Platform through the injected processor; no files are extracted to
disk, no external network access, and no procurement decision takes place.
"""

from __future__ import annotations

import stat
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from src.modules.procurement_analysis.frozen_types import AnalyzedDocument


def _unsafe_zip_member(info: zipfile.ZipInfo) -> bool:
    name = info.filename
    # Reject both POSIX and Windows traversal/absolute/device-style paths.
    # ZIP's canonical separator is '/', but archives from Windows can contain
    # backslashes; refuse these rather than reinterpreting a second path syntax.
    if not name or "\\" in name or "\x00" in name or name.startswith("/"):
        return True
    parts = PurePosixPath(name).parts
    if ".." in parts or "." in parts or any(":" in part for part in parts):
        return True
    mode = info.external_attr >> 16
    return stat.S_IFMT(mode) == stat.S_IFLNK


def read_operator_zip_documents(
    path: Path,
    parent_file_id: str,
    *,
    allowed_extensions: set[str],
    max_entries: int,
    max_total_bytes: int,
    extract_text: Callable[[str, bytes], tuple[str | None, list[str], str]],
    detect_role: Callable[[str], str],
) -> list[AnalyzedDocument]:
    """Fail closed on malformed/oversized archives; preserve legacy output."""
    def issue(message: str, *, name: str | None = None, index: int | None = None) -> AnalyzedDocument:
        filename = name or path.name
        return AnalyzedDocument(
            display_name=f"{path.name} :: {filename}" if name else path.name,
            extension=Path(filename).suffix.lower(),
            role="supporting",
            text=None,
            extracted_text_available=False,
            warnings=[message],
            source="zip",
            file_id=f"{parent_file_id}-ZIP-{index:02d}" if index is not None else parent_file_id,
            raw_content=None,
        )

    docs: list[AnalyzedDocument] = []
    try:
        with zipfile.ZipFile(path) as archive:
            members = [info for info in archive.infolist() if not info.is_dir()]
            if len(members) > max_entries:
                return [issue(f"ZIP archive contains too many entries. Limit: {max_entries}.")]
            if sum(info.file_size for info in members) > max_total_bytes:
                return [issue("ZIP archive exceeds the safe unpacked size limit.")]
            seen: set[str] = set()
            for index, info in enumerate(members, start=1):
                if _unsafe_zip_member(info):
                    docs.append(issue(
                        "ZIP entry was rejected because it contains an unsafe path.",
                        name=info.filename, index=index,
                    ))
                    continue
                key = info.filename.casefold()
                if key in seen:
                    docs.append(issue(
                        "ZIP entry was rejected because its name is duplicated.",
                        name=info.filename, index=index,
                    ))
                    continue
                seen.add(key)
                entry_name = PurePosixPath(info.filename).name
                extension = Path(entry_name).suffix.lower()
                if extension not in allowed_extensions or extension == ".zip":
                    continue
                if info.flag_bits & 1:
                    docs.append(issue(
                        "ZIP entry is encrypted and requires manual review.",
                        name=entry_name, index=index,
                    ))
                    continue
                try:
                    raw = archive.read(info)
                except (zipfile.BadZipFile, RuntimeError, OSError, EOFError, ValueError):
                    docs.append(issue(
                        "ZIP entry could not be read safely.",
                        name=entry_name, index=index,
                    ))
                    continue
                text, warnings, _status = extract_text(entry_name, raw)
                docs.append(AnalyzedDocument(
                    display_name=f"{path.name} :: {entry_name}",
                    extension=extension,
                    role=detect_role(entry_name),
                    text=text,
                    extracted_text_available=bool(text),
                    warnings=warnings,
                    source="zip",
                    file_id=f"{parent_file_id}-ZIP-{index:02d}",
                    raw_content=raw,
                ))
    except (zipfile.BadZipFile, OSError, ValueError):
        return [issue("ZIP archive could not be read safely.")]
    return docs
