"""Tender summary projection contract: verified deadlines and honest document metadata."""

from __future__ import annotations

from types import SimpleNamespace

from src.modules.tender_operator_agent_demo.operator_submission_deadline import (
    submission_deadline_from_metadata,
)
from src.modules.tender_operator_agent_demo.operator_tender_summary import (
    build_operator_tender_summary,
)


def _doc(name: str, role: str, text: str):
    return SimpleNamespace(display_name=name, role=role, text=text)


def _project(*, deadline=None, docs=None, mode="uploaded_demo", status="completed", source=None):
    metadata = {
        "run_id": "RUN-CHECK",
        "tender_title": "Разработка сайта",
        "customer_name": "Музей",
        "tender_category": "Услуги",
        "status": status,
        "files": [{"name": "notice.xml"}, {"name": "contract.pdf"}],
        "mode": mode,
    }
    if deadline is not None:
        metadata["deadline"] = deadline
    if source:
        metadata.update(source)
    if docs is None:
        docs = [_doc("Извещение.xml", "notice", "НМЦК 100000"), _doc("Контракт.pdf", "contract", "")]
    stamps = []

    def now():
        stamps.append(True)
        return "2026-10-11T08:00:00+03:00"

    summary = build_operator_tender_summary(
        metadata=metadata,
        documents=docs,
        preliminary_analysis={"overview": ["Предмет закупки: Разработка сайта"]},
        analysis_mode="fallback_deterministic_adapter",
        _safe_datetime=now,
        submission_deadline_from_metadata=submission_deadline_from_metadata,
    )
    assert stamps == [True]
    return summary


def test_no_eis_submission_deadline_is_null_not_report_time():
    summary = _project()
    assert summary["prepared_at"] == "2026-10-11T08:00:00+03:00"
    assert summary["submission_deadline"] is None
    assert summary["run_id"] == "RUN-CHECK"
    assert summary["analysis_status"] == "completed"


def test_explicit_source_iso_date_keeps_local_timezone_without_conversion():
    summary = _project(deadline="2026-10-16T10:00:00+03:00")
    assert summary["submission_deadline"] == "2026-10-16T10:00:00+03:00"
    assert summary["prepared_at"] != summary["submission_deadline"]


def test_invalid_source_deadline_is_not_filled_by_now():
    summary = _project(deadline="отменено")
    assert summary["submission_deadline"] is None


def test_structured_procurement_deadline_is_preserved():
    summary = _project(source={"procurement": {"deadline": "15.07.2026 12:00:00 +10:00"}})
    assert summary["submission_deadline"] == "2026-07-15T12:00:00+10:00"


def test_uploaded_document_signals_are_counts_not_inferred_eis_claims():
    summary = _project(docs=[
        _doc("Загруженный.xml", "unknown", ""),
        _doc("ТЗ.docx", "technical_spec", "Поставка оборудования"),
    ])
    assert len(summary["documents"]) == 2
    assert summary["documents"][0] == {"name": "Загруженный.xml", "role": "unknown", "pages": 1}
    assert "Загружено файлов: 2." in summary["document_signals"]
    assert "Файлов с извлечённым текстом: 1." in summary["document_signals"]
    assert summary["procedure_type"] == "Загруженный demo run"


def test_procurement_intake_mode_uses_explicit_procurement_id():
    summary = _project(
        mode="procurement_search_intake",
        source={"procurement_id": "0372200172326000015"},
        status="needs_review",
    )
    assert summary["procurement_code"] == "0372200172326000015"
    assert summary["procedure_type"] == "Поиск закупки + intake"
    assert summary["analysis_status"] == "needs_review"
    assert "Режим создания run: procurement_search_intake." in summary["document_signals"]


def test_uploaded_run_uses_run_id_for_procurement_code_without_fabricating_number():
    summary = _project()
    assert summary["procurement_code"] == "RUN-CHECK"
    assert summary["title"] == "Разработка сайта"
    assert summary["category"] == "Услуги"
    assert summary["customer"] == "Музей"
