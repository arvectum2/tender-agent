"""Narrow source-bound numeric claim check, not tender-wide factual inference."""

from __future__ import annotations

import re
from collections.abc import Sequence

from src.tender_research.rag.search_types import RagSearchHit

_TONNES = re.compile(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(?:тонн(?:а|ы)?|т\b)", re.IGNORECASE)
_CHUNK_REFERENCE = re.compile(r"chunk_id\s*[:=]\s*([^\s,;\])]+)", re.IGNORECASE)


def _number(raw: str) -> str:
    return str(float(raw.replace(",", ".")))


def contradicted_cited_quantity(
    answer: str, contexts: Sequence[RagSearchHit]
) -> str | None:
    """Detect an unsupported tonnes claim only for one explicitly cited chunk.

    This cannot resolve lots, revisions, quantity applicability, units other
    than metric tonnes or arithmetic. Uncertain cases are not classified.
    """
    by_id = {str(c.chunk_id): c for c in contexts}
    # A claim must explicitly name one exact chunk and the unit in the same
    # short sentence/line. Do not use document-wide number bags.
    for line in answer.splitlines():
        values = {_number(m.group(1)) for m in _TONNES.finditer(line)}
        if len(values) != 1:
            continue
        refs = set(_CHUNK_REFERENCE.findall(line))
        if len(refs) != 1:
            continue
        source = by_id.get(next(iter(refs)))
        if source is None:
            continue
        source_values = {_number(m.group(1)) for m in _TONNES.finditer(source.text)}
        if len(source_values) != 1:
            continue
        if values != source_values:
            return "quantity"
    return None
