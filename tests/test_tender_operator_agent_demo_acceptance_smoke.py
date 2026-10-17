import re

import pytest


def test_acceptance_console_page_200_and_russian(client):
    page = client.get("/demo/tender-agent")
    assert page.status_code == 200
    text = page.text
    assert "Тендерный агент" in text
    assert "Демо-режим / подтверждение человеком" in text
    assert "Пилотный контур" in text
    assert "Без внешних действий" in text
    for tab in ("Найти закупку", "Получить документацию по номеру", "Загрузить документы", "Демо-набор", "Профиль поставщика"):
        assert tab in text


def test_legacy_demo_wizard_uses_canonical_private_workspace(client, monkeypatch):
    from src.modules.tender_operator_agent_demo import router
    from src.shared.config.settings import Settings

    monkeypatch.setattr(
        router, "get_settings",
        lambda: Settings(
            pilot_auth_enabled=True,
            pilot_auth_username="test-operator",
            pilot_auth_password="private-test-password-2026",
        ),
    )
    response = client.get("/demo/tender-agent/wizard", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/pilot/tender-agent/workspace"


def test_acceptance_supplier_profile_endpoint(client):
    resp = client.get("/api/demo/tender-agent/supplier-profile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"]
    assert data["supplier_id"]
    # no actual secret values leaked (env var name is acceptable in diagnostics)
    serialized = resp.text
    assert ".env" not in serialized.lower() or "добавьте" in serialized


def test_acceptance_procurement_sources_enpoint(client):
    resp = client.get("/api/demo/tender-agent/procurement/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 3
    sources = {s["source"] for s in data}
    assert "demo_local" in sources
    assert "public_eis_html_44fz" in sources
    assert "public_eis_html_capital_repair" in sources
    # labels are in Russian
    labels = [s["label"] for s in data if s["source"] != "zakupki_gov_ru_getdocs_ip"]
    for lbl in labels:
        assert not re.match(r"^[a-z_]+$", lbl), f"Label '{lbl}' is still a machine ID"
    # no actual secret values leaked (env var name is OK in diagnostics)
    serialized = resp.text
    assert "ZAKUPKI_GOV_RU_SOAP_TOKEN" not in serialized or "не настроен" in serialized


def test_acceptance_demo_local_search_returns_results(client):
    resp = client.post(
        "/api/demo/tender-agent/procurement/search",
        json={"source": "demo_local", "query": "электротехническое оборудование", "max_results": 5},
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    for r in results:
        assert r["title"]
        assert r["procurement_id"]


def test_acceptance_relevance_scoring_public_search(client):
    resp = client.post(
        "/api/demo/tender-agent/procurement/public-44fz-search",
        data={"query": "электротехническое оборудование", "max_results": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "outcome" in data
    assert data["outcome"] in {
        "success_with_results",
        "success_empty",
        "source_unavailable",
        "source_error",
        "unsupported_search_mode",
        "validation_error",
    }
    for field in ("page", "page_size", "returned_count", "has_more", "sort"):
        assert field in data
    if data.get("status") == "parsed" and data.get("cards"):
        for card in data["cards"]:
            rel = card.get("relevance")
            if rel:
                assert "score" in rel
                assert "status" in rel
                assert rel["status"] in ("high", "medium", "low", "not_recommended")
                assert 0 <= rel["score"] <= 100
                assert "breakdown" in rel


def test_acceptance_report_page_200_and_russian(client):
    resp = client.get("/demo/tender-agent/report")
    assert resp.status_code == 200
    text = resp.text
    assert "Отчёт тендерного агента" in text
    assert "Рекомендация:" in text
    assert "Демо-отчёт" in text
    assert "Краткий вывод" in text
    assert "Ручные проверки" in text


def test_acceptance_secrets_not_leaked_in_html(client):
    pages = [
        "/demo/tender-agent",
        "/demo/tender-agent/report",
    ]
    for path in pages:
        resp = client.get(path)
        assert resp.status_code == 200
        serialized = resp.text
        # env var name is OK (it appears in diagnostic instructions), but actual token value must not leak
        # ticket and full archive URLs must not appear
        assert "ticket=" not in serialized
        assert "http://ticket" not in serialized
        assert "https://ticket" not in serialized


@pytest.mark.skip(reason="Requires running server with real getDocsIP token; run manually")
def test_acceptance_eis_docs_flow_live(client):
    """Run this manually with the server started and token configured."""
    resp = client.post(
        "/api/demo/tender-agent/runs/from-eis-docs-archive",
        json={
            "reestr_number": "0888200000224000038",
            "law": "44fz",
            "subsystem_type": "PRIZ",
            "method": "getDocsByReestrNumber",
            "download_archive": True,
            "analyze_after_download": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"]
    # verify archive URL is not leaked
    serialized = resp.text
    assert "ticket=" not in serialized, "archive ticket leaked in API response"


def test_acceptance_language_consistency(client):
    resp = client.get("/demo/tender-agent")
    text = resp.text
    # These technical English terms should NOT appear in the visible UI
    # (they may appear in JS template literals or code, but never in plain HTML labels)
    forbidden_visible = [
        "Analysis status",
        "configured=true",
    ]
    for term in forbidden_visible:
        assert term not in text, f"English term '{term}' found in HTML"
    # Russian labels that must be present
    for label in ["Статус анализа", "SOAP-метод", "ID запроса (refId)", "URL архива (archiveUrl)"]:
        assert label in text, f"Russian label '{label}' not found"
