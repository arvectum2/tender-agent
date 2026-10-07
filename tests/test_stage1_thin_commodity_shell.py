import base64

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.modules.daily_tender_run.profiles import load_daily_tender_profile
from src.modules.pilot_access_boundary.schemas import ActorCategory, VisibilityLevel
from src.modules.pilot_access_boundary.service import can_actor_view
from src.modules.tender_connectors import text_extraction
from src.modules.tender_connectors.text_extraction import extract_text_from_attachment_bytes
from src.shared.document_processing import ProcessedDocument
from src.shared.api.middleware import install_runtime_middlewares
from src.shared.config.settings import Settings


def _basic_auth(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_stage1_shell_journey_search_saved_view_card_alert_and_export(client):
    profile = load_daily_tender_profile("arvectum-it")
    assert profile.profile_id == "arvectum-it"
    assert profile.version
    assert profile.queries
    assert profile.max_results_per_query >= 1

    search = client.post(
        "/api/demo/tender-agent/procurement/search",
        json={
            "source": "demo_local",
            "query": "электротехническое оборудование",
            "max_results": 5,
        },
    )
    assert search.status_code == 200
    results = search.json()
    assert results and results[0]["procurement_id"]

    watch = client.post(
        "/procurement-monitoring/watches",
        json={
            "source": "demo_local",
            "external_id": results[0]["procurement_id"],
            "saved_search": {
                "profile_id": profile.profile_id,
                "profile_version": profile.version,
                "query": "электротехническое оборудование",
            },
        },
    )
    assert watch.status_code == 201
    assert watch.json()["saved_search"]["profile_id"] == profile.profile_id

    run = client.post(
        "/commercial-prebid-demo/run",
        json={"fixture_name": "commercial_mvp_demo", "provider": "stub"},
    )
    assert run.status_code == 201
    deal_id = run.json()["deal_id"]

    card = client.get(f"/commercial-console/deals/{deal_id}")
    assert card.status_code == 200
    assert deal_id in card.text

    exported = client.get("/api/demo/tender-agent/report/download")
    assert exported.status_code == 200
    assert "attachment; filename=" in exported.headers["content-disposition"]


def test_stage1_shell_document_adapter_and_role_boundary(monkeypatch):
    calls = []

    def fake_process(**kwargs):
        calls.append(kwargs)
        return ProcessedDocument(
            extraction_status="extracted",
            text=(
                "Техническое задание на поставку серверного оборудования. "
                "Количество 10 штук. Срок поставки 30 календарных дней."
            ),
            chunks=(),
        )

    monkeypatch.setattr(text_extraction, "process_document_bytes", fake_process)
    extracted = extract_text_from_attachment_bytes(
        "https://example.test/specification.txt",
        b"fixture-bytes",
    )
    assert extracted is not None
    assert "Техническое задание" in extracted
    assert "30 календарных дней" in extracted
    assert calls[0]["filename"] == "specification.txt"
    assert calls[0]["canonical_uri"] == "https://example.test/specification.txt"

    allowed = can_actor_view(
        ActorCategory.design_partner_viewer,
        VisibilityLevel.partner_visible,
    )
    blocked = can_actor_view(
        ActorCategory.design_partner_viewer,
        VisibilityLevel.internal_only,
    )
    assert allowed.allowed
    assert not blocked.allowed


def test_stage1_shell_baseline_auth_protects_product_routes():
    app = FastAPI()

    @app.get("/api/stage1-shell")
    def stage1_shell():
        return {"ok": True}

    install_runtime_middlewares(
        app,
        Settings(
            pilot_auth_enabled=True,
            pilot_auth_username="pilot",
            pilot_auth_password="long-stage1-test-password",
            allowed_hosts="",
            cors_allow_origins="",
        ),
    )
    client = TestClient(app)

    assert client.get("/api/stage1-shell").status_code == 401
    authenticated = client.get(
        "/api/stage1-shell",
        headers=_basic_auth("pilot", "long-stage1-test-password"),
    )
    assert authenticated.status_code == 200
    assert authenticated.headers["cache-control"] == "no-store"
