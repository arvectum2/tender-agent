"""Structured unknown states must not vanish behind readable report prose."""

import json
from pathlib import Path

from scripts.ops.audit_tdp_eis_corpus import audit_corpus


def test_structured_unknowns_count_separately_from_literal_report_items(tmp_path: Path):
    folder = tmp_path / "toa-run-20261010-a"
    (folder / "output").mkdir(parents=True)
    (folder / "input").mkdir()
    (folder / "metadata.json").write_text(json.dumps({
        "procurement_id": "0372200172326000015", "files": [], "status": "needs_review",
    }))
    (folder / "output" / "report.json").write_text(json.dumps({
        "sections": [{"title": "Decision", "items": ["Human review required"]}],
        "decision_core": {"unknowns": [
            {"code": "volume", "value": "PRIVATE-CUSTOMER-TEXT"},
            {"code": "cost", "value": None},
        ]},
    }))
    (folder / "output" / "canonical_report.json").write_text(json.dumps({
        "procurement_passport": {
            "subject": "unknown",
            "nmck": "НЕ ИЗВЛЕЧЕНО",
            "customer": "ООО private-customer-name",
            "currency": "RUB",
        },
    }, ensure_ascii=False))
    output = audit_corpus(tmp_path)
    assert output["best_report_unknown_markers"] == 0
    assert output["best_decision_core_unknown_rows"] == 2
    assert output["best_canonical_passport_exact_unknown_fields"] == 2
    assert output["procurements"][0]["decision_core_unknown_rows"] == 2
    encoded = json.dumps(output, ensure_ascii=False)
    assert "PRIVATE-CUSTOMER-TEXT" not in encoded
    assert "private-customer-name" not in encoded
    assert output["acceptance_quality_verified"] is False


def test_malformed_unknown_status_types_fail_closed(tmp_path: Path):
    folder = tmp_path / "toa-run-20261010-b"
    (folder / "output").mkdir(parents=True)
    (folder / "metadata.json").write_text(json.dumps({
        "procurement_id": "32616450723", "status": "completed", "files": [],
    }))
    (folder / "output" / "report.json").write_text(json.dumps({
        "decision_core": {"unknowns": "secret-raw-text"}, "sections": [],
    }))
    (folder / "output" / "canonical_report.json").write_text(json.dumps({
        "procurement_passport": "private-string",
    }))
    result = audit_corpus(tmp_path)
    assert result["best_decision_core_unknown_rows"] == 0
    assert result["best_canonical_passport_exact_unknown_fields"] == 0
