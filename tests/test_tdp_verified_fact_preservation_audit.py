"""R5 audit never treats stub/fallback report or unsourced fields as fact."""

from __future__ import annotations

import json

from scripts.ops.audit_tdp_verified_facts import (
    audit_verified_facts,
    compare_saved_notice_fact_projections,
)

REGISTRY = "0372200172326000015"


def _meta():
    return {
        "procurement_id": REGISTRY,
        "_verified_notice_facts": {
            "registry_number": REGISTRY,
            "file_id": "FILE-01",
            "values": {
                "procurement_title": "Создание сайта",
                "application_deadline": "2026-10-13T12:00:00",
                "nmck": "1000000.00",
            },
        },
    }


def _canonical():
    return {
        "procurement_title": "Создание сайта",
        "application_deadline": "2026-10-13T12:00:00",
        "nmck": "1000000.00",
        "field_evidence": {key: f"eis-xml:FILE-01:{key}" for key in (
            "procurement_title", "application_deadline", "nmck"
        )},
        "_verified_notice_facts": _meta()["_verified_notice_facts"],
    }


def test_known_facts_and_locators_survive():
    result = compare_saved_notice_fact_projections(_meta(), _canonical())
    assert set(result.values()) == {"known_source_with_original_xml_locator"}


def test_source_fact_never_silently_becomes_unknown():
    canonical = _canonical()
    canonical["nmck"] = "UNKNOWN"
    assert compare_saved_notice_fact_projections(_meta(), canonical)["nmck"] == (
        "known_source_became_unknown"
    )


def test_source_locator_must_survive():
    canonical = _canonical()
    canonical["field_evidence"]["procurement_title"] = "unknown"
    assert compare_saved_notice_fact_projections(_meta(), canonical)[
        "procurement_title"
    ] == "known_fact_missing_source_reference"


def test_foreign_notice_cannot_become_local_source():
    metadata = _meta()
    metadata["_verified_notice_facts"]["registry_number"] = "0372200172326000016"
    result = compare_saved_notice_fact_projections(metadata, _canonical())
    assert set(result.values()) == {"source_registry_or_file_mismatch"}


def test_all_runs_audit_does_not_change_any_bytes_or_emit_contents(tmp_path):
    run = tmp_path / "toa-run-20261010120000-abcdef"
    (run / "output").mkdir(parents=True)
    meta = _meta()
    meta["secret"] = "PRIVATE CUSTOMER NAME"
    (run / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False))
    (run / "output" / "canonical_report.json").write_text(
        json.dumps(_canonical(), ensure_ascii=False)
    )
    before = {str(x): x.read_bytes() for x in run.rglob("*") if x.is_file()}
    result = audit_verified_facts(tmp_path)
    after = {str(x): x.read_bytes() for x in run.rglob("*") if x.is_file()}
    assert before == after
    assert result["runs_checked"] == 1
    assert result["unique_procurements"] == 1
    assert result["statuses"]["known_source_with_original_xml_locator"] == 3
    assert "PRIVATE CUSTOMER NAME" not in json.dumps(result)
    assert result["source_extraction_legal_accuracy_verified"] is False


def test_notice_field_reference_does_not_masquerade_as_original_xml():
    canonical = _canonical()
    canonical["field_evidence"]["nmck"] = "eis_notice:nmck"
    assert compare_saved_notice_fact_projections(_meta(), canonical)["nmck"] == (
        "known_source_with_notice_field_reference_only"
    )
