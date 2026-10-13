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


def test_demo_console_links_to_pilot_wizard(client):
    response = client.get("/demo/tender-agent")

    assert response.status_code == 200
    assert "/pilot/tender-agent" in response.text
    assert "Пошаговый мастер" in response.text


def test_pilot_wizard_alias_renders(client):
    response = client.get("/demo/tender-agent/wizard")

    assert response.status_code == 200
    assert "Найдите закупку или вставьте ссылку / реестровый номер" in response.text
    assert "Найти закупки" in response.text
    assert "дд.мм.гггг" in response.text
    assert "НМЦК: от, ₽" in response.text
