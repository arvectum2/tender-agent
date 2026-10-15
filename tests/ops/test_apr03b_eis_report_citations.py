"""Source-grounded HTML display must not invent citations or change generic R7."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.modules.tender_operator_agent_demo.operator_eis_report_citations import (
    append_official_eis_citations,
)


def proof(*, selection="single_registry_matched_xml"):
    return {
        "source_selection": selection,
        "facts": {
            "procurement_title": {
                "status": "KNOWN", "value": 'Сайт <тест>',
                "evidence": [{
                    "source_ref": "eis-xml:FILE-01:purchaseObjectInfo",
                    "document": "официальный.xml",
                    "locator": "XML:purchaseObjectInfo",
                    "excerpt": 'Сайт <script>alert("X")</script>',
                }]
            },
            "application_deadline": {"status": "UNKNOWN", "value": None, "evidence": []},
            "nmck": {
                "status": "KNOWN", "value": 1000000.0,
                "evidence": [{
                    "source_ref": "eis-xml:FILE-01:maxPrice",
                    "document": "официальный.xml",
                    "locator": "XML:maxPrice",
                    "excerpt": "1000000.00",
                }]
            },
        },
    }


def patch_source(monkeypatch, value):
    monkeypatch.setattr(
        "src.modules.tender_operator_agent_demo.operator_workspace_evidence.get_operator_source_evidence",
        lambda run_id: value,
    )


def test_source_verified_only_safe_html_and_idempotent(monkeypatch, tmp_path: Path):
    patch_source(monkeypatch, proof())
    report = tmp_path / "report.html"
    report.write_text("<html><body><main><p>Основной анализ</p></main></body></html>")
    source = {"procurement_source": "zakupki_gov_ru_getdocs_ip"}
    assert append_official_eis_citations(report_path=report, run_id="toa-run-1", metadata=source) == 2
    result = report.read_text()
    assert "Официальный" not in result  # Title is fixed to the verifiable provenance category
    assert "Цитаты из оригинального XML ЕИС" in result
    assert "eis-xml:FILE-01:purchaseObjectInfo" in result
    assert "eis-xml:FILE-01:maxPrice" in result
    assert "&lt;script&gt;" in result
    assert "<script>" not in result
    assert "&lt;тест&gt;" in result
    assert result.count('id="official-eis-citations"') == 1
    assert append_official_eis_citations(report_path=report, run_id="toa-run-1", metadata=source) == 0
    assert result == report.read_text()


@pytest.mark.parametrize("selection", ["ambiguous_notice_revisions", "unsupported_source", "no_unique_registry_matched_xml"])
def test_missing_verified_original_cannot_append(monkeypatch, tmp_path: Path, selection):
    patch_source(monkeypatch, proof(selection=selection))
    report = tmp_path / "report.html"
    report.write_text("<main>hello</main>")
    assert append_official_eis_citations(
        report_path=report, run_id="toa-run-1",
        metadata={"procurement_source": "zakupki_gov_ru_getdocs_ip"},
    ) == 0
    assert report.read_text() == "<main>hello</main>"


def test_generic_unverified_or_non_html_report_unchanged(monkeypatch, tmp_path):
    patch_source(monkeypatch, proof())
    path = tmp_path / "report.html"
    path.write_text("NOT A FULL HTML REPORT")
    assert append_official_eis_citations(
        report_path=path, run_id="toa-run-1",
        metadata={"procurement_source": "zakupki_gov_ru_getdocs_ip"},
    ) == 0
    assert append_official_eis_citations(
        report_path=path, run_id="toa-run-1", metadata={"procurement_source": "manual"},
    ) == 0
    assert path.read_text() == "NOT A FULL HTML REPORT"


def test_partial_unverified_proof_never_embedded(monkeypatch, tmp_path):
    evidence = proof()
    evidence["facts"]["nmck"]["evidence"][0]["source_ref"] = "unverified-source"
    patch_source(monkeypatch, evidence)
    report = tmp_path / "report.html"
    report.write_text("<main>valid</main>")
    assert append_official_eis_citations(
        report_path=report, run_id="toa-run-1",
        metadata={"procurement_source": "zakupki_gov_ru_getdocs_ip"},
    ) == 1
    result = report.read_text()
    assert "1000000.0" not in result
    assert "eis-xml:FILE-01:purchaseObjectInfo" in result


def test_unverified_preliminary_heading_replaced_by_official_subject(monkeypatch, tmp_path):
    patch_source(monkeypatch, proof())
    report = tmp_path / "report.html"
    report.write_text(
        '<main><section><h2>Предварительный анализ закупки</h2>'
        '<ul><li>Предмет закупки: Раздел 1. Общие требования.</li></ul></section></main>'
    )
    assert append_official_eis_citations(
        report_path=report, run_id="toa-run-1",
        metadata={"procurement_source": "zakupki_gov_ru_getdocs_ip"},
    ) == 2
    final = report.read_text()
    assert "Предмет закупки: Раздел 1" not in final
    assert "Предмет закупки (XML ЕИС): Сайт &lt;тест&gt;" in final


def test_active_product_persistence_surfaces_xml_source_provenance(monkeypatch, tmp_path):
    from src.modules.tender_operator_agent_demo import upload_service

    report = tmp_path / "report.html"

    def fake_frozen_persist(**kwargs):
        report.write_text("<main>Оригинальный отчёт</main>")

    patch_source(monkeypatch, proof())
    monkeypatch.setattr(
        "src.modules.procurement_analysis.frozen_producer.persist_frozen_r7_outputs",
        fake_frozen_persist,
    )
    monkeypatch.setattr(
        "src.modules.tender_operator_agent_demo.operator_report_assembly.add_verified_notice_to_report_steps",
        lambda metadata, steps: steps,
    )
    monkeypatch.setattr(upload_service._legacy, "_report_html_path", lambda run_id: report)
    monkeypatch.setattr(upload_service._legacy, "_output_dir", lambda run_id: tmp_path)

    upload_service._persist_outputs(
        "toa-run-test", {"procurement_source": "zakupki_gov_ru_getdocs_ip"},
        outputs={}, steps=[],
    )
    assert report.read_text().count("eis-xml:") == 2

    upload_service._persist_outputs(
        "toa-run-test", {"procurement_source": "manual_upload"},
        outputs={}, steps=[],
    )
    assert "eis-xml:" not in report.read_text()
