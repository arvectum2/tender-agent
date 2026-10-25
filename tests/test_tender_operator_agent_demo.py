import socket

from src.modules.tender_operator_agent_demo.ui import (
    render_tender_operator_console_html,
)

REQUIRED_STEP_FIELDS = {
    "key",
    "order",
    "title",
    "short_title",
    "status",
    "description",
    "agent_action",
    "result_summary",
    "findings",
    "human_review",
    "trace",
    "result_sections",
}


def test_tender_operator_demo_page_and_report_render(client):
    page = client.get("/demo/tender-agent")
    report_page = client.get("/demo/tender-agent/report")
    asset = client.get("/demo/tender-agent/assets/arvectum-logo-block.svg")

    assert page.status_code == 200
    assert "Тендерный агент" in page.text
    assert "Демо-режим / подтверждение человеком" in page.text
    assert "Найти закупку" in page.text
    assert "Загрузка и анализ" in page.text
    assert "История анализов" in page.text
    assert "Статус фоновой задачи" in page.text
    assert "Режим анализа" in page.text
    assert "Параметры анализа" in page.text
    assert "Mac mini: локальная LLM + Qwen3 embeddings" in page.text
    assert "Быстрый тест без LLM / local hash" in page.text
    assert "Qwen3-Embedding-4B" in page.text
    assert "llama_cpp" in page.text
    assert "http://127.0.0.1:8090/v1" in page.text
    assert "http://127.0.0.1:8088/v1" in page.text
    assert "/Users/master/models/Qwen2.5-14B-Instruct-Q4_K_M.gguf" in page.text
    assert "local-hash-v1" in page.text
    assert "limit: 8" in page.text or "limit: 3" in page.text
    assert "Скачать DOCX" in page.text
    assert "Скачать PDF" in page.text

    assert report_page.status_code == 200
    assert "Отчёт тендерного агента" in report_page.text

    assert asset.status_code == 200
    assert "svg" in asset.headers["content-type"]


def test_tender_operator_demo_api_returns_expected_structure(client):
    response = client.get("/api/demo/tender-agent/run")
    steps_response = client.get("/api/demo/tender-agent/steps")
    report_response = client.get("/api/demo/tender-agent/report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["demo_mode"] is True
    assert payload["tender"]["customer"] == "Промышленный заказчик"
    assert payload["tender"]["document_count"] == 4
    assert payload["final_recommendation"]["recommendation"] == "participate_conditionally"
    assert len(payload["final_recommendation"]["manual_checks"]) >= 3
    assert len(payload["trace_summary"]) >= 3

    expected_statuses = {
        "documents": "done",
        "requirements": "done",
        "questions": "needs_review",
        "rfq": "done",
        "quotes": "done",
        "economics": "warning",
        "risks": "warning",
        "decision": "needs_review",
    }

    assert len(payload["steps"]) == 8
    for step in payload["steps"]:
        assert REQUIRED_STEP_FIELDS <= step.keys()
        assert step["status"] == expected_statuses[step["key"]]
        assert step["findings"]
        assert step["human_review"]
        assert step["trace"]

    assert steps_response.status_code == 200
    assert steps_response.json()["run_id"] == payload["tender"]["run_id"]
    assert len(steps_response.json()["steps"]) == len(payload["steps"])

    assert report_response.status_code == 200
    report_payload = report_response.json()
    assert report_payload["recommendation"] == "participate_conditionally"
    assert "## Краткий вывод" in report_payload["report_markdown"]


def test_tender_operator_demo_report_download_works(client):
    response = client.get("/api/demo/tender-agent/report/download")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "attachment; filename=" in response.headers["content-disposition"]
    assert '"run_id": "TOA-DEMO-001"' in response.text


def test_tender_operator_demo_stays_off_external_network(client, monkeypatch):
    def fail_on_network(*args, **kwargs):
        raise AssertionError("External network access should not be attempted in demo mode")

    monkeypatch.setattr(socket, "create_connection", fail_on_network)

    response = client.get("/api/demo/tender-agent/run")

    assert response.status_code == 200
    payload = response.json()
    assert "no external actions" in payload["safety"]["restrictions"]


def test_tender_operator_console_history_report_button_avoids_broken_inline_js():
    page = render_tender_operator_console_html()

    assert "history-open-report" in page
    assert "data-run-id=" in page
    assert "handleOpenHistoryReport(''" not in page


def test_legacy_demo_wizard_cannot_serve_second_operator_ui(client, monkeypatch):
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
    actual = client.get(response.headers["location"])
    assert actual.status_code == 200
    assert "Поиск закупок в ЕИС" in actual.text
    assert "НМЦК от, ₽" in actual.text
    assert 'id="search-date-from"' in actual.text
    assert "Скачать и проанализировать" in actual.text


def test_tender_operator_console_contains_background_job_polling():
    page = render_tender_operator_console_html()

    assert "/api/tender-research/jobs/prepare" in page
    assert "/api/tender-research/jobs/analyze" in page
    assert "/api/tender-research/jobs/" in page
    assert "analysis-job-status" in page
    assert "current_section_title" in page
    assert "provider: runtime.provider" in page
    assert "model: runtime.model" in page
    assert "base_url: runtime.base_url" in page
    assert "payload.llm_base_url = runtime.llm_base_url" in page
    assert "payload.llm_model = runtime.llm_model" in page
    assert "analysis_mode: runtime.analysis_mode" in page
    assert "limit: runtime.limit" in page
    assert "analysis-runtime-summary" in page
    assert "Mac mini: локальная LLM + Qwen3 embeddings" in page
    assert "Быстрый тест без LLM / local hash" in page
    assert "/api/tender-research/analyze/history/" in page
    assert "/export/docx" in page
    assert "/export/pdf" in page
    assert "/api/demo/tender-agent/runs/" in page
    assert "/api/demo/tender-agent/runs/${encodeURIComponent(result.run_id)}/export/docx" in page
    assert "/api/demo/tender-agent/runs/${encodeURIComponent(result.run_id)}/export/pdf" in page
    assert "/api/demo/tender-agent/runs/${encodeURIComponent(run.run_id)}/export/docx" in page
    assert "/api/demo/tender-agent/runs/${encodeURIComponent(run.run_id)}/export/pdf" in page
