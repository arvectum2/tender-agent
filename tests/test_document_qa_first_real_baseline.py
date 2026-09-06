from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import openpyxl

from src.modules.procurement_analysis.frozen_types import AnalyzedDocument
from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.document_qa_runtime_patch import (
    _guard_operator_output,
)
from src.tender_research.document_text_extractor import EXTRACTED_STATUS, extract_text


def _document(text: str, *, name: str = "Техническое задание.docx") -> AnalyzedDocument:
    return AnalyzedDocument(
        display_name=name,
        extension=Path(name).suffix.lower(),
        role="technical_spec",
        text=text,
        extracted_text_available=True,
        warnings=[],
        source="test",
        file_id="FILE-TEST",
    )


def test_mislabeled_pdf_with_docx_content_is_extracted(tmp_path: Path) -> None:
    source = tmp_path / "Электронный документ.pdf"
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p><w:r><w:t>Заказчик: МКУ Служба кладбищ</w:t></w:r></w:p></w:body>
    </w:document>"""
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("word/document.xml", document_xml)

    status, text = extract_text(str(source))

    assert status == EXTRACTED_STATUS
    assert "МКУ Служба кладбищ" in text


def test_misspelled_xslx_with_real_xlsx_content_is_extracted(tmp_path: Path) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Расчет"
    sheet.append(["НМЦК", 3_400_000])
    payload = io.BytesIO()
    workbook.save(payload)
    workbook.close()

    source = tmp_path / "reportXls.xslx"
    source.write_bytes(payload.getvalue())

    status, text = extract_text(str(source))

    assert status == EXTRACTED_STATUS
    assert "НМЦК" in text
    assert "3400000" in text


def test_customer_extraction_prefers_role_scoped_customer_over_organizer_full_name() -> None:
    source = """
    <notice>
      <organizer><fullName>МКУ Центр муниципальных закупок</fullName></organizer>
      <customer><fullName>МКУ Служба кладбищ</fullName></customer>
    </notice>
    """

    assert legacy._extract_customer_name_from_text(source) == "МКУ Служба кладбищ"


def test_customer_extraction_does_not_promote_arbitrary_full_name() -> None:
    source = "<notice><organizer><fullName>МКУ Центр муниципальных закупок</fullName></organizer></notice>"

    assert legacy._extract_customer_name_from_text(source) is None


def test_customer_extraction_accepts_explicit_contract_party() -> None:
    source = (
        'МУНИЦИПАЛЬНОЕ КАЗЕННОЕ УЧРЕЖДЕНИЕ "СЛУЖБА КЛАДБИЩ", '
        'именуемое в дальнейшем «Заказчик», в лице директора, с одной стороны.'
    )

    assert (
        legacy._extract_customer_name_from_text(source)
        == 'МУНИЦИПАЛЬНОЕ КАЗЕННОЕ УЧРЕЖДЕНИЕ "СЛУЖБА КЛАДБИЩ"'
    )


def test_generic_software_source_does_not_emit_healthcare_or_named_system_templates() -> None:
    documents = [
        _document(
            "Предусмотрена модификация программного комплекса, интеграция с региональным "
            "поисковым сервисом и обработка персональных данных. Приемка выполняется "
            "после испытаний. Срок исполнения определяется контрактом."
        )
    ]

    payload = {
        "requirements": legacy._build_document_grounded_requirements(
            documents, "software_modification"
        ),
        "questions": legacy._build_document_grounded_questions(
            "software_modification", documents
        ),
        "risks": legacy._build_document_grounded_risks(
            "software_modification", documents, documents[0].text or ""
        ),
        "rfq": legacy._build_document_grounded_rfq_sections("software_modification"),
    }
    rendered = json.dumps(payload, ensure_ascii=False).lower()

    for forbidden in (
        "здравоохран",
        "медицинск",
        "смэв",
        "ерн",
        "сэмд",
        "ипра",
        "минобороны",
        "министерства обороны",
        "участник",
    ):
        # "участник" alone is not a domain marker, so only reject the old
        # procurement-specific phrase rather than ordinary procurement wording.
        if forbidden == "участник":
            assert "участниках сво" not in rendered
        else:
            assert forbidden not in rendered

    assert "модификация программного комплекса" in rendered
    assert "региональным поисковым сервисом" in rendered


def test_named_integration_requirement_survives_when_source_contains_exact_markers() -> None:
    documents = [_document("Требуется интеграция с ЕРН через СМЭВ и приемочное тестирование.")]

    rows = legacy._build_document_grounded_requirements(documents, "integration")

    assert any(row["title"] == "Интеграция с ЕРН через СМЭВ" for row in rows)


def test_final_output_guard_drops_named_domain_claims_absent_from_source() -> None:
    documents = [_document("Интеграция выполняется с региональным поисковым сервисом.")]
    outputs = {
        "final_recommendation": {
            "key_requirements": [
                "Интеграция с ЕРН через СМЭВ",
                "Интеграция с региональным поисковым сервисом",
            ],
            "open_questions": [
                "Кто предоставляет витрину Минобороны?",
                "Какие критерии приемки установлены?",
            ],
            "risks": ["Риск по медицинским данным", "Требуется проверка интеграций"],
        },
        "rfq_draft": {
            "sections": [
                "Подход к СМЭВ",
                "Стоимость подтвержденных интеграционных работ",
            ]
        },
    }

    hardened = _guard_operator_output(outputs, metadata={}, documents=documents)
    rendered = json.dumps(hardened, ensure_ascii=False).lower()

    assert "смэв" not in rendered
    assert "ерн" not in rendered
    assert "минобороны" not in rendered
    assert "медицин" not in rendered
    assert "региональным поисковым сервисом" in rendered
    assert "критерии приемки" in rendered
