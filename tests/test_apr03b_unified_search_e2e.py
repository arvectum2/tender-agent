"""Owner feedback regression: one truthful EIS search -> real documents -> analyzed run."""

from __future__ import annotations

import base64
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.modules.tender_operator_agent_demo import router as operator_router
from src.shared.api.middleware import TenderPilotBasicAuthMiddleware
from src.shared.config.settings import Settings


@pytest.fixture
def workspace_client(monkeypatch):
    monkeypatch.setattr(
        operator_router,
        "get_settings",
        lambda: Settings(
            pilot_auth_enabled=True,
            pilot_auth_username="workspace-test",
            pilot_auth_password="workspace-test-password-2026",
        ),
    )
    app = FastAPI()
    app.include_router(operator_router.router)
    app.add_middleware(
        TenderPilotBasicAuthMiddleware,
        username="workspace-test",
        password="workspace-test-password-2026",
        protected=("/pilot/tender-agent", "/api/demo/tender-agent"),
        public=("/health",),
    )
    auth = "Basic " + base64.b64encode(b"workspace-test:workspace-test-password-2026").decode()
    return TestClient(app), {"Authorization": auth}


def test_only_one_canonical_operator_entry_and_real_search_controls(workspace_client):
    client, headers = workspace_client
    assert client.get("/pilot/tender-agent").status_code == 401
    assert client.get("/pilot/tender-agent/workspace").status_code == 401
    old = client.get("/pilot/tender-agent", headers=headers)
    new = client.get("/pilot/tender-agent/workspace", headers=headers)
    assert old.status_code == 200
    assert old.text == new.text
    assert "Найти закупки" in old.text
    assert 'id="search-query"' in old.text
    assert 'id="search-law"' in old.text
    assert 'id="search-region"' in old.text
    assert 'id="search-price-from"' in old.text
    assert 'id="search-deadline-to"' in old.text
    assert "Скачать и проанализировать" in old.text
    assert 'id="append-files"' in old.text
    assert 'id="operator-history"' in old.text
    assert 'id="registry-list"' in old.text
    assert 'href="/pilot/tender-agent">Пошаговый мастер' not in old.text


@pytest.mark.parametrize("law", ["44fz", "223fz"])
def test_unified_search_uses_prior_working_eis_endpoint(law, workspace_client, monkeypatch):
    client, headers = workspace_client
    seen = []

    def existing_search(**kwargs):
        seen.append(kwargs)
        return {
            "status": "success",
            "outcome": "success_with_results",
            "query": kwargs["query"],
            "source": "public_eis_html_" + law,
            "cards": [
                {
                    "reestr_number": "0372200172326000015" if law == "44fz" else "32616450723",
                    "title": "Реальная проверочная карточка",
                    "law": law,
                }
            ],
            "returned_count": 1,
            "message": "Результаты получены из ЕИС",
        }

    monkeypatch.setattr(operator_router, "search_public_44fz", existing_search)
    response = client.post(
        "/api/demo/tender-agent/procurement/public-44fz-search",
        params={
            "query": "создание сайта",
            "law": law,
            "page_size": 10,
            "max_results": 10,
            "price_from": 50000,
            "date_from": "2026-10-01",
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "success_with_results"
    assert len(body["cards"]) == 1
    assert seen[0]["query"] == "создание сайта"
    assert seen[0]["law"] == law
    assert seen[0]["price_from"] == 50000
    assert seen[0]["date_from"] == "2026-10-01"


def test_actual_browser_javascript_one_click_analysis_and_missing_doc_fails_closed():
    if not shutil.which("node"):
        pytest.skip("node runtime required to exercise browser JavaScript")
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["node", str(root / "tests/js/operator_workspace_flow.cjs")],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=35,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "UNIFIED_UI_E2E_SIMULATION_PASS" in result.stdout


def test_legacy_eis_parser_only_accepts_unique_registry_identity():
    from src.modules.tender_operator_agent_demo.eis_notice_parser import (
        extract_notice_revision_info,
    )

    xml = """<notice><purchaseNumber>0372200172326000015</purchaseNumber>
    <purchaseNumber>0019</purchaseNumber><docVersion>2</docVersion>
    <purchaseObjectInfo>Реальный предмет</purchaseObjectInfo></notice>"""
    verified = extract_notice_revision_info(xml)
    assert verified["purchase_number"] == "0372200172326000015"
    assert verified["version"] == 2

    for unsafe in (
        "<notice><purchaseObjectInfo>Реальный предмет</purchaseObjectInfo></notice>",
        (
            "<notice><purchaseNumber>0372200172326000015</purchaseNumber>"
            "<purchaseNumber>0372200172326000016</purchaseNumber></notice>"
        ),
        "<!DOCTYPE foo [<!ENTITY xxe SYSTEM 'file:///private/secret'>]><notice/>",
        "<notice><purchaseNumber>0372200172326000015</purchaseNumber>",
    ):
        assert extract_notice_revision_info(unsafe) == {}
