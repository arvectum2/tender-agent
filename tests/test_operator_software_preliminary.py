"""Contract regression for the extracted software/integration report projection."""

from __future__ import annotations

from src.modules.tender_operator_agent_demo import upload_service as guarded_facade
from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.operator_software_preliminary import (
    build_software_preliminary_analysis,
)


def _direct_projection(kind: str = "integration", *, rows=None, price=None, title=None):
    seen: list[str] = []

    def work_rows(_documents):
        seen.append("work_rows")
        return [] if rows is None else rows

    def match_first(_text, _patterns):
        return None

    result = build_software_preliminary_analysis(
        {"tender_title": title, "procurement": {"delivery_term": "12 месяцев"}},
        [],
        "Сопровождение информационной системы",
        "Работы по интеграции",
        "В проекте контракта предусмотрена приемка",
        "Извещение о закупке",
        {"procurement_primary_scope": kind, "goods_extraction_applicable": False},
        kind,
        _build_software_work_rows=work_rows,
        _extract_notice_price=lambda *_: price,
        _extract_notice_service_deadline=lambda *_: None,
        _extract_notice_delivery_deadline=lambda *_: None,
        _cleanup_tabular_value=lambda x: x,
        _match_first=match_first,
        _dedupe_text_items=lambda xs: list(dict.fromkeys(x for x in xs if x)),
    )
    assert seen == ["work_rows"]
    return result


def test_no_source_rows_does_not_create_software_spec_rows():
    result = _direct_projection(kind="software_modification", title="Доработка ПО")
    assert result["procurement_kind"] == "software_modification"
    assert result["spec_table"]["rows"] == []
    assert result["scope"]["goods_extraction_applicable"] is False
    assert "НМЦК" not in result["extracted_fields"]
    assert "функциональные блоки" not in result["extracted_fields"]
    assert "Полный смысловой разбор" in result["supply_section_note"]


def test_source_rows_and_confirmed_notice_price_keep_original_attribution():
    row = {
        "№": "1",
        "Блок работ / результат": "Интеграция с источником",
        "Источник": "Техническое задание / пункт 4",
    }
    result = _direct_projection(kind="mixed", rows=[row], price="750 000", title="СМЭВ")
    assert result["spec_table"]["rows"] == [row]
    assert "НМЦК" in result["extracted_fields"]
    assert "интеграции" in result["extracted_fields"]
    assert any("750 000" in part for part in result["overview"])
    assert result["scope"]["procurement_primary_scope"] == "mixed"


def test_public_evidence_guard_survives_extraction(monkeypatch):
    metadata = {"tender_title": "Сопровождение информационной системы"}
    scope = {
        "procurement_primary_scope": "license",
        "goods_extraction_applicable": False,
    }
    monkeypatch.setattr(legacy, "_classify_procurement_scope", lambda *_: scope)
    monkeypatch.setattr(legacy, "_collect_supply_items", lambda *_: [])
    # Public facade applies additional source-evidence guards to a raw projection.
    actual = guarded_facade._ORIGINAL_BUILD_PRELIMINARY_PROCUREMENT_ANALYSIS(
        metadata=metadata,
        documents=[],
        technical_spec_text="Передача лицензии",
        contract_draft_text="Контракт и приемка",
        notice_text="Извещение",
    )
    expected = build_software_preliminary_analysis(
        metadata,
        [],
        "Передача лицензии\nКонтракт и приемка\nИзвещение",
        "Передача лицензии",
        "Контракт и приемка",
        "Извещение",
        scope,
        "license",
        _build_software_work_rows=legacy._build_software_work_rows,
        _extract_notice_price=legacy._extract_notice_price,
        _extract_notice_service_deadline=legacy._extract_notice_service_deadline,
        _extract_notice_delivery_deadline=legacy._extract_notice_delivery_deadline,
        _cleanup_tabular_value=legacy._cleanup_tabular_value,
        _match_first=legacy._match_first,
        _dedupe_text_items=legacy._dedupe_text_items,
    )
    assert actual["procurement_kind"] == expected["procurement_kind"] == "license"
    assert actual["spec_table"] == expected["spec_table"]
    assert actual["scope"] == expected["scope"]
    assert any("INSUFFICIENT_EVIDENCE" in item for item in actual["delivery_model"])
    assert not any("INSUFFICIENT_EVIDENCE" in item for item in expected["delivery_model"])
