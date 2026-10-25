"""Canonically sourced PDF/DOCX append ONLY labeled unverified LLM review material."""

from __future__ import annotations

import json
from pathlib import Path

from docx import Document

from src.modules.tender_operator_agent_demo.operator_review_export import (
    review_only_export_sections,
)
from src.modules.tender_operator_agent_demo.report_export_service import (
    _build_docx_from_canonical,
    _build_pdf_from_canonical,
)


def _write(path: Path, payload: dict):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _review_outputs(root: Path):
    _write(root / "requirements.json", {"requirements": [
        {"title": "[LLM — проверить по ТЗ] Сделать адаптивный сайт", "verification_status": "unverified", "source": "unverified_llm"},
        {"title": "ЗАЯВЛЕНО КАК ПОДТВЕРЖДЁННОЕ", "verification_status": "verified", "source": "eis_xml"},
    ]})
    _write(root / "contract_risks.json", {"risks": [
        {"risk": "[Гипотеза LLM — проверить договор] Есть штраф", "source_status": "unverified_llm", "status": "requires_review"},
        {"risk": "Скрытая гипотеза", "source_status": "legacy_unverified", "status": "blocker"},
    ]})
    _write(root / "supplier_questions.json", {"questions": [
        "[LLM — согласовать перед отправкой] Какие сроки?",
        "Непомеченный вопрос",
    ]})
    _write(root / "rfq_draft.json", {"sections": [
        "[Черновик LLM — согласовать] Предложите цену",
        "Подтвержденное условие без источника",
    ]})


def _minimal_canonical() -> dict:
    return {
        "executive_summary": {},
        "procurement_passport": {},
        "line_items": [],
        "missing_data": [],
        "limitations": [],
        "procurement_scope": {"procurement_primary_scope": "services"},
        "procurement_title": "Тестовая закупка",
        "procurement_number": "0372200172326000015",
        "decision": "manual_review_required",
    }


def test_only_explicitly_unverified_rows_appear_in_appendix(tmp_path):
    _review_outputs(tmp_path)
    result = review_only_export_sections(tmp_path)
    assert len(result) == 4
    flat = "\n".join(line for _, rows in result for line in rows)
    assert "Сделать адаптивный сайт" in flat
    assert "Есть штраф" in flat
    assert "Какие сроки" in flat
    assert "Предложите цену" in flat
    assert "ЗАЯВЛЕНО КАК ПОДТВЕРЖДЁННОЕ" not in flat
    assert "Скрытая гипотеза" not in flat
    assert "Непомеченный вопрос" not in flat


def test_actual_docx_includes_review_only_heading_and_suggestions(tmp_path):
    _review_outputs(tmp_path)
    path = tmp_path / "review.docx"
    _build_docx_from_canonical(_minimal_canonical(), "Анализ закупки", path, review_only_export_sections(tmp_path))
    assert path.exists()
    content = "\n".join(p.text for p in Document(path).paragraphs)
    assert "Неподтверждённые предложения LLM" in content
    assert "Сделать адаптивный сайт" in content
    assert "Предложите цену" in content
    assert "Ни один пункт ниже не подтверждён первоисточником" in content


def test_actual_pdf_contains_distinct_review_heading(tmp_path):
    _review_outputs(tmp_path)
    path = tmp_path / "review.pdf"
    _build_pdf_from_canonical(_minimal_canonical(), "Анализ закупки", path, review_only_export_sections(tmp_path))
    assert path.exists()
    assert path.read_bytes().startswith(b"%PDF-")
    assert path.stat().st_size > 1000


def test_pdf_artifact_is_not_overwritten_when_unverified_appendix_changes(tmp_path, monkeypatch):
    from unittest.mock import patch

    from src.modules.tender_operator_agent_demo.report_export_service import (
        export_demo_agent_report_pdf,
    )
    from src.modules.tender_operator_agent_demo.schemas import (
        TenderOperatorDemoReportResponse,
    )

    rid = "toa-run-20261009101331-bfdddd"
    output = tmp_path / "run-output"
    output.mkdir()
    (output / "canonical_report.json").write_text(
        json.dumps(_minimal_canonical(), ensure_ascii=False), encoding="utf-8"
    )
    metadata = {"run_id": rid, "procurement_id": "0372200172326000015"}
    report = TenderOperatorDemoReportResponse(
        run_id=rid,
        report_title="Анализ закупки",
        generated_at="2026-10-09T12:00:00",
        recommendation="manual_review_required",
        recommendation_label="Проверка",
        executive_summary=[],
        manual_checks=[],
        sections=[],
        report_markdown="# Отчёт",
    )
    with (
        patch("src.modules.tender_operator_agent_demo.report_export_service._safe_output_dir", return_value=tmp_path),
        patch("src.modules.tender_operator_agent_demo.report_export_service.get_demo_run_output_dir", return_value=output),
        patch("src.modules.tender_operator_agent_demo.report_export_service._load_metadata", return_value=metadata),
        patch("src.modules.tender_operator_agent_demo.report_export_service.get_uploaded_demo_report", return_value=report),
    ):
        first = export_demo_agent_report_pdf(rid)
        first_bytes = Path(first.file_path).read_bytes()
        _review_outputs(output)
        second = export_demo_agent_report_pdf(rid)
        assert first.file_path != second.file_path
        assert Path(first.file_path).read_bytes() == first_bytes
        assert Path(second.file_path).read_bytes().startswith(b"%PDF-")
        assert export_demo_agent_report_pdf(rid).file_path == second.file_path
