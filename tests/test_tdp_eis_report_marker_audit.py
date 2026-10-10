"""No private content escapes an R5 source-marker inventory."""

import json

from scripts.ops.audit_tdp_eis_corpus import audit_corpus, report_source_marker_counts


def test_explicit_eis_and_unknown_and_model_review_markers_are_separate():
    report = {"sections": [
        {"title": "Требования", "items": [
            "НМЦК: 100 рублей [eis-xml:source]",
            "Срок: UNKNOWN",
            "[LLM — проверить по ТЗ] Адаптивный сайт",
            "Значение не извлечено",
        ]},
        {"title": "Экономика", "items": ["Цена не установлена"]},
    ]}
    result = report_source_marker_counts(report)
    assert result == {
        "report_sections": 2,
        "report_items": 5,
        "report_unknown_markers": 3,
        "report_eis_xml_references": 1,
        "report_unverified_llm_markers": 1,
    }


def test_read_only_inventory_counts_only_and_never_exposes_report_content(tmp_path):
    folder = tmp_path / "toa-run-20261009-example"
    (folder / "input").mkdir(parents=True)
    (folder / "output").mkdir()
    (folder / "metadata.json").write_text(json.dumps({
        "procurement_id": "0372200172326000015",
        "files": [{"stored_name": "notice.xml", "extracted_text_available": True}],
        "status": "completed_with_warnings",
    }), encoding="utf-8")
    (folder / "input" / "notice.xml").write_text("private original")
    (folder / "output" / "report.json").write_text(json.dumps({
        "sections": [{"title": "Private", "items": [
            "Secret document body 7474; source UNKNOWN",
            "НМЦК подтверждена eis-xml:source",
        ]}],
    }), encoding="utf-8")
    before = {str(p): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    result = audit_corpus(tmp_path)
    after = {str(p): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    assert before == after
    assert result["best_report_unknown_markers"] == 1
    assert result["best_report_eis_xml_references"] == 1
    assert result["best_reports_without_eis_xml_references"] == 0
    serialized = json.dumps(result)
    assert "Secret document" not in serialized
    assert "private original" not in serialized
    assert result["acceptance_quality_verified"] is False


def test_missing_report_never_counts_as_zero_unknown_quality_pass():
    assert report_source_marker_counts(None)["report_unknown_markers"] == 0
    assert report_source_marker_counts({"sections": "invalid"})["report_items"] == 0
