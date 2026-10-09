"""APR-03B real-source acceptance: EIS XML citation identity and strict UNKNOWN gating."""
from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.modules.tender_operator_agent_demo import operator_workspace_evidence as evidence
from src.modules.tender_operator_agent_demo import router as operator_router
from src.modules.tender_operator_agent_demo import upload_service as upload
from src.modules.tender_operator_agent_demo import eis_notice_parser as parser
from src.shared.api.middleware import TenderPilotBasicAuthMiddleware
from src.shared.config.settings import Settings

NUMBER = "0372200172326000015"
TITLE = "Оказание услуг по разработке сайта Музея Хлеба"
GOOD_XML = (
    "<notice><purchaseNumber>" + NUMBER + "</purchaseNumber>"
    "<purchaseObjectInfo>" + TITLE + "</purchaseObjectInfo>"
    "<endDT>2026-10-16T10:00:00+03:00</endDT>"
    "<maxPrice>1000000.00</maxPrice>"
    "<purchaseNumber>0019</purchaseNumber></notice>"
)


@pytest.fixture
def source(tmp_path, monkeypatch):
    directory = tmp_path / "run" / "input"
    directory.mkdir(parents=True)
    (directory / "notice.xml").write_text(GOOD_XML, encoding="utf-8")
    metadata = {
        "procurement_source": "zakupki_gov_ru_getdocs_ip",
        "procurement_id": NUMBER,
        "files": [{
            "file_id": "FILE-01", "stored_name": "notice.xml",
            "display_name": "Оригинал_извещения.xml", "extension": ".xml",
        }],
    }
    monkeypatch.setattr(evidence, "load_demo_run_metadata", lambda _: metadata)
    monkeypatch.setattr(evidence, "get_demo_run_input_dir", lambda _: directory)
    return directory, metadata


def test_real_xml_evidence_is_verified_and_attributable(source):
    result = evidence.get_operator_source_evidence("existing-run")
    assert result["contract_version"] == "operator-eis-source-evidence-v1"
    assert result["warnings"] == []
    assert result["human_control_required"] is True
    assert result["external_action_allowed"] is False
    assert set(result["facts"]) == {"procurement_title", "application_deadline", "nmck"}
    assert all(fact["status"] == "KNOWN" for fact in result["facts"].values())
    title = result["facts"]["procurement_title"]
    assert title["value"] == TITLE
    assert title["evidence"] == [{
        "source_ref": "eis-xml:FILE-01:purchaseObjectInfo",
        "document": "Оригинал_извещения.xml",
        "locator": "XML:purchaseObjectInfo",
        "excerpt": TITLE,
        "file_id": "FILE-01",
    }]
    assert result["facts"]["nmck"]["value"] == 1000000.0
    assert result["facts"]["application_deadline"]["value"].startswith("2026-10-16T10:00")


def test_wrong_registry_number_never_promotes_source(source):
    _directory, metadata = source
    metadata["procurement_id"] = "1111111111111111111"
    result = evidence.get_operator_source_evidence("existing-run")
    assert all(f["status"] == "UNKNOWN" and not f["evidence"] for f in result["facts"].values())
    assert result["warnings"]


def test_duplicate_notice_revision_fails_closed(source):
    directory, metadata = source
    (directory / "second.xml").write_text(GOOD_XML, encoding="utf-8")
    metadata["files"].append({
        "file_id": "FILE-02", "stored_name": "second.xml",
        "display_name": "second.xml", "extension": ".xml",
    })
    assert all(f["status"] == "UNKNOWN" for f in evidence.get_operator_source_evidence("existing-run")["facts"].values())


def test_conflicting_prices_degrade_only_nmck(source):
    directory, _metadata = source
    (directory / "notice.xml").write_text(GOOD_XML.replace(
        "</maxPrice>", "</maxPrice><maxPrice>700000.00</maxPrice>"
    ))
    facts = evidence.get_operator_source_evidence("existing-run")["facts"]
    assert facts["procurement_title"]["status"] == "KNOWN"
    assert facts["nmck"]["status"] == "UNKNOWN"


def test_xml_entity_and_symlink_escape_are_rejected(source, tmp_path):
    directory, metadata = source
    (directory / "notice.xml").write_text(
        '<!DOCTYPE foo [<!ENTITY sneaky "payload">]>' + GOOD_XML
    )
    assert all(f["status"] == "UNKNOWN" for f in evidence.get_operator_source_evidence("existing-run")["facts"].values())
    outside = tmp_path / "outside.xml"
    outside.write_text(GOOD_XML)
    (directory / "notice.xml").unlink()
    (directory / "notice.xml").symlink_to(outside)
    assert all(f["status"] == "UNKNOWN" for f in evidence.get_operator_source_evidence("existing-run")["facts"].values())


def test_manually_uploaded_or_223_source_not_claimed_as_eis(source):
    _directory, metadata = source
    metadata["procurement_source"] = "public_eis_html_223fz"
    assert all(f["status"] == "UNKNOWN" for f in evidence.get_operator_source_evidence("existing-run")["facts"].values())


def test_title_override_requires_matched_registry_revision(monkeypatch):
    correct = "Подтверждённый исходным XML предмет закупки"
    def original(metadata, **_kwargs):
        return {**metadata, "procurement_title": "Раздел 1. Общие требования", "_field_evidence": {
            "procurement_title": "documents:generic-text"
        }}
    monkeypatch.setattr(upload, "_ORIGINAL_ENRICH_PROCUREMENT_METADATA_FROM_DOCUMENTS", original)
    monkeypatch.setattr(parser, "extract_notice_metadata", lambda _text: {
        "procurement_subject": correct
    })
    monkeypatch.setattr(parser, "extract_notice_revision_info", lambda _text: {
        "purchase_number": NUMBER, "version": 1, "published_at": "2026-10-08"
    })
    metadata = {
        "procurement_source": "zakupki_gov_ru_getdocs_ip",
        "procurement_id": NUMBER,
        "procurement": {"procurement_number": NUMBER, "title": "Заглушка ЕИС"},
    }
    doc = SimpleNamespace(extension=".xml", text="<notice />", role="notice")
    fixed = upload._enrich_procurement_metadata_from_documents(metadata, documents=[doc])
    assert fixed["procurement_title"] == correct
    assert fixed["procurement"]["title"] == correct
    assert fixed["_field_evidence"]["procurement_title"] == "eis_notice:procurement_subject"
    monkeypatch.setattr(parser, "extract_notice_revision_info", lambda _text: {
        "purchase_number": "1111111111111111111", "version": 1,
        "published_at": "2026-10-08"
    })
    rejected = upload._enrich_procurement_metadata_from_documents(metadata, documents=[doc])
    assert rejected["procurement_title"] == "Раздел 1. Общие требования"


def test_endpoint_is_auth_protected(source, monkeypatch):
    monkeypatch.setattr(
        operator_router, "get_settings",
        lambda: Settings(
            pilot_auth_enabled=True,
            pilot_auth_username="operator",
            pilot_auth_password="safe-private-pass-12345",
        ),
    )
    app = FastAPI()
    app.include_router(operator_router.router)
    app.add_middleware(
        TenderPilotBasicAuthMiddleware, username="operator", password="safe-private-pass-12345",
        protected=("/pilot/tender-agent", "/api/demo/tender-agent"), public=("/health",),
    )
    client = TestClient(app)
    route = "/api/demo/tender-agent/workspace/runs/existing-run/evidence"
    assert client.get(route).status_code == 401
    authorization = base64.b64encode(b"operator:safe-private-pass-12345").decode()
    result = client.get(route, headers={"Authorization": "Basic " + authorization})
    assert result.status_code == 200
    assert result.json()["facts"]["procurement_title"]["value"] == TITLE
