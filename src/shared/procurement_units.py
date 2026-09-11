from __future__ import annotations

from typing import Final


_TYPED_POSITION_UNIT_ALIASES: Final[dict[str, str]] = {
    "шт": "шт",
    "шт.": "шт",
    "штука": "шт",
    "штук": "шт",
    "упак": "упак",
    "упак.": "упак",
    "упаковка": "упак",
    "рул": "рул.",
    "рул.": "рул.",
}


def canonicalize_typed_position_unit(value: str | None) -> str | None:
    """Return the canonical unit token used by typed procurement positions.

    This is deliberately narrower than source-format normalization. Source
    readers may accept many aliases, but the final typed positions contract
    uses one deterministic spelling for explicitly governed equivalents.
    Unknown unit tokens are preserved rather than guessed.
    """

    if value is None:
        return None
    cleaned = " ".join(str(value).split()).strip()
    if not cleaned:
        return None
    return _TYPED_POSITION_UNIT_ALIASES.get(cleaned.lower(), cleaned)
