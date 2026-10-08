"""Detect explicit generated numeric-unit values absent from supplied source text.

Conservative error gate only; not semantic entailment, calculations or lot binding.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from src.tender_research.rag.search_types import RagSearchHit

_VALUE_UNIT = re.compile(
    r"(?<![\w.])(\d[\d \u00a0]*(?:[.,]\d+)?)\s*"
    r"(тонн(?:а|ы)?|т\b|килограмм[а-я]*|кг\b|литр[а-я]*|л\b|штук[а-я]*|шт\b|"
    r"руб(?:лей|ля|ль|\.)?|₽|%)",
    re.IGNORECASE,
)
_UNIT_KIND = {
    "%": "percent",
    "₽": "rub",
    "т": "tonnes",
    "кг": "kilograms",
    "л": "litres",
    "шт": "pieces",
}


def _kind(token: str) -> str:
    low = token.casefold().rstrip(".")
    if low in _UNIT_KIND:
        return _UNIT_KIND[low]
    for name, kind in (
        ("тонн", "tonnes"),
        ("килограмм", "kilograms"),
        ("литр", "litres"),
        ("штук", "pieces"),
        ("руб", "rub"),
    ):
        if low.startswith(name):
            return kind
    return low


def _observed_values(text: str) -> set[tuple[str, str]]:
    result = set()
    for match in _VALUE_UNIT.finditer(text):
        raw = match.group(1).replace(" ", "").replace("\u00a0", "").replace(",", ".")
        try:
            numeric = format(float(raw), ".12g")
        except ValueError:
            continue
        result.add((_kind(match.group(2)), numeric))
    return result


def unsupported_explicit_numeric_claim(
    answer: str, contexts: Sequence[RagSearchHit]
) -> str | None:
    """Return a unit type if a generated explicit unit-value is absent from supplied text.

    Does not infer correctness, scope, currency conversions, lot applicability,
    document revisions, arithmetic, or missing numeric facts.
    """
    source_values = set()
    for context in contexts:
        source_values.update(_observed_values(context.text))
    for kind, value in _observed_values(answer):
        if (kind, value) not in source_values:
            return kind
    return None
