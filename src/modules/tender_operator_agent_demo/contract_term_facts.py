"""Source-bound extraction of explicit contract terms."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_PAYMENT_TERMS = re.compile(
    r"(?:порядок\s+и\s+сроки\s+оплаты|оплата)\s*[:|]\s*"
    r"(?P<payment>[^.\n]{3,240}?)\.\s*"
    r"срок\s+исполнения\s+обязательства\s+заказчиком\s*[:|]\s*"
    r"(?P<deadline>[^\n]{3,240})",
    re.IGNORECASE,
)
_PAYMENT_TABLE_CONDITION = re.compile(
    r"\bоплата\s+(?P<payment>100%\s+по\s+фактическому\s+объ[её]му)\b",
    re.IGNORECASE,
)
_PAYMENT_TABLE_DEADLINE = re.compile(
    r"срок\s+исполнения\s+обязательства\s+заказчиком\*{0,2}\s*"
    r"(?P<deadline>\d+\s+раб\.\s+дн\.\s+от\s+даты\s+подписания\s+"
    r"документа-предшественника\s+«[^»]+»)",
    re.IGNORECASE,
)
_ADVANCE_ABSENT = re.compile(
    r"\b(?:выплата\s+аванса|авансовый\s+плат[её]ж|аванс)\s+"
    r"(?:не\s+предусмотрен[ао]?|отсутствует)\b",
    re.IGNORECASE,
)
_ADVANCE_PROVIDED = re.compile(
    r"\b(?:авансовый\s+плат[её]ж|выплата\s+аванса|аванс)\s*"
    r"(?:составляет|устанавливается\s+в\s+размере|предусмотрен[ао]?)\s*"
    r"\d+(?:[.,]\d+)?\s*%",
    re.IGNORECASE,
)
_PERFORMANCE_SECURITY = re.compile(
    r"размер\s+обеспечения\s+исполнения\s+контракта\s*,?\s*%\s*"
    r"(?:от\s+нмцк\s*)?[|:]\s*(?P<percent>\d+(?:[.,]\d+)?)\b",
    re.IGNORECASE,
)
_PERFORMANCE_SECURITY_TABLE = re.compile(
    r"размер\s+обеспечения\s+исполнения\s+контракта\s*,?\s*%[^\n]*\n"
    r"\s*(?P<percent>\d+(?:[.,]\d+)?)\b",
    re.IGNORECASE,
)
_ACCEPTANCE_TERMS = re.compile(
    r"исполнитель\s*:\s*(?P<executor>[^\n]{3,240}?)\.\s*"
    r"заказчик\s*:\s*(?P<customer>[^\n]{3,240})",
    re.IGNORECASE,
)
_ACCEPTANCE_TABLE = re.compile(
    r"(?P<executor>\d+\s+раб\.\s+дн\.\s+от\s+даты\s+окончания\s+исполнения\s+обязательства)"
    r"(?:\s+в\s+данном\s+документе)?\t\s*подписание\s*\t\s*исполнитель\s*\n"
    r"[^\n]*?\t\s*(?P<customer>\d+\s+раб\.\s+дн\.\s+от\s+даты\s+получения\s+документа)"
    r"\t\s*подписание\s*\t\s*заказчик",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ContractTermFact:
    field: str
    value: Any
    source_document: str
    file_id: str
    locator: str
    excerpt: str
    confidence: str = "high"
    status: str = "ASSERTED"

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "value": self.value,
            "source_document": self.source_document,
            "file_id": self.file_id,
            "locator": self.locator,
            "excerpt": self.excerpt,
            "confidence": self.confidence,
            "status": self.status,
        }


def _clean(value: str) -> str:
    return " ".join(value.split()).strip(" .;:")


def _fact(document: Any, field: str, value: Any, start: int, end: int) -> ContractTermFact:
    text = str(getattr(document, "text", "") or "")
    line = text[:start].count("\n") + 1
    return ContractTermFact(
        field=field,
        value=value,
        source_document=str(getattr(document, "display_name", "")),
        file_id=str(getattr(document, "file_id", "")),
        locator=f"line:{line}",
        excerpt=_clean(text[start:end])[:500],
    )


def _extract_from_contract(document: Any) -> list[ContractTermFact]:
    text = str(getattr(document, "text", "") or "")
    if not text:
        return []

    facts: list[ContractTermFact] = []
    payment = _PAYMENT_TERMS.search(text)
    if payment:
        facts.append(
            _fact(
                document,
                "payment_terms",
                {
                    "payment": _clean(payment.group("payment")),
                    "deadline": _clean(payment.group("deadline")),
                },
                payment.start(),
                payment.end(),
            )
        )
    else:
        payment_condition = _PAYMENT_TABLE_CONDITION.search(text)
        payment_deadline = _PAYMENT_TABLE_DEADLINE.search(text)
        if payment_condition and payment_deadline and 0 <= payment_deadline.start() - payment_condition.end() <= 2000:
            facts.append(
                _fact(
                    document,
                    "payment_terms",
                    {
                        "payment": _clean(payment_condition.group("payment")),
                        "deadline": _clean(payment_deadline.group("deadline")),
                    },
                    payment_condition.start(),
                    payment_deadline.end(),
                )
            )

    advance_absent = _ADVANCE_ABSENT.search(text)
    advance_provided = _ADVANCE_PROVIDED.search(text)
    if advance_absent and not advance_provided:
        facts.append(_fact(document, "advance_payment", False, advance_absent.start(), advance_absent.end()))
    elif advance_provided and not advance_absent:
        facts.append(_fact(document, "advance_payment", True, advance_provided.start(), advance_provided.end()))

    security = _PERFORMANCE_SECURITY.search(text) or _PERFORMANCE_SECURITY_TABLE.search(text)
    if security:
        percent = float(security.group("percent").replace(",", "."))
        facts.append(
            _fact(
                document,
                "performance_security_percent",
                int(percent) if percent.is_integer() else percent,
                security.start(),
                security.end(),
            )
        )

    acceptance = _ACCEPTANCE_TERMS.search(text)
    if acceptance:
        facts.append(
            _fact(
                document,
                "acceptance_terms",
                {
                    "executor_submission": _clean(acceptance.group("executor")),
                    "customer_acceptance": _clean(acceptance.group("customer")),
                },
                acceptance.start(),
                acceptance.end(),
            )
        )
    else:
        acceptance_table = _ACCEPTANCE_TABLE.search(text)
        if acceptance_table:
            facts.append(
                _fact(
                    document,
                    "acceptance_terms",
                    {
                        "executor_submission": _clean(acceptance_table.group("executor")),
                        "customer_acceptance": _clean(acceptance_table.group("customer")),
                    },
                    acceptance_table.start(),
                    acceptance_table.end(),
                )
            )
    return facts


def extract_contract_term_facts(documents: list[Any]) -> tuple[dict[str, ContractTermFact], list[str]]:
    """Return explicit contract facts, omitting fields with source conflicts."""
    candidates: dict[str, list[ContractTermFact]] = {}
    for document in documents:
        if getattr(document, "role", None) != "contract_draft":
            continue
        for fact in _extract_from_contract(document):
            candidates.setdefault(fact.field, []).append(fact)

    agreed: dict[str, ContractTermFact] = {}
    conflicts: list[str] = []
    for field, facts in candidates.items():
        if len({repr(fact.value) for fact in facts}) == 1:
            agreed[field] = facts[0]
        else:
            conflicts.append(field)
    return agreed, sorted(conflicts)
