"""A source-parsed draft contract cannot be simultaneously reported as missing."""
from __future__ import annotations

from types import SimpleNamespace

from src.modules.tender_operator_agent_demo.operator_recommendation import (
    build_provisional_operator_recommendation,
)
from src.modules.tender_operator_agent_demo.operator_services_analysis import (
    project_build_services_preliminary_analysis,
)
from src.modules.tender_operator_agent_demo.schemas import DemoRecommendationCode


def _preliminary(contract_text: str, service_items: list | None = None) -> dict:
    return project_build_services_preliminary_analysis(
        metadata={"procurement_id": "0151600003226000011"},
        documents=[],
        notice_text="Оказание услуг по технической поддержке порталов",
        contract_draft_text=contract_text,
        _collect_supply_items=lambda _docs: service_items or [],
        _service_subject_from_sources=lambda *args: "Техническая поддержка",
        _service_okpd2_from_sources=lambda *args: "62.02",
        _is_vehicle_maintenance_services=lambda *args: False,
        _extract_notice_price=lambda *args: "183333.50",
        _service_item_analysis_rows=lambda _items: [],
    )


def _recommendation(preliminary_analysis: dict) -> dict:
    recommendation, rationale = build_provisional_operator_recommendation(
        procurement_kind="services",
        core_complete=True,
        quote_files_present=False,
        economics=None,
        preliminary_analysis=preliminary_analysis,
        requirement_rows=[],
        supplier_questions_payload={"questions": []},
        risks_payload={"risks": []},
        economics_payload={"metrics": []},
    )
    assert recommendation["rationale"] == rationale
    return recommendation


def test_original_draft_present_does_not_trigger_get_draft_again() -> None:
    pre = _preliminary("Муниципальный контракт: исполнитель оказывает техническую поддержку.")
    assert pre["contract_draft_available"] is True
    assert pre["missing_documents"] == []
    assert "Получить проект контракта" not in " ".join(pre["next_actions"])
    assert "Проверить имеющийся проект контракта" in " ".join(pre["next_actions"])

    recommendation = _recommendation(pre)
    assert recommendation["recommendation"] == DemoRecommendationCode.MANUAL_REVIEW_REQUIRED.value
    text = " ".join(recommendation["rationale"])
    assert "Проект контракта найден" in text
    assert "после получения проекта контракта" not in text
    assert "Проект контракта, коммерческие входы" not in text
    assert "подтверждение ресурсов отсутствуют" in text


def test_missing_draft_preserves_fail_closed_gate() -> None:
    pre = _preliminary("")
    assert pre["contract_draft_available"] is False
    assert pre["missing_documents"] == ["draft_contract"]
    assert "Получить проект контракта" in " ".join(pre["next_actions"])
    recommendation = _recommendation(pre)
    assert recommendation["recommendation"] == DemoRecommendationCode.MANUAL_REVIEW_REQUIRED.value
    assert "после получения проекта контракта" in " ".join(recommendation["rationale"])


def test_unproven_boolean_never_claims_contract_exists() -> None:
    # Absence of source evidence does not become a positive assertion simply
    # because a free-form summary claims "contract supplied".
    recommendation = _recommendation({"contract_highlights": ["Документ доступен."]})
    assert recommendation["recommendation"] == DemoRecommendationCode.MANUAL_REVIEW_REQUIRED.value
    assert not any("Проект контракта найден" in x for x in recommendation["rationale"])


def test_no_structured_rows_cannot_claim_source_has_no_fixed_volume() -> None:
    # The actual EIS procurement 0151600003226000011 TЗ states 50 hours
    # despite the saved structural service-row extraction returning zero.
    pre = _preliminary("Муниципальный контракт; 01.01.2027–31.12.2027, 50 часов")
    assert pre["item_coverage"]["extracted_item_count"] == 0
    text = " ".join(pre["overview"] + pre["delivery_model"] + pre["next_actions"]
                    + [pre["supply_section_note"]])
    assert "структурирован" in text
    assert "в документации указаны единичные расценки" not in text.casefold()
    assert "фиксированный объём отдельных услуг не определён" not in text.casefold()
    assert "объём услуг определяется потребностью заказчика" not in text.casefold()
    assert "фиксированный объём по строкам не заявлен" not in text.casefold()
    assert "собраны из таблицы обоснования нмцк" not in text.casefold()


def test_service_quantity_from_attested_structured_row_not_discarded() -> None:
    item = SimpleNamespace(
        item_type="service",
        name="Техническая поддержка",
        quantity=50,
        unit="час",
        unit_original="час",
        unit_price=1000,
        source_document="Описание объекта закупки.docx",
        evidence_id="source-quantity-50",
    )
    pre = _preliminary("Проект контракта", [item])
    assert pre["item_coverage"]["extracted_item_count"] == 1
    assert "Количество по структурированным позициям извлечено" in " ".join(pre["overview"])
    assert "объём по строкам извлечён" in pre["extracted_fields"]
    assert "единичные расценки" in pre["extracted_fields"]
    assert "Получить проект контракта" not in " ".join(pre["next_actions"])
