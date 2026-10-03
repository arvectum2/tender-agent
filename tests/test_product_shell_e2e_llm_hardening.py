from __future__ import annotations

import zipfile

from src.modules.procurement_analysis.frozen_types import AnalyzedDocument
from src.modules.tender_operator_agent_demo.report_model_legacy import _parse_timestamp
from src.modules.tender_operator_agent_demo.upload_service_legacy import (
    _bounded_controlled_llm_text,
    _collect_spreadsheet_sources,
    _decode_zip_member_name,
    _extract_zip_documents,
    _is_transient_analysis_limitation,
    _is_transient_analysis_warning,
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
