from __future__ import annotations

import zipfile

from src.modules.procurement_analysis.frozen_types import AnalyzedDocument
from src.modules.tender_operator_agent_demo.report_model import _russian_datetime
from src.modules.tender_operator_agent_demo.report_model_legacy import _item_rows, _parse_timestamp
from src.modules.tender_operator_agent_demo.upload_service_legacy import (
    _bounded_controlled_llm_text,
    _build_document_grounded_questions,
    _build_document_grounded_requirements,
    _build_document_grounded_rfq_sections,
    _build_document_grounded_risks,
    _build_preliminary_procurement_analysis,
    _collect_spreadsheet_sources,
    _decode_zip_member_name,
    _document_relevance_event_payload,
    _extract_service_items_from_notice_text,
    _extract_zip_documents,
    _final_recommendation_manual_checks,
    _is_transient_analysis_limitation,
    _is_transient_analysis_warning,
    _risk_manual_checks,
    _risk_status_from_classification,
    _software_economics_payload,
    _software_quote_guidance,
    _tender_summary_identity_fields,
)


def test_controlled_llm_context_is_bounded_with_explicit_omission_marker():
    text = "A" * 6000 + "B" * 6000
    bounded = _bounded_controlled_llm_text(text, max_chars=8000)
    assert len(bounded) <= 8000
    assert bounded.startswith("A" * 100)
    assert bounded.endswith("B" * 100)
    assert "SOURCE TEXT OMITTED FOR LOCAL LLM CONTEXT BUDGET" in bounded


def test_eis_legacy_cp866_zip_name_is_recovered():
    garbled = "Åα«Ñ¬Γ ¬«¡Γαá¬Γá.docx"
    assert _decode_zip_member_name(garbled, 0) == "Проект контракта.docx"


def test_utf8_zip_name_is_not_redecoded():
    name = "Проект контракта.docx"
    assert _decode_zip_member_name(name, 0x800) == name


def test_rendered_eis_notice_service_position_keeps_quantity_unit_and_price():
    title = (
        "Оказание услуг по разработке модуля определения пересечений границ земельных "
        "участков с землями лесного фонда для программного обеспечения «Аксиома»"
    )
    text = (
        "Объект закупки\n"
        "Наименование товара, работы, услугиКод позицииТип позицииЕдиница измерения"
        "Цена за единицуЗаказчикКоличество (объем работы, услуги)Стоимость позиции"
        f"{title}Идентификатор: 22318524862.02.30.000"
        "УслугаУсловная единица521000.00"
        "ДЕПАРТАМЕНТ ПРИРОДНЫХ РЕСУРСОВ - ЮГРЫ"
        "1521000.00"
        "Характеристики товара, работы, услуги"
    )
    items = _extract_service_items_from_notice_text(text, "Извещение.docx")
    assert len(items) == 1
    item = items[0]
    assert item.item_type == "service"
    assert item.quantity == "1"
    assert item.unit == "условная единица"
    assert item.unit_price == "521 000,00"
    assert item.total_price == "521 000,00"
    assert item.okpd2 == "62.02.30.000"


def test_canonical_service_line_keeps_notice_pricing_from_source_item():
    name = "Оказание услуг по разработке модуля для ГИС Аксиома"
    preliminary = {
        "procurement_kind": "software_modification",
        "canonical_procurement_model": {
            "canonical_items": [
                {
                    "canonical_item_id": "direct-1",
                    "official_name": name,
                    "display_name": name,
                    "quantity": "1",
                    "unit": "условная единица",
                    "evidence_ids": ["notice-row-1"],
                    "field_provenance": {
                        "name": "notice-row-1",
                        "quantity": "notice-row-1",
                        "unit": "notice-row-1",
                    },
                }
            ]
        },
        "service_items": [
            {
                "original_name": name,
                "normalized_name": name,
                "quantity": "1",
                "unit": "Условная единица",
                "unit_price": "521 000,00",
                "total_price": "521 000,00",
                "pricing_basis": "unit_price",
                "evidence_ids": ["notice-row-1"],
            }
        ],
    }

    [row] = _item_rows(preliminary)

    assert row["quantity"] == "1"
    assert row["unit_normalized"] == "условная единица"
    assert row["unit_price"] == "521 000,00"
    assert row["line_total"] == "521 000,00"
    assert row["line_total_display"] == "521 000,00"
    assert row["pricing_basis"] == "unit_price"


def test_software_commercial_guidance_uses_internal_cost_model_not_reseller_tkp():
    highlights, checks = _software_quote_guidance(quote_files_present=False)
    rendered = " ".join([*highlights, *checks]).lower()
    assert "собственной разработки" in rendered
    assert "трудозатрат" in rendered
    assert "субподряд" in rendered
    assert "собрать ткп вручную" not in rendered


def test_software_economics_calculates_security_cash_requirement():
    payload = _software_economics_payload(
        metadata={"procurement": {"initial_price": 521000}},
        preliminary_analysis={
            "contract_highlights": [
                "Оплата: В размере 100 % в течение 7 рабочих дней после приёмки.",
                "Аванс: не предусмотрен.",
                "Обеспечение исполнения контракта: 10,00%.",
            ]
        },
        notice_text="Размер обеспечения исполнения контракта\t10.00%",
        contract_draft_text="Авансовые платежи по Контракту не предусмотрены.",
        analysis_mode="llm_tender_operator_provider",
    )
    metrics = {item["label"]: item["value"] for item in payload["metrics"]}
    assert metrics["НМЦК"] == "521 000,00"
    assert "52 100,00" in metrics["Обеспечение исполнения"]
    assert "не предусмотрен" in metrics["Аванс"]
    assert "трудозатраты" in metrics["Внутренняя себестоимость разработки"]
    assert "субподряд" in metrics["КП подрядчика"]
    assert "внутренней оценки трудозатрат" in payload["result"]


def test_software_final_manual_checks_are_decision_specific():
    checks = " ".join(_final_recommendation_manual_checks("software_modification")).lower()
    assert "ч. 3 ст. 30" in checks
    assert "трудозатрат" in checks
    assert "кассовый разрыв" in checks
    assert "rfq" not in checks
    assert "excel" not in checks


def test_software_risk_manual_check_is_domain_specific():
    [check] = _risk_manual_checks("software_modification")
    lowered = check.lower()
    assert "трудозатрат" in lowered
    assert "кассовый разрыв" in lowered
    assert "совместимость аналогов" not in lowered


def test_candidate_risk_is_review_not_hard_blocker():
    assert _risk_status_from_classification("deal_breaker_candidate") == "requires_review"
    assert _risk_status_from_classification("market_standard_harsh_term") == "requires_review"
    assert _risk_status_from_classification("hard_blocker") == "blocker"


def test_previous_analysis_messages_are_recognized_as_transient():
    assert _is_transient_analysis_warning(
        "Контролируемый LLM-анализ не прошёл валидацию для разделов: requirements."
    )
    assert _is_transient_analysis_warning(
        "Не удалось извлечь текст из broken.pdf."
    )
    assert not _is_transient_analysis_warning("Входной архив был нормализован безопасно.")
    assert _is_transient_analysis_limitation(
        "TKP not uploaded. Supplier comparison and economics remain blocked or partial."
    )
    assert not _is_transient_analysis_limitation(
        "Без авторизации, без обхода captcha, без подачи заявки."
    )


def test_zip_member_inherits_parent_role_and_skips_pdf_companion(tmp_path):
    path = tmp_path / "outer.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("document.txt", "primary contract evidence")
        archive.writestr("document.txt.pdf", b"not-a-real-pdf")

    docs = _extract_zip_documents(path, "FILE-02", parent_role="contract_draft")

    assert len(docs) == 1
    assert docs[0].role == "contract_draft"
    assert docs[0].text == "primary contract evidence"
    assert docs[0].display_name.endswith("document.txt")


def test_msk_source_deadline_parses_to_correct_instant():
    parsed = _parse_timestamp("05.10.2026 10:00 (МСК+2)")
    assert parsed is not None
    assert parsed.isoformat() == "2026-10-05T10:00:00+05:00"


def test_software_tabular_spec_uses_current_source_rows_and_contract_terms():
    tech_text = "\n".join(
        [
            "6.1.\tТребования к интеграции Модуля\tПлагин на Python с API axipy 7.x, Windows и Linux.",
            "6.3.\tОбщие требования к пространственному анализу\tАвтоматическое определение пересечений; полный цикл ≤ 15 мин.",
            "8.\tПорядок приемки оказания услуг\tПМИ передается за 7 календарных дней до испытаний.",
            "9.\tГарантийные обязательства\tГарантия 1 год. Срок устранения недостатков 5 рабочих дней.",
            "13.\tКритерии приемки Модуля\tУспешная установка .axp; отклонение площади ≤ 0,01 %; полный цикл ≤ 15 мин.",
            "2.\tМесто оказания услуг\tКамерально по месту Исполнителя; испытания на средствах Заказчика.",
            "3.\tСроки оказания услуг\tС даты заключения контракта до 13.11.2026.",
        ]
    )
    contract_text = (
        "Авансовые платежи по Контракту не предусмотрены. "
        "Расчет за оказанные услуги осуществляется в размере 100 % в течение 7 (семи) рабочих дней "
        "со дня подписания Заказчиком документа о приёмке оказанных услуг."
    )
    notice_text = (
        "Размер обеспечения исполнения контракта\t10.00%\n"
        "Обеспечение заявок не требуется\n"
        "Обеспечение гарантийных обязательств не требуется\n"
        "Преимущество\tПреимущество в соответствии с ч. 3 ст. 30 Закона № 44-ФЗ\n"
        "Национальный режим: Постановление Правительства РФ № 1875; запрет на услуги иностранных лиц.\n"
        "Дата и время окончания подачи заявок\t05.10.2026 10:00"
    )
    documents = [
        AnalyzedDocument(
            display_name="Техническое задание.docx",
            extension=".docx",
            role="technical_spec",
            text=tech_text,
            extracted_text_available=True,
            warnings=[],
            source="upload",
            file_id="TECH",
            raw_content=None,
        ),
        AnalyzedDocument(
            display_name="Проект контракта.docx",
            extension=".docx",
            role="contract_draft",
            text=contract_text,
            extracted_text_available=True,
            warnings=[],
            source="upload",
            file_id="CONTRACT",
            raw_content=None,
        ),
        AnalyzedDocument(
            display_name="Извещение.docx",
            extension=".docx",
            role="notice",
            text=notice_text,
            extracted_text_available=True,
            warnings=[],
            source="upload",
            file_id="NOTICE",
            raw_content=None,
        ),
    ]
    result = _build_preliminary_procurement_analysis(
        metadata={
            "tender_title": "Разработка модуля для ГИС Аксиома",
            "deadline": "05.10.2026 10:00 (МСК+2)",
            "procurement": {
                "procedure_type": "Запрос котировок",
            },
        },
        documents=documents,
        technical_spec_text=tech_text,
        contract_draft_text=contract_text,
        notice_text=notice_text,
    )

    rendered = " ".join(
        [
            *result["overview"],
            *result["compliance_highlights"],
            *result["contract_highlights"],
            *result["next_actions"],
            *(row["Блок работ / результат"] for row in result["spec_table"]["rows"]),
        ]
    ).lower()
    assert "требования к интеграции модуля" in rendered
    assert "общие требования к пространственному анализу" in rendered
    assert "гарантийные обязательства" in rendered
    assert "запрос котировок" in rendered
    assert "13.11.2026" in rendered
    assert "05.10.2026 10:00 (мск+2)" in rendered
    assert "оплата:" in rendered and "100 %" in rendered and "7 рабочих дней" in rendered
    assert "аванс: не предусмотрен" in rendered
    assert "обеспечение заявки: не требуется" in rendered
    assert "обеспечение гарантийных обязательств: не требуется" in rendered
    assert "1875" in rendered
    assert "ч. 3 ст. 30" in rendered
    assert "профилю поставщика" in rendered
    assert "10" in rendered and "обеспечение исполнения контракта" in rendered
    assert "критерии приемки модуля" in rendered
    assert "0,01 %" in rendered
    assert "15 мин" in rendered
    for forbidden in ("смэв", "ерн", "минобороны", "ипра", "сэмд"):
        assert forbidden not in rendered


def test_customer_datetime_preserves_eis_source_timezone_label():
    assert _russian_datetime('05.10.2026 10:00 (МСК+2)') == '05.10.2026 10:00 (МСК+2)'


def test_software_grounded_sections_do_not_leak_unrelated_template():
    tech = AnalyzedDocument(
        display_name="Техническое задание.docx",
        extension=".docx",
        role="technical_spec",
        text=(
            "6.1.\tТребования к интеграции Модуля\tПлагин Python, API axipy 7.x, Windows/Linux.\n"
            "7.\tПрава на результаты\tИсключительные права на код остаются у Исполнителя.\n"
            "8.\tПорядок приёмки\tПМИ и приёмо-сдаточные испытания.\n"
            "11.\tКонфиденциальность\tЗапрет публикации кода за пределами Российской Федерации.\n"
            "13.\tКритерии приёмки\tПолный цикл не более 15 минут."
        ),
        extracted_text_available=True,
        warnings=[],
        source="upload",
        file_id="TECH",
        raw_content=None,
    )
    docs = [tech]
    requirements = _build_document_grounded_requirements(docs, "software_modification")
    questions = _build_document_grounded_questions("software_modification", docs)
    risks = _build_document_grounded_risks("software_modification", docs, "")
    rfq_sections = _build_document_grounded_rfq_sections("software_modification")
    rendered = " ".join(
        [
            *(item["title"] + " " + item["detail"] for item in requirements),
            *questions,
            *(item["clause"] + " " + item["impact"] + " " + item["mitigation"] for item in risks),
            *rfq_sections,
        ]
    ).lower()

    assert "axipy" in rendered
    assert "права" in rendered
    assert "приём" in rendered or "прием" in rendered
    assert risks and all(item.get("evidence_locators") for item in risks)
    unrelated_markers = ("смэв", "ерн", "ипра", "сэмд", "медицин")
    for marker in unrelated_markers:
        assert marker not in rendered


def test_missing_supplier_profile_is_reported_as_skipped_not_zero_match():
    message, metadata = _document_relevance_event_payload(
        profile=None,
        doc_relevance={
            "document_score": 0.0,
            "document_matched_terms": [],
            "document_reasons": ["Профиль поставщика не загружен"],
        },
    )
    assert "пропущен" in message.lower()
    assert "0 совпадений" not in message.lower()
    assert metadata["document_score"] is None
    assert metadata["scoring_skipped"] is True
    assert metadata["reason"] == "supplier_profile_not_bound"


def test_tender_summary_uses_procurement_deadline_and_procedure_not_runtime_clock():
    fields = _tender_summary_identity_fields(
        {
            "mode": "procurement_search_intake",
            "status": "analyzing",
            "analysis_status": "completed",
            "deadline": "05.10.2026 10:00 (МСК+2)",
            "procurement": {
                "procedure_type": "Запрос котировок",
                "deadline": "05.10.2026 10:00 (МСК+2)",
            },
        },
        analysis_mode="llm_tender_operator_provider",
    )
    assert fields["procedure_type"] == "Запрос котировок"
    assert fields["submission_deadline"] == "05.10.2026 10:00 (МСК+2)"
    assert fields["analysis_status"] == "completed"
    assert fields["analysis_mode"] == "llm_tender_operator_provider"
    assert fields["intake_mode"] == "procurement_search_intake"
