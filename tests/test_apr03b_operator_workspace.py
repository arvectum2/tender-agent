"""APR-03B: private browser workspace, strict EIS intake and read-only canonical data."""

from __future__ import annotations

import base64
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.modules.tender_operator_agent_demo import operator_workspace_service as service
from src.modules.tender_operator_agent_demo import router as operator_router
from src.shared.api.middleware import TenderPilotBasicAuthMiddleware
from src.shared.config.settings import Settings
from src.tender_research.models import ProcurementTender, ProcurementTenderDocument


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        operator_router, "get_settings",
        lambda: Settings(
            pilot_auth_enabled=True,
            pilot_auth_username="test-operator",
            pilot_auth_password="test-secret-unique-12345",
        ),
    )
    app = FastAPI()
    app.include_router(operator_router.router)
    app.add_middleware(
        TenderPilotBasicAuthMiddleware,
        username="test-operator",
        password="test-secret-unique-12345",
        protected=("/pilot/tender-agent", "/api/demo/tender-agent"),
        public=("/health",),
    )
    return TestClient(app)


@pytest.fixture
def auth():
    payload = base64.b64encode(b"test-operator:test-secret-unique-12345").decode()
    return {"Authorization": "Basic " + payload}


@pytest.mark.parametrize(
    ("value", "number", "law"),
    [
        ("0372200172326000015", "0372200172326000015", "44fz"),
        ("32500001234", "32500001234", "223fz"),
        (
            "https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber=0372200172326000015",
            "0372200172326000015", "44fz",
        ),
        (
            "https://zakupki.gov.ru/223/purchase/public/purchase/info/common-info.html?regNumber=32500001234",
            "32500001234", "223fz",
        ),
    ],
)
def test_strict_eis_reference_accepts_known_formats(value, number, law):
    got, regime, url = service.parse_eis_reference(value)
    assert got == number
    assert regime == law
    if value.startswith("https:"):
        assert url == value


@pytest.mark.parametrize(
    "value",
    [
        "https://evil.com/epz/order/notice/ok20/view/common-info.html?regNumber=0372200172326000015",
        "https://zakupki.gov.ru.evil.com/epz/order/notice/ok20/view/common-info.html?regNumber=0372200172326000015",
        "https://attacker@zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber=0372200172326000015",
        "http://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber=0372200172326000015",
        "https://zakupki.gov.ru@evil.com/epz/order/notice/ok20/view/common-info.html?regNumber=0372200172326000015",
        "https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber=bad",
        "https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber=0372200172326000015&regNumber=1111111111111111111",
        "https://zakupki.gov.ru/sneaky?regNumber=0372200172326000015",
        "123456789",
    ],
)
def test_strict_eis_reference_denies_unsafe_inputs(value):
    with pytest.raises(ValueError):
        service.parse_eis_reference(value)


def test_workspace_auth_html_assets_and_no_demo_handoffs(client, auth):
    assert client.get("/pilot/tender-agent/workspace").status_code == 401
    assert client.get("/pilot/tender-agent/workspace/assets/workspace.js").status_code == 401
    assert client.get("/api/demo/tender-agent/workspace/registry").status_code == 401

    html = client.get("/pilot/tender-agent/workspace", headers=auth)
    assert html.status_code == 200
    assert "База закупок" in html.text
    assert "Новый анализ" in html.text
    assert "Cache-Control" in html.headers
    for suffix, media in (("workspace.css", "text/css"), ("workspace.js", "text/javascript")):
        res = client.get("/pilot/tender-agent/workspace/assets/" + suffix, headers=auth)
        assert res.status_code == 200
        assert media in res.headers["content-type"]
        assert "no-store" in res.headers.get("cache-control", "")
    assert client.get("/pilot/tender-agent/workspace/assets/../router.py", headers=auth).status_code in {404, 405}


def test_workspace_denies_disabled_or_incomplete_auth_configuration(client, auth, monkeypatch):
    monkeypatch.setattr(operator_router, "get_settings", lambda: Settings(pilot_auth_enabled=False))
    assert client.get("/pilot/tender-agent/workspace", headers=auth).status_code == 503
    assert client.get("/api/demo/tender-agent/workspace/registry", headers=auth).status_code == 503
    monkeypatch.setattr(
        operator_router, "get_settings",
        lambda: Settings(
            pilot_auth_enabled=True,
            pilot_auth_username="test-operator",
            pilot_auth_password="test-secret-unique-12345",
            pilot_auth_protected_prefixes="/pilot/tender-agent",
        ),
    )
    assert client.get("/pilot/tender-agent/workspace", headers=auth).status_code == 503


def test_api_import_rejects_invalid_and_delegates_valid_reference(client, auth, monkeypatch):
    seen = []
    def fake_import(value):
        seen.append(value)
        return {"run_id": "real-corpus-run-1", "status": "ready_to_analyze"}
    monkeypatch.setattr(operator_router, "import_eis_reference", fake_import)
    bad = client.post("/api/demo/tender-agent/workspace/import", json={"reference": "https://malicious.example/223"}, headers=auth)
    assert bad.status_code == 400
    assert seen == []
    good = client.post("/api/demo/tender-agent/workspace/import", json={"reference": "0372200172326000015"}, headers=auth)
    assert good.status_code == 200
    assert seen == ["0372200172326000015"]
    assert client.post("/api/demo/tender-agent/workspace/import", json={"reference": "abc"}, headers=auth).status_code == 422


@pytest.fixture
def fake_db(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ProcurementTender.__table__.create(engine)
    ProcurementTenderDocument.__table__.create(engine)
    with Session(engine) as session:
        tender = ProcurementTender(
            source="eis", external_id="notice-1", registry_number="0372200172326000015",
            law_type="44fz", title="Разработка сайта музея", customer_name="Музей хлеба",
            nmck_amount=450000, currency="RUB", status="published",
        )
        session.add(tender)
        session.flush()
        path = tmp_path / "original.pdf"
        path.write_bytes(b"%PDF-1.5 valid-test-attachment")
        outside = tmp_path.parent / "other-secret.pdf"
        outside.write_bytes(b"SECRET")
        doc = ProcurementTenderDocument(
            tender_id=tender.id, file_name="original.pdf", local_path=str(path),
            download_status="downloaded", text_extraction_status="done",
        )
        bad_doc = ProcurementTenderDocument(
            tender_id=tender.id, file_name="outside.pdf", local_path=str(outside),
            download_status="downloaded", text_extraction_status="failed",
        )
        session.add_all([doc, bad_doc])
        session.commit()
        ids = tender.id, doc.id, bad_doc.id
    @contextmanager
    def session_factory():
        with Session(engine) as session:
            yield session
    monkeypatch.setattr(service, "read_session", session_factory)
    monkeypatch.setattr(service, "get_settings", lambda: Settings(arvectum_data_dir=str(tmp_path)))
    yield ids
    engine.dispose()


def test_readonly_registry_search_detail_and_scoped_download(fake_db, client, auth):
    tender, good, bad = fake_db
    res = client.get("/api/demo/tender-agent/workspace/registry?query=музея", headers=auth)
    assert res.status_code == 200
    assert res.json()["total"] == 1
    assert res.json()["items"][0]["title"] == "Разработка сайта музея"
    assert "raw_payload" not in res.json()["items"][0]
    assert client.get("/api/demo/tender-agent/workspace/registry?query=other", headers=auth).json()["total"] == 0
    details = client.get(f"/api/demo/tender-agent/workspace/registry/{tender}", headers=auth)
    assert details.status_code == 200
    assert len(details.json()["documents"]) == 2
    assert {entry["local_download"] for entry in details.json()["documents"]} == {True, False}
    download = client.get(f"/api/demo/tender-agent/workspace/registry/{tender}/documents/{good}/download", headers=auth)
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF-")
    assert client.get(f"/api/demo/tender-agent/workspace/registry/{tender}/documents/{bad}/download", headers=auth).status_code == 404
    assert client.get(f"/api/demo/tender-agent/workspace/registry/{'a'*36}", headers=auth).status_code == 404
    assert client.get("/api/demo/tender-agent/workspace/registry?limit=999", headers=auth).status_code == 422


def test_duplicate_sql_wildcards_are_treated_as_literal(fake_db):
    assert service.registry_records(query="%")["total"] == 0
    assert service.registry_records(query="_")["total"] == 0


def test_document_path_cannot_escape_data_root(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "secret.pdf"
    outside.write_bytes(b"private")
    (root / "shortcut.pdf").symlink_to(outside)
    monkeypatch.setattr(service, "get_settings", lambda: Settings(arvectum_data_dir=str(root)))
    assert service._allowed_document_path(str(outside)) is None
    assert service._allowed_document_path(str(root / "shortcut.pdf")) is None
