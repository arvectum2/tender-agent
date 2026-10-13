"""Product-owned notice and goods textual source projections."""

from __future__ import annotations

import re


def split_trailing_classification(
    raw_name: str | None,
    *,
    _cleanup_tabular_value,
    _TRAILING_CLASSIFICATION_RE,
    _is_ktru_or_okpd,
) -> tuple[str | None, str | None, str | None]:
    """Split a labelled classification suffix off a product name cell.

    Legacy NMCK layouts often place the identifier inside the name cell
    (``<name> КТРУ <code>``, ``<name> КТРУ-<code>``, ``<name> ОКПД 2-<code>``).
    Returns ``(clean_name, ktru, okpd2)``.  Only an explicit КТРУ/ОКПД label
    qualifies; an unlabeled trailing number is never interpreted, and the
    caller keeps the untouched original line in ``raw_fragment``.
    """

    cleaned = _cleanup_tabular_value(raw_name) or ""
    match = _TRAILING_CLASSIFICATION_RE.match(cleaned)
    if not match:
        return raw_name, None, None
    code = match.group("code")
    if not _is_ktru_or_okpd(code):
        return raw_name, None, None
    label = re.sub(r"\s+", "", match.group("label")).upper()
    name = (match.group("name") or "").strip(" -") or cleaned
    if label == "КТРУ":
        return name, code, None
    return name, None, code


def summarize_supply_characteristics(
    values: list[str], *, _cleanup_tabular_value, limit: int = 6
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _cleanup_tabular_value(value)
        if not cleaned:
            continue
        if cleaned.lower().startswith(
            ("требования к качеству", "требования к безопасности")
        ):
            continue
        if "__" in cleaned:
            continue
        if any(
            marker in cleaned.lower()
            for marker in ("заказчик", "поставщик", "м.п.", "при учете требований")
        ):
            continue
        normalized = cleaned.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result
