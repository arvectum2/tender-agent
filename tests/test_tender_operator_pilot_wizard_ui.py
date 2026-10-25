def test_pilot_wizard_page_uses_unified_operator_workspace(client, monkeypatch):
    from src.modules.tender_operator_agent_demo import router
    from src.shared.config.settings import Settings

    monkeypatch.setattr(
        router, "get_settings",
        lambda: Settings(
            pilot_auth_enabled=True,
            pilot_auth_username="test-user",
            pilot_auth_password="test-password-123456789",
        ),
    )
    response = client.get("/pilot/tender-agent")
    assert response.status_code == 200
    assert "Поиск закупок в ЕИС" in response.text
    assert "Найти закупки" in response.text
    assert "Ключевые слова" in response.text
    assert "Реестровый номер или ссылка" in response.text
    assert "Скачать и проанализировать" in response.text
    assert "База закупок" in response.text
    assert "Пошаговый мастер" not in response.text


def test_demo_console_links_to_single_workspace(client):
    response = client.get("/demo/tender-agent")
    assert response.status_code == 200
    assert 'href="/pilot/tender-agent/workspace"' in response.text
    assert "Открыть рабочий кабинет" in response.text
    assert "Пошаговый мастер" not in response.text


def test_legacy_wizard_bookmark_redirects_to_same_private_workspace(client, monkeypatch):
    from src.modules.tender_operator_agent_demo import router
    from src.shared.config.settings import Settings

    monkeypatch.setattr(
        router, "get_settings",
        lambda: Settings(
            pilot_auth_enabled=True,
            pilot_auth_username="test-user",
            pilot_auth_password="test-password-123456789",
        ),
    )
    response = client.get("/demo/tender-agent/wizard", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/pilot/tender-agent/workspace"
    workspace = client.get("/pilot/tender-agent/workspace")
    pilot = client.get("/pilot/tender-agent")
    assert workspace.status_code == pilot.status_code == 200
    assert workspace.content == pilot.content
    assert b'id="search-query"' in pilot.content
    assert b'id="operator-history"' in pilot.content

def test_one_operator_source_and_no_stale_local_docker_overlay():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    module = root / "src/modules/tender_operator_agent_demo"
    assert not (module / "pilot_wizard_ui.py").exists()
    assert (module / "assets/operator_workspace.html").is_file()
    assert (module / "assets/operator_workspace.js").is_file()
    assert (module / "assets/operator_workspace.css").is_file()
    dockerfile = (root / "deploy/local/Dockerfile").read_text()
    assert "rm -rf /app/src /app/scripts /app/migrations" in dockerfile
    for tree in ("src", "scripts", "migrations"):
        assert f"COPY --chown=app:app {tree} /app/{tree}" in dockerfile
    owner_source = (root / "docs/architecture/TENDER_AGENT_SINGLE_OPERATOR_UI.md").read_text()
    assert "18082" in owner_source
    assert "/pilot/tender-agent/workspace" in owner_source
