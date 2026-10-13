"""Product-owned economics intake bounds for tender upload requests.

No persistence, model calls, supplier contact or procurement decision here.
"""

from __future__ import annotations

from fastapi import HTTPException


def _sanitize_percent(value: float | None, *, default: float, field_name: str) -> float:
    numeric = default if value is None else float(value)
    if numeric < 0 or numeric > 95:
        raise HTTPException(status_code=400, detail=f"{field_name} must be between 0 and 95")
    return round(numeric, 2)


def _sanitize_delay_days(value: int | None, *, default: int) -> int:
    numeric = default if value is None else int(value)
    if numeric < 0 or numeric > 365:
        raise HTTPException(status_code=400, detail="payment_delay_days must be between 0 and 365")
    return numeric
