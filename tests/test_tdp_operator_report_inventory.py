from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.operator_report_inventory import (
    build_downloaded_documents_inventory,
    document_type_label,
)


def test_legacy_facade_and_evidence_status():
    metadata = {"files": [{"display_name": "ТЗ.docx", "role_hint": "technical_spec", "source_type": "eis-soap", "extracted_text_available": False, "text_extraction_status": "failed"}, {"original_name": "Извещение.xml", "document_kind": "eis_notice", "source": "eis", "extracted_text_available": True}, {"stored_name": "unknown.bin"}]}
    actual = build_downloaded_documents_inventory(metadata)
    assert actual == legacy._build_downloaded_documents_inventory(metadata)
    assert actual[0] == {"name": "ТЗ.docx", "type": "техническое задание / техническая часть", "download_status": "downloaded", "text_status": "failed", "source": "eis-soap"}
    assert actual[1]["name"] == "Извещение.xml"
    assert actual[1]["text_status"] == "extracted"
    assert actual[2]["name"] == "Документ"
    assert actual[2]["text_status"] == "pending"
    assert actual[2]["source"] == "runtime"
    assert metadata["files"][0]["extracted_text_available"] is False

def test_unknown_role_never_claims_to_be_official_notice():
    assert document_type_label({"role_hint": "not-verified"}) == "документ закупки"
    assert legacy._document_type_label({"document_kind": "contract_draft"}) == "проект контракта"
