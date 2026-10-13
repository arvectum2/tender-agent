"""Procurement recommendation projection remains human-gated across branches."""

from __future__ import annotations

from src.modules.tender_operator_agent_demo.operator_recommendation import (
    build_provisional_operator_recommendation,
)
from src.modules.tender_operator_agent_demo.schemas import DemoRecommendationCode


def base(**changes):
    payload = {
        "procurement_kind": "services",
        "core_complete": False,
        "quote_files_present": False,
        "economics": None,
        "preliminary_analysis": {},
        "requirement_rows": [{"title": "[LLM — проверить] Прототип"}],
        "supplier_questions_payload": {"questions": ["Сроки?"]},
        "risks_payload": {"risks": [{"risk": "[LLM — проверить] Штраф"}]},
        "economics_payload": {"metrics": [{"label": "НМЦК", "value": "1 млн ₽"}]},
    }
    payload.update(changes)
    return build_provisional_operator_recommendation(**payload)


def test_unverified_model_requirements_cannot_trigger_auto_go():
    report, rationale = base()
    assert report["recommendation"] == DemoRecommendationCode.MANUAL_REVIEW_REQUIRED.value
    assert report["rationale"] == rationale
    assert "Проверить исходные документы и роли файлов." in report["manual_checks"]
    assert report["key_requirements"] == ["[LLM — проверить] Прототип"]
    assert report["risks"] == ["[LLM — проверить] Штраф"]


def test_conditional_business_option_remains_human_approved():
    report, rationale = base(
        core_complete=True,
        quote_files_present=True,
        economics={"economics_status": "viable"},
        preliminary_analysis={"missing_documents": []},
    )
    assert report["recommendation"] == DemoRecommendationCode.PARTICIPATE_CONDITIONALLY.value
    assert "проверки оператором" in " ".join(rationale)
    assert "Сделать финальное решение только после ручной проверки." in report["manual_checks"]


def test_missing_service_contract_blocks_conditional_option():
    report, _ = base(
        core_complete=True,
        quote_files_present=True,
        economics={"economics_status": "viable"},
        preliminary_analysis={"missing_documents": ["draft_contract"]},
    )
    assert report["recommendation"] == DemoRecommendationCode.MANUAL_REVIEW_REQUIRED.value


def test_goods_fallback_preserves_largest_position_and_review():
    report, rationale = base(
        procurement_kind="goods",
        preliminary_analysis={"largest_position": "Лот 1 — 12 штук"},
    )
    assert report["recommendation"] == DemoRecommendationCode.MANUAL_REVIEW_REQUIRED.value
    assert any("Лот 1 — 12 штук" in line for line in rationale)


def test_empty_requirement_input_does_not_invent_specific_requirement():
    report, _ = base(requirement_rows=[], supplier_questions_payload={"questions": []}, risks_payload={"risks": []}, economics_payload={"metrics": []})
    assert report["key_requirements"] == ["Проверка комплектности документов"]
    assert report["open_questions"] == []
    assert report["risks"] == []
