from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.operator_upload_descriptors import (
    _build_file_descriptor,
    build_demo_file_descriptor,
)


def test_legacy_facade_and_default_shape():
    assert legacy._build_file_descriptor is _build_file_descriptor
    assert legacy.build_demo_file_descriptor is build_demo_file_descriptor
    payload = legacy.build_demo_file_descriptor(
        file_id="doc-1", original_name="ТЗ.docx",
        stored_name="01-tz.docx", size_bytes=17,
        content_type="", source="eis",
        source_type="soap", source_url="https://zakupki.gov.ru/file",
    )
    assert payload["display_name"] == "ТЗ.docx"
    assert payload["extension"] == ".docx"
    assert payload["content_type"] == "application/octet-stream"
    assert payload["source"] == "eis"
    assert payload["source_type"] == "soap"
    assert payload["text_extraction_status"] == "pending"
    assert payload["warnings"] == []
