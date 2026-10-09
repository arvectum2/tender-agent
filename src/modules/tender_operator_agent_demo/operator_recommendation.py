"""Deterministic, human-gated procurement recommendation projection.

Presentation-only rule; no signing, submitting, sending RFQs or pretending
model-only requirements and risks are attested facts.
"""
from __future__ import annotations

from typing import Any

from src.modules.tender_operator_agent_demo.schemas import DemoRecommendationCode


def build_provisional_operator_recommendation(
    *,
    procurement_kind: str,
    core_complete: bool,
    quote_files_present: bool,
    economics: dict[str, Any] | None,
    preliminary_analysis: dict[str, Any],
    requirement_rows: list[dict[str, Any]],
    supplier_questions_payload: dict[str, Any],
    risks_payload: dict[str, Any],
    economics_payload: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    economics_ready = bool(economics and economics.get("economics_status") in {"conditionally_viable", "viable"})
    service_contract_missing = procurement_kind == "services" and bool(preliminary_analysis.get("missing_documents"))
    if core_complete and quote_files_present and economics_ready and not service_contract_missing:
        recommendation = DemoRecommendationCode.PARTICIPATE_CONDITIONALLY
        label = "участвовать условно"
        rationale = [
            "Базовый контролируемый путь раннера выполнен на локально загруженных документах.",
            "ТКП структурированы и сопоставлены в локальном deterministic parser слое.",
            "Экономика выглядит условно приемлемой, но решение всё ещё требует проверки оператором.",
            "Рекомендация остаётся предварительной и не заменяет решение человека.",
        ]
    elif procurement_kind == "goods":
        largest_position = preliminary_analysis.get("largest_position")
        recommendation = DemoRecommendationCode.MANUAL_REVIEW_REQUIRED
        label = "нужна ручная проверка"
        rationale = [
            "Документы извлечены, и агент выделил конкретные позиции поставки, количества и характеристики.",
            "Для участия нужно получить КП и подтверждение ГОСТ, сертификатов и сроков поставки по каждой позиции.",
            f"Особое внимание требует самая объёмная позиция: {largest_position}." if largest_position else "Нужно проверить наличие товара и срок поставки по всем позициям.",
            "Финальное решение возможно только после проверки цены, логистики и документов качества.",
        ]
    else:
        recommendation = DemoRecommendationCode.MANUAL_REVIEW_REQUIRED
        label = "нужна ручная проверка"
        rationale = [
            "Документы извлечены и дают предметное понимание закупки, но ценовая модель и подтверждение ресурсов отсутствуют.",
            "Проект контракта, коммерческие входы и подтверждение ресурсов отсутствуют или требуют проверки.",
            "Следующее действие должен подтвердить оператор после получения проекта контракта и внутренней оценки исполнения.",
        ]

    final_recommendation = {
        "recommendation": recommendation.value,
        "label": label,
        "rationale": rationale,
        "key_requirements": [item["title"] for item in requirement_rows[:4]] or ["Проверка комплектности документов"],
        "open_questions": supplier_questions_payload["questions"][:3],
        "risks": [item["risk"] for item in risks_payload["risks"][:4]],
        "economics": [f"{item['label']}: {item['value']}" for item in economics_payload["metrics"]],
        "manual_checks": [
            "Проверить исходные документы и роли файлов.",
            "Подтвердить RFQ и вопросы перед внешними коммуникациями.",
            "Проверить нормализацию Excel-таблиц и сопоставление позиций перед финансовым решением.",
            "Сделать финальное решение только после ручной проверки.",
        ],
    }

    return final_recommendation, rationale
