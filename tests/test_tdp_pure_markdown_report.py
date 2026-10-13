"""Independent report presentation with frozen legacy compatibility entrypoints."""

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.operator_report_markdown import (
    preliminary_supply_section_markdown,
    preliminary_supply_section_title,
    render_operator_report_markdown,
)


def test_supply_section_helpers_remain_semantically_compatible():
    goods = {"spec_table": {"columns": ["Наименование"], "rows": []}}
    works = {"spec_table": {
        "columns": ["Блок работ / результат"],
        "rows": [{"№": 1, "Блок работ / результат": "Сайт",
                  "Что нужно сделать": "Разработка", "Источник": "ТЗ"}],
    }}
    for value in (goods, works):
        assert legacy._preliminary_analysis_supply_section_title(value) == preliminary_supply_section_title(value)
        assert legacy._preliminary_analysis_supply_section_markdown(value) == preliminary_supply_section_markdown(value)


def test_rendering_is_pure_and_compatible_with_old_entrypoint():
    metadata = {
        "run_id": "toa-test",
        "tender_title": "Разработка сайта",
        "tender_category": "44-ФЗ",
        "customer_name": "Заказчик",
        "status": "completed_with_warnings",
        "analysis_mode": "llm_tender_operator_provider",
        "files": [],
    }
    outputs = {
        "final_recommendation": {
            "recommendation": "manual_review_required",
            "rationale": ["Нужна проверка"],
            "manual_checks": ["Проверить первоисточники"],
        },
        "quotes_comparison": {"suppliers": []},
        "economics": {"metrics": [{"label": "НМЦК", "value": "unknown"}]},
        "requirements": {"preliminary_analysis": {"overview": ["Сайт"],
            "spec_table": {"columns": ["Наименование"], "rows": []}},
            "requirements": [{"title": "[LLM — проверить] Адаптивность",
                "source": "unverified_llm"}]},
    }
    before_meta = repr(metadata)
    before_outputs = repr(outputs)
    report = render_operator_report_markdown(
        metadata, outputs,
        inventory_builder=legacy._build_downloaded_documents_inventory,
        supply_title=preliminary_supply_section_title,
        supply_markdown=preliminary_supply_section_markdown,
    )
    assert report == legacy._build_report_markdown(metadata, outputs)
    assert "[LLM — проверить] Адаптивность" in report
    assert "ТКП не загружены" in report
    assert repr(metadata) == before_meta
    assert repr(outputs) == before_outputs
