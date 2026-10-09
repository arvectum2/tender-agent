"""One domain validator for source-bound 44-FZ EIS notice facts.

Does not fetch files, infer values from text headings or mutate frozen R7
outputs. Consumers must separately verify the exact original XML file/registry.
"""

from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal, InvalidOperation

EIS_NOTICE_FACT_TAGS: tuple[tuple[str, str], ...] = (
    ("procurement_title", "purchaseObjectInfo"),
    ("application_deadline", "endDT"),
    ("nmck", "maxPrice"),
)


def verified_eis_fact_value(key: str, excerpt: str) -> str | float | None:
    """Validate an exact XML element excerpt without inventing missing facts."""
    if not isinstance(excerpt, str) or not 0 < len(excerpt.strip()) <= 4096:
        return None
    if key == "procurement_title":
        return excerpt
    if key == "application_deadline":
        try:
            parsed = datetime.fromisoformat(excerpt)
        except ValueError:
            return None
        return excerpt if parsed.tzinfo is not None and parsed.utcoffset() is not None else None
    if key == "nmck":
        try:
            value = Decimal(excerpt)
        except InvalidOperation:
            return None
        if not value.is_finite() or value < 0:
            return None
        try:
            result = float(value)
        except (ValueError, OverflowError):
            return None
        return result if math.isfinite(result) else None
    return None
