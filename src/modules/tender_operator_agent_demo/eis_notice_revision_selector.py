"""Pick latest *archived* EIS notice XML before retrieving referenced files.

An archive can contain several notice revisions with the same attachment name
but different official filestore UIDs. Source version selection is not proof
that this is the currently published EIS/legal tender status.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import PurePath
from typing import Any

_NOTICE_RE = re.compile(
    r"(?:ep|fcs)Notification[A-Za-z0-9]*_([0-9]{19})_([0-9]{1,4})_([A-Fa-f0-9]{32})\.xml\Z",
    re.IGNORECASE,
)
_NOTICE_PREFIX_RE = re.compile(r"(?:ep|fcs)Notification", re.IGNORECASE)
_REG_NUMBER_RE = re.compile(r"[0-9]{19}\Z")


def select_latest_archived_notice_files(
    files: Sequence[Mapping[str, Any]],
    *,
    expected_registry_number: str | None,
) -> list[Mapping[str, Any]]:
    """Keep only one unambiguous newest notice XML and other source documents.

    A same-version disagreement or mixed-procurement archive fails closed for
    the affected notice sources. Legacy unversioned notices remain usable if
    no versioned notice is present, preserving older supported source forms.
    """
    expected = (
        expected_registry_number
        if isinstance(expected_registry_number, str)
        and _REG_NUMBER_RE.fullmatch(expected_registry_number)
        else None
    )
    versioned: dict[int, tuple[str, int, str]] = {}
    unversioned: set[int] = set()
    for index, row in enumerate(files):
        filename = PurePath(str(row.get("original_name") or "")).name
        if not _NOTICE_PREFIX_RE.match(filename):
            continue
        match = _NOTICE_RE.fullmatch(filename)
        if match:
            number, edition, uid = match.groups()
            versioned[index] = (number, int(edition), uid.lower())
        else:
            unversioned.add(index)

    eligible = {
        index: fields
        for index, fields in versioned.items()
        if expected is None or fields[0] == expected
    }
    numbers = {fields[0] for fields in eligible.values()}
    keep: set[int] = set()
    if len(numbers) <= 1:
        for number in numbers:
            recent = max(v for n, v, _ in eligible.values() if n == number)
            newest = [
                (i, uid)
                for i, (n, v, uid) in eligible.items()
                if n == number and v == recent
            ]
            if len({uid for _, uid in newest}) == 1:
                keep.add(newest[0][0])

    reject = set(versioned) - keep
    if versioned:
        reject.update(unversioned)
    return [row for i, row in enumerate(files) if i not in reject]
