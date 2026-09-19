from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.tender_research.rag.job_runner import run_analyze_job, run_prepare_job
from src.tender_research.rag.prepare_service import (
    TenderPreparationResult,
    TenderPreparationStep,
)
from src.tender_research.rag.schemas import TenderAnalysisResult


def test_run_prepare_job_completes_and_persists_result() -> None:
    session = MagicMock()
    prepare_result = TenderPreparationResult(
        status="completed",
        registry_number="0323100010326000013",
        ready_for_analysis=True,
        steps=[TenderPreparationStep("readiness_check", "completed", "Ready")],
        tender_found=True,
        documents_total=4,
        documents_downloaded=4,
        extracted_texts_total=4,
        chunks_total=40,
        chunks_created=40,
        embeddings_total=40,
        embeddings_created=40,
    )

    def fake_prepare(*args, **kwargs):
        kwargs["progress_callback"](
            {
                "progress_percent": 100,
                "current_step": "readiness_check",
                "message": "Ready",
                "steps": prepare_result.steps,
            }
        )
        return prepare_result

    with patch("src.tender_research.rag.job_runner._get_session", return_value=session), patch(
        "src.tender_research.rag.job_runner.mark_job_running"
    ), patch(
        "src.tender_research.rag.job_runner.prepare_tender_for_analysis",
        side_effect=fake_prepare,
    ) as mock_prepare, patch(
        "src.tender_research.rag.job_runner.update_job_progress"
    ) as mock_progress, patch(
        "src.tender_research.rag.job_runner.complete_job"
    ) as mock_complete:
        run_prepare_job("job-prepare-1", {"registry_number": "0323100010326000013"})

    mock_prepare.assert_called_once()
    assert mock_progress.call_count >= 1
    mock_complete.assert_called_once()
    session.close.assert_called_once()


def test_run_analyze_job_completes_and_saves_history_link() -> None:
    session = MagicMock()
    analyze_result = TenderAnalysisResult(
        status="completed",
        registry_number="0323100010326000013",
        sections=[],
        sections_count=10,
        sources_count=30,
        analysis_mode="fast",
        report_markdown="# Preview",
        report_path="data/rag/reports/test.md",
        used_llm=True,
        duration_seconds=18.4,
        timings={"total_seconds": 18.4},
        per_section_timings=[],
        run_id="run-123",
    )

    with patch("src.tender_research.rag.job_runner._get_session", return_value=session), patch(
        "src.tender_research.rag.job_runner.mark_job_running"
    ), patch(
        "src.tender_research.rag.job_runner.analyze_tender",
        return_value=analyze_result,
    ) as mock_analyze, patch(
        "src.tender_research.rag.job_runner.update_job_progress"
    ) as mock_progress, patch(
        "src.tender_research.rag.job_runner.complete_job"
    ) as mock_complete:
        run_analyze_job("job-analyze-1", {"registry_number": "0323100010326000013", "use_llm": True, "save_report": True})

    mock_analyze.assert_called_once()
    analyze_kwargs = mock_analyze.call_args.kwargs
    assert analyze_kwargs["registry_number"] == "0323100010326000013"
    assert analyze_kwargs["use_llm"] is True
    assert analyze_kwargs["save_report"] is True
    assert analyze_kwargs["limit"] is None
    assert analyze_kwargs["analysis_mode"] == "balanced"
    assert mock_progress.call_count >= 1
    mock_complete.assert_called_once()
    kwargs = mock_complete.call_args.kwargs
    assert kwargs["result"]["analysis_run_id"] == "run-123"
    assert kwargs["result"]["run_id"] == "run-123"
    assert kwargs["result"]["analysis_mode"] == "fast"
    assert kwargs["result"]["duration_seconds"] == 18.4
    assert kwargs["analysis_run_id"] == "run-123"
    assert kwargs["report_path"] == "data/rag/reports/test.md"
    session.close.assert_called_once()


def test_run_analyze_job_preserves_request_parameters() -> None:
    session = MagicMock()
    analyze_result = TenderAnalysisResult(
        status="completed",
        registry_number="0323100010326000013",
        sections=[],
        sections_count=10,
        sources_count=12,
        analysis_mode="fast",
        report_markdown="# Preview",
        report_path="data/rag/reports/test.md",
        used_llm=True,
        run_id="run-params",
    )

    request = {
        "registry_number": "0323100010326000013",
        "provider": "llama_cpp",
        "model": "Qwen3-Embedding-4B",
        "base_url": "http://127.0.0.1:8090/v1",
        "use_llm": True,
        "llm_base_url": "http://127.0.0.1:8088/v1",
        "llm_model": "/Users/master/models/Qwen2.5-14B-Instruct-Q4_K_M.gguf",
        "limit": 8,
        "analysis_mode": "fast",
        "llm_timeout_seconds": 90,
        "max_context_chars_per_section": 4000,
        "max_chunks_per_section": 3,
        "save_report": True,
        "source": "api",
    }

    with patch("src.tender_research.rag.job_runner._get_session", return_value=session), patch(
        "src.tender_research.rag.job_runner.mark_job_running"
    ), patch(
        "src.tender_research.rag.job_runner.analyze_tender",
        return_value=analyze_result,
    ) as mock_analyze, patch(
        "src.tender_research.rag.job_runner.update_job_progress"
    ), patch(
        "src.tender_research.rag.job_runner.complete_job"
    ):
        run_analyze_job("job-analyze-params", request)

    assert mock_analyze.call_args.kwargs == {
        "registry_number": "0323100010326000013",
        "provider": "llama_cpp",
        "model": "Qwen3-Embedding-4B",
        "base_url": "http://127.0.0.1:8090/v1",
        "use_llm": True,
        "llm_base_url": "http://127.0.0.1:8088/v1",
        "llm_model": "/Users/master/models/Qwen2.5-14B-Instruct-Q4_K_M.gguf",
        "llm_timeout_seconds": 90,
        "limit": 8,
        "analysis_mode": "fast",
        "max_context_chars_per_section": 4000,
        "max_chunks_per_section": 3,
        "save_report": True,
        "record_history": True,
        "history_source": "api",
        "session": session,
        "progress_callback": mock_analyze.call_args.kwargs["progress_callback"],
    }
    session.close.assert_called_once()


def test_run_analyze_job_downgrades_zero_sources_to_warning_status() -> None:
    session = MagicMock()
    analyze_result = TenderAnalysisResult(
        status="completed",
        registry_number="0323100010326000013",
        sections=[],
        sections_count=10,
        sources_count=0,
        report_markdown="# Preview",
        report_path="data/rag/reports/test.md",
        used_llm=True,
        run_id="run-zero",
    )

    with patch("src.tender_research.rag.job_runner._get_session", return_value=session), patch(
        "src.tender_research.rag.job_runner.mark_job_running"
    ), patch(
        "src.tender_research.rag.job_runner.analyze_tender",
        return_value=analyze_result,
    ), patch(
        "src.tender_research.rag.job_runner.update_job_progress"
    ), patch(
        "src.tender_research.rag.job_runner.complete_job"
    ) as mock_complete:
        run_analyze_job("job-analyze-zero", {"registry_number": "0323100010326000013"})

    kwargs = mock_complete.call_args.kwargs
    assert kwargs["status"] == "completed_with_warnings"
    assert "Analysis completed, but no cited sources were found." in kwargs["warnings"]
    session.close.assert_called_once()


def test_run_analyze_job_failure_marks_failed() -> None:
    session = MagicMock()

    with patch("src.tender_research.rag.job_runner._get_session", return_value=session), patch(
        "src.tender_research.rag.job_runner.mark_job_running"
    ), patch(
        "src.tender_research.rag.job_runner.analyze_tender",
        side_effect=RuntimeError("embedding server unavailable"),
    ), patch(
        "src.tender_research.rag.job_runner.update_job_progress"
    ), patch(
        "src.tender_research.rag.job_runner.fail_job"
    ) as mock_fail:
        run_analyze_job("job-analyze-2", {"registry_number": "0323100010326000013"})

    mock_fail.assert_called_once()
    assert "embedding server unavailable" in mock_fail.call_args.kwargs["errors"][0]
    session.close.assert_called_once()


def test_run_analyze_job_progress_preserves_section_statuses() -> None:
    session = MagicMock()

    def fake_analyze(**kwargs):
        kwargs["progress_callback"](
            {
                "progress_percent": 42,
                "current_step": "section_analysis",
                "message": "2/10 — Условия контракта",
                "steps": [
                    {
                        "name": "section:contract_terms",
                        "title": "2/10 — Условия контракта",
                        "status": "running",
                        "progress_percent": 42,
                        "message": "Выполняем запрос к локальной LLM.",
                        "details": {
                            "section_id": "contract_terms",
                            "section_title": "Условия контракта",
                            "section_index": 2,
                            "total_sections": 10,
                        },
                    }
                ],
            }
        )
        return TenderAnalysisResult(
            status="completed",
            registry_number="0323100010326000013",
            sections=[],
            sections_count=10,
            sources_count=10,
            per_section_timings=[
                {
                    "section_id": "contract_terms",
                    "section_title": "Условия контракта",
                    "section_index": 2,
                    "status": "completed",
                    "retrieval_seconds": 0.2,
                    "llm_seconds": 1.1,
                    "duration_seconds": 1.3,
                    "chunks_retrieved": 3,
                    "chunks_used": 3,
                    "context_chars": 2500,
                    "context_tokens_estimate": 625,
                    "fallback_reason": None,
                }
            ],
        )

    with patch("src.tender_research.rag.job_runner._get_session", return_value=session), patch(
        "src.tender_research.rag.job_runner.mark_job_running"
    ), patch(
        "src.tender_research.rag.job_runner.analyze_tender",
        side_effect=fake_analyze,
    ), patch(
        "src.tender_research.rag.job_runner.update_job_progress"
    ) as mock_progress, patch(
        "src.tender_research.rag.job_runner.complete_job"
    ):
        run_analyze_job("job-analyze-progress", {"registry_number": "0323100010326000013"})

    progress_steps = mock_progress.call_args_list[-1].kwargs["steps"]
    section_step = next(step for step in progress_steps if step["name"] == "section:contract_terms")
    assert section_step["details"]["section_title"] == "Условия контракта"


def test_submit_analyze_job_redis_backend_enqueues_durable_envelope() -> None:
    from src.tender_research.rag.job_runner import submit_analyze_job

    queue = MagicMock()
    settings = SimpleNamespace(
        tender_research_job_backend="redis",
        tender_research_worker_queue_name="tender-analysis",
        tender_research_worker_max_attempts=3,
        tender_research_worker_visibility_timeout_seconds=300,
    )
    request = {"registry_number": "0848300045426000620", "source": "api"}

    with patch("src.tender_research.rag.job_runner.get_settings", return_value=settings), patch(
        "src.tender_research.rag.job_runner.build_worker_queue", return_value=queue
    ):
        submit_analyze_job("job-redis-1", request)

    envelope = queue.enqueue.call_args.args[0]
    assert envelope.queue_name == "tender-analysis"
    assert envelope.job_type == "analyze"
    assert envelope.run_id == "job-redis-1"
    assert envelope.payload == {"job_id": "job-redis-1", "request": request}
    assert envelope.attempt == 1
    assert envelope.max_attempts == 3


def test_submit_prepare_job_thread_backend_uses_explicit_executor() -> None:
    from src.tender_research.rag.job_runner import submit_prepare_job

    settings = SimpleNamespace(tender_research_job_backend="thread")
    future = object()
    with patch("src.tender_research.rag.job_runner.get_settings", return_value=settings), patch(
        "src.tender_research.rag.job_runner._EXECUTOR.submit", return_value=future
    ) as submit:
        submit_prepare_job("job-thread-1", {"registry_number": "0848300045426000620"})

    submit.assert_called_once()
