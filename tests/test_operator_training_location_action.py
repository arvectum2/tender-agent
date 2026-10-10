"""Training-service next actions must never invent a city."""

from __future__ import annotations

import pytest

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.operator_training_location_action import (
    build_training_location_action,
)


@pytest.mark.parametrize("location", ["г. Казань", "город Москва", "пос. Северный"])
def test_explicit_location_produces_source_referenced_action_not_hardcoded_city(location):
    action = build_training_location_action(location, "Очно-заочная")
    assert "по месту оказания услуг" in action
    assert "указанному в ТЗ" in action
    assert location in action
    assert "Хабаровск" not in action


def test_training_format_without_location_requires_clarification():
    action = build_training_location_action(None, "Очно-заочная")
    assert "Уточнить" in action
    assert "место проведения" in action
    assert "Хабаровск" not in action


def test_unknown_location_and_format_remain_unconfirmed():
    action = build_training_location_action(None, None)
    assert action == "Подтвердить реальный формат оказания услуг и локацию исполнения."


def test_actual_source_mention_of_khabarovsk_is_preserved_in_delivery_fact():
    value = legacy._rewrite_delivery_model_item(
        "Очная часть проводится в городе Хабаровске", "services"
    )
    assert "Хабаровск" in value


def test_training_preliminary_report_never_invents_khabarovsk(monkeypatch):
    monkeypatch.setattr(
        legacy,
        "_classify_procurement_scope",
        lambda *_: {
            "procurement_primary_scope": "services",
            "goods_extraction_applicable": False,
        },
    )
    monkeypatch.setattr(legacy, "_collect_supply_items", lambda *_: [])
    actual = legacy._build_preliminary_procurement_analysis(
        metadata={"tender_title": "Оказание услуг по обучению"},
        documents=[],
        technical_spec_text=(
            "Оказание услуг по обучению. Форма обучения: Очно-заочная.\n"
            "3. Место оказания услуг: г. Казань\n"
            "4. Срок выполнения"
        ),
        contract_draft_text="",
        notice_text="",
    )
    assert actual["procurement_kind"] == "services"
    assert not any("Хабаровск" in str(x) for x in actual["next_actions"])
