from types import SimpleNamespace

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.operator_risk_report import (
    build_document_grounded_rfq_sections,
    build_document_grounded_risks,
)


def risk(kind, items=(), enabled=False):
    return build_document_grounded_risks(kind, [], "", detect_maintenance=lambda *a: enabled, source_okpd2=lambda *a: None, collect_items=lambda *a: list(items))

def test_unresolved_source_keeps_review_required():
    assert legacy._build_document_grounded_risks("unresolved", [], "") == risk("unresolved")
    assert risk("unresolved")[0]["clause"] == "Недостаточно предметных данных"
    assert len(risk("goods")) == 4
    assert len(build_document_grounded_rfq_sections("goods")) == 5
    assert legacy._build_document_grounded_rfq_sections("goods") == build_document_grounded_rfq_sections("goods")

def test_source_ids_only_from_service_entries():
    items = [SimpleNamespace(item_type="service", evidence_id="SRC-1"), SimpleNamespace(item_type="good", evidence_id="NON-SERVICE") ]
    result = risk("services", items, enabled=True)
    assert len(result) == 5
    assert result[0]["evidence_ids"] == "SRC-1"
    assert result[2]["evidence_ids"] == ""
    assert not any("NON-SERVICE" in row["evidence_ids"] for row in result)

def test_templates_do_not_forge_source_ids():
    assert all("evidence_ids" not in row for row in risk("integration"))
    assert all(not row["evidence_ids"] for row in risk("services", enabled=True))
