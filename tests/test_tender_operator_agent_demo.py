import socket

from src.modules.tender_operator_agent_demo.ui import render_tender_operator_console_html


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
    assert "http://127.0.0.1:8081/v1" in page.text
    assert "arvectum-gemma4-12b-it-qat-q4_0" in page.text
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


def test_tender_operator_wizard_page_header(client):
    response = client.get("/demo/tender-agent/wizard")
    assert response.status_code == 200
    html = response.text
    assert "Поиск и анализ закупки" in html
    assert "Прогон тендера через формы" not in html
    assert ".md" not in html
    assert "Агент скачает доступные документы" in html
    assert "/api/demo/tender-agent/runs/${encodeURIComponent(run.run_id)}/export/docx" in html
    assert "/api/demo/tender-agent/runs/${encodeURIComponent(run.run_id)}/export/pdf" in html
    assert "Скачать DOCX" in html
    assert "Скачать PDF" in html


def test_tender_operator_wizard_date_filters_empty(client):
    response = client.get("/demo/tender-agent/wizard")
    html = response.text
    assert "search_date_from" in html
    assert "placeholder=\"дд.мм.гггг\"" in html
    assert "mm/dd/yyyy" not in html.lower()


def test_tender_operator_wizard_nmck_format(client):
    response = client.get("/demo/tender-agent/wizard")
    html = response.text
    assert "НМЦК: от, ₽" in html
    assert "НМЦК: до, ₽" in html
    assert "placeholder=\"1 000 000\"" in html


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
