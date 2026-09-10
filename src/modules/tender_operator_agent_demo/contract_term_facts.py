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
_SERVICE_PERIOD = re.compile(
    r"срок\s+начала\s+оказания\s+услуг\s+исполнителем\*{0,2}\s*[:|]\s*"
    r"(?P<start>[^;\n]{3,240})\s*;\s*"
    r"срок\s+окончания\s+оказания\s+услуг\s+исполнителем\*{0,2}\s*[:|]\s*"
    r"(?P<deadline>[^;\n]{3,240})",
    re.IGNORECASE,
)
_CONTRACT_END_DATE = re.compile(
    r"дата\s+окончания\s+исполнения\s+контракта\s*(?:[:|]|\t+)\s*"
    r"(?P<date>[^\n\t]{3,120})",
    re.IGNORECASE,
)
_PERFORMANCE_PLACE = re.compile(
    r"место\s+оказания\s+услуг\s*:\s*(?P<place>[^\n]{3,400})",
    re.IGNORECASE,
)
_WARRANTY_TERM = re.compile(
    r"срок\s*,?\s*на\s+который\s+предоставляется\s+гарантия[^—\n]{0,300}"
    r"[—-]\s*(?P<term>\d+\s+месяц(?:а|ев)?\s+с\s+даты\s+при[её]мки\s+оказанных\s+услуг)",
    re.IGNORECASE,
)
_WARRANTY_SECURITY = re.compile(
    r"требуется\s+обеспечение\s+исполнения\s+обязательств\s+по\s+предоставленной\s+"
    r"гарантии\s+качества\s+товаров?\s*,?\s*работ\s*,?\s*услуг\s*(?:[:|]|\t+)\s*"
    r"(?P<required>да|нет)",
    re.IGNORECASE,
)
_WARRANTY_SECURITY_NOT_REQUIRED = re.compile(
    r"требовани[ея]\s+к\s+обеспечению\s+гарантийных\s+обязательств\s+не\s+установлен[ыо]",
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


def _clean_preserving_period(value: str) -> str:
    return " ".join(value.split()).strip(" ;:")


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

    service_period = _SERVICE_PERIOD.search(text)
    if service_period:
        facts.extend(
            (
                _fact(
                    document,
                    "service_start",
                    _clean(service_period.group("start")),
                    service_period.start(),
                    service_period.end(),
                ),
                _fact(
                    document,
                    "service_deadline",
                    _clean(service_period.group("deadline")),
                    service_period.start(),
                    service_period.end(),
                ),
            )
        )

    contract_end_date = _CONTRACT_END_DATE.search(text)
    if contract_end_date:
        facts.append(
            _fact(
                document,
                "contract_end_date",
                _clean(contract_end_date.group("date")),
                contract_end_date.start(),
                contract_end_date.end(),
            )
        )

    warranty_security = _WARRANTY_SECURITY.search(text)
    if warranty_security:
        facts.append(
            _fact(
                document,
                "warranty_security_required",
                warranty_security.group("required").lower() == "да",
                warranty_security.start(),
                warranty_security.end(),
            )
        )
    else:
        warranty_security_absent = _WARRANTY_SECURITY_NOT_REQUIRED.search(text)
        if warranty_security_absent:
            facts.append(
                _fact(
                    document,
                    "warranty_security_required",
                    False,
                    warranty_security_absent.start(),
                    warranty_security_absent.end(),
                )
            )
    return facts


def _extract_from_technical_spec(document: Any) -> list[ContractTermFact]:
    text = str(getattr(document, "text", "") or "")
    if not text:
        return []

    facts: list[ContractTermFact] = []
    performance_place = _PERFORMANCE_PLACE.search(text)
    if performance_place:
        facts.append(
            _fact(
                document,
                "performance_place",
                _clean_preserving_period(performance_place.group("place")),
                performance_place.start(),
                performance_place.end(),
            )
        )

    warranty_term = _WARRANTY_TERM.search(text)
    if warranty_term:
        facts.append(
            _fact(
                document,
                "warranty_term",
                _clean(warranty_term.group("term")),
                warranty_term.start(),
                warranty_term.end(),
            )
        )
    return facts


def extract_contract_term_facts(documents: list[Any]) -> tuple[dict[str, ContractTermFact], list[str]]:
    """Return explicit contract and technical-spec facts, omitting conflicts."""
    candidates: dict[str, list[ContractTermFact]] = {}
    for document in documents:
        role = getattr(document, "role", None)
        if role == "contract_draft":
            extracted = _extract_from_contract(document)
        elif role == "technical_spec":
            extracted = _extract_from_technical_spec(document)
        else:
            extracted = []
        for fact in extracted:
            candidates.setdefault(fact.field, []).append(fact)

    agreed: dict[str, ContractTermFact] = {}
    conflicts: list[str] = []
    for field, facts in candidates.items():
        if len({repr(fact.value) for fact in facts}) == 1:
            agreed[field] = facts[0]
        else:
            conflicts.append(field)
    return agreed, sorted(conflicts)
