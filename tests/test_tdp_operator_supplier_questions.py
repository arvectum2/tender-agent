"""Behavior-preserving extraction of supplier questionnaire formatter."""

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.operator_supplier_questions import (
    normalize_supplier_questions,
)


def test_service_category_overrides_and_deduplicates():
    questions = [
        {"category": "price", "question": "english"},
        {"category": "price", "question": "english"},
        {"category": "unknown", "question": "custom"},
    ]
    result = normalize_supplier_questions(
        questions, "services", translate_user_text=str.upper
    )
    assert result == ["Какова стоимость услуг с НДС и без НДС?", "CUSTOM"]


def test_goods_translation_order_no_dedupe():
    questions = [
        {"category": "price", "question": "one"},
        {"category": "price", "question": "one"},
    ]
    assert normalize_supplier_questions(
        questions, "goods", translate_user_text=str.upper
    ) == ["ONE", "ONE"]


def test_service_limit_of_eight():
    questions = [{"category": "custom", "question": str(i)} for i in range(14)]
    assert (
        len(
            normalize_supplier_questions(
                questions, "services", translate_user_text=lambda x: x
            )
        )
        == 8
    )


def test_legacy_facade_behavior_matches_new_function(monkeypatch):
    monkeypatch.setattr(legacy, "_translate_user_text", str.upper)
    questions = [
        {"category": "delivery_time", "question": "x"},
        {"category": "other", "question": "y"},
    ]
    assert legacy._normalize_supplier_questions(
        questions, "services"
    ) == normalize_supplier_questions(
        questions, "services", translate_user_text=str.upper
    )
