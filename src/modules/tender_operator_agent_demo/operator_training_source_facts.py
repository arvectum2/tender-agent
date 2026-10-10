"""Source-derived candidates for Tender Agent training-service preliminary analysis.

These extraction heuristics provide candidates, not authenticated statements
about EIS documents. External matchers are injected by the legacy caller.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, NamedTuple


class TrainingCandidateFacts(NamedTuple):
    service_subject: Any
    training_format: Any
    hours: Any
    listeners: Any
    service_deadline: Any
    location: Any
    initial_price: Any
    payment_terms: Any
    execution_security: Any
    execution_security_percent: Any
    execution_security_amount: Any
    acceptance_window: Any
    unilateral_termination: Any


def extract_training_candidate_facts(
    metadata: dict[str, Any],
    tz_text: str,
    contract_text: str,
    notice: str,
    *,
    _match_first: Callable[..., Any],
    _extract_notice_service_deadline: Callable[..., Any],
    _cleanup_tabular_value: Callable[..., Any],
    _extract_notice_price: Callable[..., Any],
    _match_first_dotall: Callable[..., Any],
) -> TrainingCandidateFacts:
    service_subject = _match_first(
        tz_text,
        (
            r"1\.\s*Наименование и описание услуг:\s*(.+?)(?:\n\d+\.|\Z)",
            r"Объект закупки\s*[:\-]?\s*(.+?)(?:\n|$)",
            r"Описание объекта закупки\s*[:\-]?\s*(.+?)(?:\n|$)",
        ),
    ) or metadata.get("tender_title")
    training_format = _match_first(
        tz_text,
        (
            r"\b(Очно-заочная(?:\s*\([^)]+\))?)\b",
            r"\b(Очная(?:\s*\([^)]+\))?)\b",
            r"\b(Заочная(?:\s*\([^)]+\))?)\b",
            r"Форма обучения\s*\n\s*([^\n]+)",
            r"Форма обучения\s*[:\-]?\s*([^\n]+)",
        ),
    )
    hours = _match_first(
        tz_text,
        (
            r"(\d+\s*час(?:ов|а)?)",
        ),
    )
    listeners = _match_first(
        tz_text,
        (
            r"\b\d+\s*час(?:ов|а)?\s*\n\s*(\d+)\b",
            r"Кол-во слушателей.*?\n.*?\n.*?\n.*?\n.*?\n\s*(\d+)",
            r"(\d+)\s*\(?[а-я]*\)?\s*человек",
            r"слушател[^\n]*?(\d+)",
        ),
    )
    service_deadline = _match_first(
        tz_text,
        (
            r"не позднее\s+(\d{1,2}\s+[А-Яа-яЁё]+\s+\d{4}\s+года)",
            r"не позднее\s+([^.\\n]+)",
            r"Сроки оказания Услуг\s*[–-]\s*([^.\\n]+)",
        ),
    ) or _extract_notice_service_deadline(notice)
    service_deadline = _cleanup_tabular_value(service_deadline) or service_deadline
    location = _match_first(
        tz_text,
        (
            r"3\.\s*Место оказания услуг:\s*(.+?)(?:\n\d+\.|\Z)",
            r"Место оказания Услуг:\s*(.+?)(?:\n\d+\.|\Z)",
        ),
    )
    initial_price = _extract_notice_price(metadata, notice, contract_text)
    payment_terms = _match_first(
        contract_text,
        (
            r"в течение\s+(\d+\s*\([^)]+\)\s*рабочих дней[^.]+документа о приемке)",
            r"в течение\s+(\d+\s*рабочих дней[^.]+документа о приемке)",
            r"Оплата[^.]*?в течение\s+([^.]+)",
        ),
    )
    execution_security = _match_first(
        contract_text + "\n" + notice,
        (
            r"обеспечени[ея]\s+исполнения\s+контракта[^.]{0,120}",
        ),
    )
    if not execution_security and "исполнения контракта" in contract_text.lower() and "обеспеч" in contract_text.lower():
        execution_security = "обеспечение исполнения контракта"
    execution_security_percent = _match_first_dotall(
        notice + "\n" + contract_text,
        (
            r"contractGuarantee[\s\S]{0,600}?<(?:\w+:)?part>(\d+(?:[.,]\d+)?)</(?:\w+:)?part>",
            r"обеспечени[ея]\s+исполнения\s+контракта[^%\n]{0,200}?(\d+(?:[.,]\d+)?)\s*%",
        ),
    )
    execution_security_amount = _match_first_dotall(
        notice + "\n" + contract_text,
        (
            r"contractGuarantee[\s\S]{0,600}?<(?:\w+:)?amount>(\d+(?:[.,]\d+)?)</(?:\w+:)?amount>",
            r"обеспечени[ея]\s+исполнения\s+контракта[^\\d]{0,200}?([\d\s]+(?:[.,]\d+)?)\s*руб",
        ),
    )
    acceptance_window = _match_first(
        contract_text,
        (
            r"Не позднее\s+(\d+\s*\([^)]+\)\s*рабочих дней[^.]+документа о приемке)",
            r"Не позднее\s+(\d+\s*рабочих дней[^.]+документа о приемке)",
        ),
    )
    unilateral_termination = _match_first(
        contract_text,
        (
            r"(Заказчик вправе принять решение об одностороннем отказе[^.]+)",
            r"(одностороннем отказе от исполнения Контракта[^.]+)",
        ),
    )

    return TrainingCandidateFacts(
        service_subject=service_subject,
        training_format=training_format,
        hours=hours,
        listeners=listeners,
        service_deadline=service_deadline,
        location=location,
        initial_price=initial_price,
        payment_terms=payment_terms,
        execution_security=execution_security,
        execution_security_percent=execution_security_percent,
        execution_security_amount=execution_security_amount,
        acceptance_window=acceptance_window,
        unilateral_termination=unilateral_termination,
    )
