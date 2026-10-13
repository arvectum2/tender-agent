"""Product-owned deterministic procurement text helpers."""

from __future__ import annotations

import re


def project_collect_matches(
    text: str, patterns: tuple[str, ...], *, limit: int = 6
) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            value = " ".join(group for group in match.groups() if group)
            value = re.sub("\\s+", " ", value).strip(" .;,\n\t")
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(value)
            if len(found) >= limit:
                return found
    return found


def project_extract_notice_service_deadline(
    text: str, *, _extract_notice_timeline, _match_first_dotall
) -> str | None:
    return _extract_notice_timeline(
        text,
        (
            "Срок оказания услуг",
            "Сроки оказания услуг",
            "Период оказания услуг",
            "Срок выполнения работ",
        ),
        stop_markers=(
            "Место оказания услуг",
            "Место выполнения работ",
            "Условия оплаты",
            "Порядок оплаты",
            "Обеспечение исполнения контракта",
        ),
    ) or _match_first_dotall(
        text,
        (
            "<(?:\\w+:)?deliveryTerm>\\s*(.+?)\\s*</(?:\\w+:)?deliveryTerm>",
            "оказани[ея]\\s+услуг[^.\\n]{0,80}(в течение[^.\\n]+)",
            "оказани[ея]\\s+услуг[^.\\n]{0,80}(до\\s+\\d{1,2}\\s+[А-Яа-яЁё]+\\s+\\d{4}\\s+года)",
        ),
    )


def project_extract_inline_goods_field(
    text: str,
    labels: tuple[str, ...],
    *,
    stop_markers: tuple[str, ...],
    _cleanup_tabular_value,
) -> str | None:
    if not text:
        return None
    label_pattern = "|".join(re.escape(label) for label in labels)
    stop_pattern = "|".join(re.escape(marker) for marker in stop_markers)
    match = re.search(
        f"(?:{label_pattern})[^:\\n]*[:\\-]?\\s*(.+?)(?=\\s*(?:{stop_pattern})|\\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    return _cleanup_tabular_value(match.group(1))
