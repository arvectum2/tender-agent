"""Source-locked requirements context reporting without invented procurement facts."""

from __future__ import annotations

from types import SimpleNamespace

from src.modules.tender_operator_agent_demo.operator_requirements_context import (
    build_operator_requirements_context,
)


def _project(
    *,
    kind="services",
    notice_price=None,
    contract_text="",
    enriched=None,
    preliminary=None,
    terms=None,
    status="missing",
):
    metadata = enriched if enriched is not None else {
        "procurement_id": "01234567890123456789",
        "tender_title": "Сопровождение портала",
        "_field_evidence": {},
        "procurement": {},
    }
    pre = preliminary if preliminary is not None else {
        "overview": ["Предмет закупки: Услуги сопровождения"],
        "service_items": [{"description": "Поддержка", "evidence_ids": ["DOC:1"]}],
        "missing_documents": ["Проект контракта"],
    }
    docs = [SimpleNamespace(display_name="Извещение.xml", file_id="D-1")]
    contract_documents = (
        [SimpleNamespace(display_name="Контракт.docx", file_id="D-2")]
        if status == "present" else []
    )
    reads = {"price": [], "okpd2": [], "delivery": []}

    def extract_price(*args):
        reads["price"].append(args)
        return notice_price

    def extract_okpd2(*args):
        reads["okpd2"].append(args)
        return "62.02" if "ОКПД2" in args[0] else None

    def delivery(pre):
        reads["delivery"].append(pre)

    facts = terms if terms is not None else {}
    output = build_operator_requirements_context(
        requirement_rows=[{"value": "Только по документу"}],
        preliminary_analysis=pre,
        metadata=metadata,
        documents=docs,
        contract_documents=contract_documents,
        contract_draft_status=status,
        contract_draft_text=contract_text,
        notice_text="Извещение с ОКПД2",
        scope={"goods_extraction_applicable": kind == "goods", "scope_classification_conflict": False},
        procurement_kind=kind,
        goods_positions=[],
        output_warnings=["Не все документы извлечены"],
        contract_term_facts=facts,
        contract_term_conflicts=[],
        economics=None,
        delivery_address_from_preliminary=delivery,
        _service_okpd2_from_sources=extract_okpd2,
        _extract_notice_price=extract_price,
    )
    return output, reads


def test_missing_contract_terms_and_delivery_remain_unknown():
    out, reads = _project(notice_price=None)
    context = out["analysis_context"]
    assert context["nmck"] is None
    assert context["delivery_place"] is None
    assert context["delivery_address"] is None
    assert context["delivery_status"] == "unknown"
    assert context["known_contract_terms"] == []
    assert context["unknown_contract_terms"] == [
        "payment", "acceptance", "penalties", "security", "liability"
    ]
    assert context["document_coverage"] == "partial"
    assert context["missing_documents"] == ["Проект контракта"]
    assert context["commercial_inputs"] == {}
    assert context["supplier_profile"] is None
    assert len(reads["price"]) == 1


def test_enriched_source_evidence_and_operator_price_pass_through():
    metadata = {
        "procurement_id": "ABC",
        "tender_title": "Поставка",
        "customer_name": "Заказчик",
        "customer_inn": "123",
        "customer_kpp": "456",
        "delivery_place": "Казань",
        "delivery_address": "Казань, ул. Победы",
        "delivery_status": "known",
        "_field_evidence": {"delivery_place": "eis_notice:delivery_place"},
        "procurement": {},
    }
    out, _ = _project(kind="goods", notice_price="1000000", enriched=metadata)
    context = out["analysis_context"]
    assert context["nmck"] == "1000000"
    assert context["delivery_evidence_ids"] == ["eis_notice:delivery_place"]
    assert context["delivery_place"] == "Казань"
    assert context["delivery_status"] == "known"
    assert context["customer_inn"] == "123"
    assert context["customer_kpp"] == "456"
    assert context["okpd2"] is None


def test_service_source_okpd2_not_guessed_for_goods():
    service, service_reads = _project(kind="services", notice_price="50000")
    goods, goods_reads = _project(kind="goods", notice_price=None)
    assert service["analysis_context"]["okpd2"] == "62.02"
    assert service_reads["okpd2"]
    assert goods["analysis_context"]["okpd2"] is None
    assert goods_reads["okpd2"] == []


def test_present_contract_uses_only_source_terms_and_original_file_identity():
    fact = SimpleNamespace(as_dict=lambda: {"field": "payment", "value": "7 дней", "source": "D-2"}, value="7 дней")
    pre = {"overview": ["Предмет закупки: Услуги"], "contract_highlights": ["Проверка приёмки"]}
    out, _ = _project(
        contract_text="Оплата в течение 7 дней",
        preliminary=pre,
        terms={"payment": fact},
        status="present",
    )
    context = out["analysis_context"]
    assert context["contract_term_facts"] == [{"field": "payment", "value": "7 дней", "source": "D-2"}]
    assert context["payment"] == "7 дней"
    assert context["known_contract_terms"] == ["Проверка приёмки"]
    assert context["unknown_contract_terms"] == []
    assert context["contract_draft_evidence_ids"] == ["contract:D-2"]
    assert context["missing_documents"] == []


def test_not_extracted_contract_remains_explicitly_incomplete():
    out, _ = _project(kind="services", contract_text="", status="parse_failed")
    context = out["analysis_context"]
    assert context["missing_documents"] == []
    assert context["unknown_contract_terms"]
    assert context["contract_draft_documents"] == []
    assert context["extraction_warnings"] == ["Не все документы извлечены"]
    assert len(out["manual_review_points"]) == 2
    assert "перед внешними действиями" in out["manual_review_points"][1]


def test_requirements_and_service_items_keep_input_evidence_link():
    out, _ = _project(kind="services", notice_price=None)
    assert out["requirements"] == [{"value": "Только по документу"}]
    assert out["analysis_context"]["evidence_map"] == [["DOC:1"]]
    assert out["analysis_context"]["service_items"][0]["evidence_ids"] == ["DOC:1"]
