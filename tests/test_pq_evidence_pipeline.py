"""Original-source PQ triage integration tests."""
from datetime import date

from src.modules.market_intelligence.pq_evidence_pipeline import triage


def test_empty_source_scope_preserves_unknown_market(tmp_path):
    ontology = tmp_path / "ontology.yaml"
    ontology.write_text("families:\n  - id: ukrm\n    positive: ['УКРМ']\n", encoding="utf-8")
    result = triage(root=tmp_path, ontology=ontology,
                    first=date(2024, 1, 1), last=date(2024, 1, 1),
                    regions=["77"], subsystems=["RI223"], max_archives=1)
    assert result["source_day_status"] == {"missing": 1}
    assert result["archives_sha_verified_and_inspected"] == 0
    assert result["lexical_candidates"] == []
    assert result["equipment_market_total_rub"] is None
    assert result["signed_awards_verified"] is False
    assert result["technical_attachment_content_inspected"] is False
