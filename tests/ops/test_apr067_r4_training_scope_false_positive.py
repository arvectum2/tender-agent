"""Do not route 24/7 website-hosting services through an education template."""
from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy


def _scope_as_services(monkeypatch):
    monkeypatch.setattr(legacy, "_classify_procurement_scope", lambda *_: {
        "procurement_primary_scope": "services",
        "goods_extraction_applicable": False,
    })
    monkeypatch.setattr(legacy, "_collect_supply_items", lambda *_: [])


def test_hosting_with_incidental_staff_training_is_not_training_service(monkeypatch):
    _scope_as_services(monkeypatch)
    report = legacy._build_preliminary_procurement_analysis(
        metadata={"tender_title": "Услуги по технической поддержке и размещению сайта Управления"},
        documents=[],
        technical_spec_text=(
            "Техническая поддержка и размещение сайта. "
            "Услуги оказываются 24 часа в сутки 7 дней в неделю. "
            "Исполнитель обеспечивает обучение технических специалистов заказчика."
        ),
        contract_draft_text="Оплата по контракту в течение 7 рабочих дней.",
        notice_text="",
    )
    text = " ".join(report.get("overview", []) + report.get("next_actions", [])).lower()
    assert report["procurement_kind"] == "services"
    assert "преподавател" not in text
    assert "аудитори" not in text
    assert "учебные материалы" not in text
    assert "объём: 24 часа" not in text
    for unrelated in ("ремонтная база", "запасные части", "преподаватели", "нормо-час"):
        assert unrelated not in text
    assert report["domain_profile"] == "general_services"


def test_genuine_training_title_keeps_training_workflow(monkeypatch):
    _scope_as_services(monkeypatch)
    report = legacy._build_preliminary_procurement_analysis(
        metadata={"tender_title": "Оказание услуг по обучению специалистов"},
        documents=[],
        technical_spec_text="Форма обучения: очно-заочная. Объем программы 72 часа, 15 слушателей.",
        contract_draft_text="",
        notice_text="",
    )
    actions = " ".join(report.get("next_actions", [])).lower()
    assert report["procurement_kind"] == "services"
    assert "преподавател" in actions or "программу" in actions
