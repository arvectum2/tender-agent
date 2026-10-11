"""Product-owned notice and goods textual source projections."""

from __future__ import annotations

from typing import Any


def extract_notice_price(
    metadata: dict[str, Any], *texts: str, _format_money_value, _match_first_dotall
) -> str | None:
    procurement = (
        metadata.get("procurement")
        if isinstance(metadata.get("procurement"), dict)
        else {}
    )
    for candidate in (
        procurement.get("initial_price"),
        metadata.get("initial_price"),
    ):
        formatted = _format_money_value(candidate)
        if formatted:
            return formatted
    combined = "\n".join(text for text in texts if text)
    if not combined:
        return None
    raw_value = _match_first_dotall(
        combined,
        (
            r"<(?:\w+:)?maxPrice>\s*([\d\s]+(?:[.,]\d+)?)\s*</(?:\w+:)?maxPrice>",
            r"Начальная\s*\(максимальная\)\s*цена\s*(?:контракта|договора)?\D{0,80}([\d\s]+(?:[.,]\d+)?)\s*(?:руб|₽|RUB)",
            r"\bНМЦК\b\D{0,40}([\d\s]+(?:[.,]\d+)?)\s*(?:руб|₽|RUB)",
            r"Цена\s+контракта\D{0,40}([\d\s]+(?:[.,]\d+)?)\s*(?:руб|₽|RUB)",
        ),
    )
    return _format_money_value(raw_value)


def extract_notice_delivery_deadline(
    text: str, *, _extract_notice_timeline, _match_first_dotall
) -> str | None:
    return _extract_notice_timeline(
        text,
        (
            "Срок поставки",
            "Сроки поставки",
            "Срок поставки товара",
            "Сроки поставки товара",
            "Период поставки",
        ),
        stop_markers=(
            "Место поставки",
            "Адрес поставки",
            "Условия оплаты",
            "Порядок оплаты",
            "Условия поставки",
            "Порядок поставки",
            "Обеспечение исполнения контракта",
        ),
    ) or _match_first_dotall(
        text,
        (
            r"<(?:\w+:)?deliveryTerm>\s*(.+?)\s*</(?:\w+:)?deliveryTerm>",
            r"поставка[^.\n]{0,80}(в течение[^.\n]+)",
            r"поставка[^.\n]{0,80}(до\s+\d{1,2}\s+[А-Яа-яЁё]+\s+\d{4}\s+года)",
        ),
    )
