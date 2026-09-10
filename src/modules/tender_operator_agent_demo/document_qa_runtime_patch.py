"""DOCUMENT-QA-001: source-bound hardening for the first real benchmark baseline.

The historical Tender Operator demo contains software/integration templates that
were originally written for a healthcare procurement.  Those templates must not
become facts, questions, or risks for unrelated software procurements.  This
patch keeps the legacy pipeline stable while making its generated operator
content source-relative and fixing ambiguous customer extraction.
"""
from __future__ import annotations

import html
import re
from copy import deepcopy
from typing import Any

from src.modules.tender_operator_agent_demo import upload_service_legacy as _legacy

_INSTALLED = False
_ORIGINAL_REQUIREMENTS: Any = None
_ORIGINAL_OUTPUT_PAYLOADS: Any = None

_SOFTWARE_SCOPES = {"mixed", "software_modification", "integration", "license"}

# Contract-party role labels that act as field boundaries when followed by ":".
# These must not leak into an extracted customer candidate.
_CUSTOMER_BOUNDARY_RE = re.compile(
    r"\s+(?:Исполнитель|Поставщик|Подрядчик)\s*:",
)


def _clean_explicit_customer_value(value: str) -> str:
    """Trim trailing contract-party labels from an explicit customer candidate.

    When DOCX/table extraction places the next signature-party field on the
    same logical line, the ``Заказчик:`` pattern may consume:

        <actual customer> Исполнитель:________________

    This helper strips such trailing role-label boundaries while preserving
    legitimate organization names that happen to contain the role word.
    """
    cleaned = _CUSTOMER_BOUNDARY_RE.split(value, maxsplit=1)[0]
    return cleaned.strip(" ,.;:")


def _document_text(documents: list[Any]) -> str:
    return "\n".join(str(getattr(document, "text", "") or "") for document in documents).lower()


def _document_text_for_source(documents: list[Any], source: str | None) -> str:
    if not source:
        return _document_text(documents)
    for document in documents:
        if str(getattr(document, "display_name", "")) == source:
            return str(getattr(document, "text", "") or "").lower()
    return _document_text(documents)


def _extract_explicit_customer_name(*texts: str | None) -> str | None:
    """Return only a role-explicit customer; never infer it from arbitrary fullName.

    EIS bundles may contain many ``fullName`` nodes (organizer, customer,
    signatory organization, etc.).  The legacy global ``fullName`` fallback was
    therefore able to turn an organizer into the customer.  Prefer a scoped
    ``customer`` node, an explicit ``customerName`` element, or a contract/text
    phrase that names the party as ``Заказчик``.  Otherwise fail closed.
    """

    customer_block = re.compile(
        r"<(?:[A-Za-z_][\w.-]*:)?customer\b[^>]*>(.*?)</(?:[A-Za-z_][\w.-]*:)?customer>",
        re.IGNORECASE | re.DOTALL,
    )
    customer_name_tag = re.compile(
        r"<(?:[A-Za-z_][\w.-]*:)?customerName\b[^>]*>([^<]+)</(?:[A-Za-z_][\w.-]*:)?customerName>",
        re.IGNORECASE,
    )
    scoped_name_tag = re.compile(
        r"<(?:[A-Za-z_][\w.-]*:)?(?:fullName|name)\b[^>]*>([^<]+)</(?:[A-Za-z_][\w.-]*:)?(?:fullName|name)>",
        re.IGNORECASE,
    )
    text_patterns = (
        re.compile(r"(?im)^\s*Заказчик(?:а|у|ом|е)?\s*[:\-]\s*([^\n]{4,240})"),
        re.compile(
            r"(?im)^\s*([А-ЯA-Z][^\n]{3,220}?)\s*,?\s+именуем(?:ое|ая|ый|ые)?[^\n]{0,80}[«\"]Заказчик[»\"]"
        ),
    )

    for raw in texts:
        text = str(raw or "")
        if not text.strip():
            continue

        direct = customer_name_tag.search(text)
        if direct:
            value = _clean_explicit_customer_value(html.unescape(direct.group(1)).strip())
            if value:
                return value

        for block_match in customer_block.finditer(text):
            scoped = scoped_name_tag.search(block_match.group(1))
            if scoped:
                value = _clean_explicit_customer_value(html.unescape(scoped.group(1)).strip())
                if value:
                    return value

        for pattern in text_patterns:
            match = pattern.search(text)
            if match:
                value = _clean_explicit_customer_value(
                    " ".join(html.unescape(match.group(1)).split()).strip(" ,.;")
                )
                if value:
                    return value
    return None


def _build_source_bound_requirements(
    documents: list[Any], procurement_kind: str
) -> list[dict[str, str]]:
    rows = list(_ORIGINAL_REQUIREMENTS(documents, procurement_kind))
    if procurement_kind not in _SOFTWARE_SCOPES:
        return rows

    hardened: list[dict[str, str]] = []
    for raw_row in rows:
        row = deepcopy(raw_row)
        title = str(row.get("title") or "")
        source_text = _document_text_for_source(documents, row.get("source"))

        if title == "Модификация ПК «Здравоохранение»":
            row["title"] = "Модификация программного комплекса"
        elif title == "Требования к обработке медицинских и персональных данных":
            row["title"] = (
                title if "медицинск" in source_text else "Требования к обработке персональных данных"
            )
        elif title == "Интеграция с ЕРН через СМЭВ":
            has_ern = bool(re.search(r"(?<![а-яё])ерн(?![а-яё])", source_text))
            has_smev = "смэв" in source_text or "межведомственного электронного взаимодействия" in source_text
            if has_ern and has_smev:
                pass
            elif has_smev:
                row["title"] = "Интеграция через СМЭВ"
            elif has_ern:
                row["title"] = "Интеграция с ЕРН"
            else:
                # A legacy keyword match must not manufacture named systems.
                continue
        elif title == "Получение данных об участниках СВО из витрины Минобороны":
            has_svo = bool(re.search(r"(?<![а-яё])сво(?![а-яё])", source_text))
            has_mod_source = "министерств" in source_text and "оборон" in source_text
            if not (has_svo and has_mod_source):
                continue
        elif title == "Передача лицензии и прав на обновленный модуль":
            row["title"] = "Лицензионные требования и передача прав"
        elif title == "Требования к приемке результатов работ":
            row["title"] = "Требования к приемке результатов"
        elif title == "Сроки и этапность выполнения работ":
            row["title"] = "Сроки и этапность исполнения"

        hardened.append(row)
    return hardened[:12]


def _build_source_bound_questions(procurement_kind: str, documents: list[Any]) -> list[str]:
    if procurement_kind not in _SOFTWARE_SCOPES:
        return _legacy_question_fallback(procurement_kind, documents)
    return [
        "Какие внешние системы, интерфейсы и сценарии интеграции прямо требуются документацией?",
        "Кто предоставляет необходимые доступы, учетные данные и тестовые контуры?",
        "Какие требования к данным, информационной безопасности и журналированию прямо установлены документами?",
        "Входит ли в объем интеграционное тестирование и сопровождение приемки?",
        "Какие результаты должны быть переданы заказчику: программные компоненты, документация, лицензии или права?",
        "Какие критерии приемки и ограничения по срокам подтверждены первичными документами?",
    ]


def _legacy_question_fallback(procurement_kind: str, documents: list[Any]) -> list[str]:
    # Rebound during install to avoid recursion after monkey-patching.
    return _ORIGINAL_QUESTIONS(procurement_kind, documents)


def _build_source_bound_risks(
    procurement_kind: str, documents: list[Any], contract_text: str
) -> list[dict[str, str]]:
    if procurement_kind not in _SOFTWARE_SCOPES:
        return _ORIGINAL_RISKS(procurement_kind, documents, contract_text)

    source_text = _document_text(documents) + "\n" + str(contract_text or "").lower()
    risks: list[dict[str, str]] = []
    if any(marker in source_text for marker in ("интеграц", " api ", "интерфейс", "внешн")):
        risks.append(
            {
                "clause": "Интеграционные требования требуют проверки",
                "classification": "market_standard_harsh_term",
                "impact": "Объем, интерфейсы и критерии приемки интеграций нужно сверить с первичными документами.",
                "mitigation": "Зафиксировать подтвержденные интерфейсы, сценарии, доступы и критерии приемки по источникам закупки.",
            }
        )
    if "персональн" in source_text:
        risks.append(
            {
                "clause": "Требования к обработке персональных данных требуют проверки",
                "classification": "market_standard_harsh_term",
                "impact": "Условия обработки и размещения персональных данных должны соответствовать документации закупки.",
                "mitigation": "Сверить контур размещения, роли доступа и требования к защите данных с первичными документами.",
            }
        )
    if any(marker in source_text for marker in ("лиценз", "исключительн", "передач")):
        risks.append(
            {
                "clause": "Лицензионные условия и права требуют проверки",
                "classification": "market_standard_harsh_term",
                "impact": "Объем предоставляемых прав должен быть подтвержден условиями закупки и проекта контракта.",
                "mitigation": "Сверить вид лицензии, право реализации и объем передаваемых прав по первичным документам.",
            }
        )
    return risks or [
        {
            "clause": "Недостаточно подтвержденных оснований для автоматической классификации рисков",
            "classification": "market_standard_harsh_term",
            "impact": "Материальные риски нельзя надежно вывести без дополнительной проверки первичных документов.",
            "mitigation": "Проверить техническое задание и проект контракта вручную.",
        }
    ]


def _build_source_bound_rfq_sections(procurement_kind: str) -> list[str]:
    if procurement_kind not in _SOFTWARE_SCOPES:
        return _ORIGINAL_RFQ_SECTIONS(procurement_kind)
    return [
        "Опыт выполнения сопоставимых программных работ и интеграций",
        "Команда проекта и роли по разработке, интеграции, тестированию и ИБ",
        "Оценка трудоемкости по подтвержденным функциональным блокам и этапам",
        "Подход к интеграциям и доступам, прямо указанным в документации",
        "Состав передаваемых результатов, лицензий, прав и документации",
        "Стоимость по подтвержденным блокам работ, тестированию и сопровождению",
    ]


def _unsupported_domain_markers(source_text: str) -> tuple[str, ...]:
    rules = (
        ("медицин", "медицин"),
        ("здравоохран", "здравоохран"),
        ("сэмд", "сэмд"),
        ("ипра", "ипра"),
        ("смэв", "смэв"),
        ("ерн", "ерн"),
        ("минобороны", "минобороны"),
        ("министерства обороны", "министерства обороны"),
        ("витрин", "витрин"),
    )
    return tuple(output_marker for output_marker, source_marker in rules if source_marker not in source_text)


def _contains_unsupported_marker(value: Any, markers: tuple[str, ...]) -> bool:
    text = str(value or "").lower()
    return any(marker in text for marker in markers)


def _filter_generated_list(value: Any, markers: tuple[str, ...]) -> Any:
    if not isinstance(value, list):
        return value
    return [item for item in value if not _contains_unsupported_marker(item, markers)]


def _guard_operator_output(
    outputs: dict[str, Any], *, metadata: dict[str, Any], documents: list[Any]
) -> dict[str, Any]:
    source_text = _document_text(documents)
    markers = _unsupported_domain_markers(source_text)
    if not markers:
        return outputs

    recommendation = outputs.get("final_recommendation")
    if isinstance(recommendation, dict):
        for key in ("key_requirements", "open_questions", "risks"):
            recommendation[key] = _filter_generated_list(recommendation.get(key), markers)

    rfq = outputs.get("rfq_draft")
    if isinstance(rfq, dict):
        rfq["sections"] = _filter_generated_list(rfq.get("sections"), markers)

    return outputs


def _build_output_payloads(*args: Any, **kwargs: Any) -> dict[str, Any]:
    outputs = _ORIGINAL_OUTPUT_PAYLOADS(*args, **kwargs)
    metadata = kwargs.get("metadata")
    documents = kwargs.get("documents")
    if not isinstance(outputs, dict) or not isinstance(metadata, dict) or not isinstance(documents, list):
        return outputs
    return _guard_operator_output(outputs, metadata=metadata, documents=documents)


def install() -> None:
    """Install the DOCUMENT-QA hardening as the final legacy runtime patch."""
    global _INSTALLED
    global _ORIGINAL_REQUIREMENTS, _ORIGINAL_QUESTIONS, _ORIGINAL_RISKS
    global _ORIGINAL_RFQ_SECTIONS, _ORIGINAL_OUTPUT_PAYLOADS
    if _INSTALLED:
        return

    _ORIGINAL_REQUIREMENTS = _legacy._build_document_grounded_requirements
    _ORIGINAL_QUESTIONS = _legacy._build_document_grounded_questions
    _ORIGINAL_RISKS = _legacy._build_document_grounded_risks
    _ORIGINAL_RFQ_SECTIONS = _legacy._build_document_grounded_rfq_sections
    _ORIGINAL_OUTPUT_PAYLOADS = _legacy._build_output_payloads

    _legacy._extract_customer_name_from_text = _extract_explicit_customer_name
    _legacy._build_document_grounded_requirements = _build_source_bound_requirements
    _legacy._build_document_grounded_questions = _build_source_bound_questions
    _legacy._build_document_grounded_risks = _build_source_bound_risks
    _legacy._build_document_grounded_rfq_sections = _build_source_bound_rfq_sections
    _legacy._build_output_payloads = _build_output_payloads
    _INSTALLED = True
