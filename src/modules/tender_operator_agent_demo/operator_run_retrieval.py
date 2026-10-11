"""Procurement-owned stored run projection.

Read-only projection from persisted report/step/economic data to the operator
API response. Dependency injection preserves all legacy runtime patch points;
the original projection body remains AST-identical.
"""
from __future__ import annotations

from typing import Any


def project_uploaded_run(
    run_id: str,
    *,
    _load_metadata: Any,
    DemoStep: Any,
    DemoFinalRecommendation: Any,
    _output_dir: Any,
    _read_json: Any,
    _build_final_recommendation: Any,
    _load_report_json: Any,
    DemoStepStatus: Any,
    _coerce_quote_comparison_payload: Any,
    _coerce_economics_summary_payload: Any,
    _report_html_path: Any,
    _ensure_procurement_blocked_report_html: Any,
    TenderOperatorUploadedRunResponse: Any,
    datetime: Any,
    TenderOperatorUploadedRunStatus: Any,
    TenderOperatorUploadedFile: Any,
    load_demo_run_events: Any,
) -> Any:
    metadata = _load_metadata(run_id)
    steps: list[DemoStep] = []
    final_recommendation: DemoFinalRecommendation | None = None
    quote_comparison = None
    economics_summary = None
    outputs_path = _output_dir(run_id)
    if (outputs_path / "final_recommendation.json").is_file() and (outputs_path / "trace.json").is_file():
        outputs = {
            "final_recommendation": _read_json(outputs_path / "final_recommendation.json"),
            "trace": _read_json(outputs_path / "trace.json"),
        }
        final_recommendation = _build_final_recommendation(outputs)
    if (outputs_path / "report.json").is_file():
        report_json = _load_report_json(run_id)
        steps = [
            DemoStep.model_validate(
                {
                    "key": f"section-{index}",
                    "order": index,
                    "title": section["title"],
                    "short_title": section["title"],
                    "status": DemoStepStatus.DONE,
                    "description": section["title"],
                    "agent_action": section["title"],
                    "result_summary": section["title"],
                    "findings": section.get("items", []),
                    "human_review": [],
                    "trace": "Saved report section.",
                    "result_sections": [],
                }
            )
            for index, section in enumerate(report_json.get("sections", []), start=1)
        ]
    stored_steps_path = outputs_path / "steps.json"
    if stored_steps_path.is_file():
        steps = [DemoStep.model_validate(item) for item in _read_json(stored_steps_path).get("steps", [])]
    quote_path = outputs_path / "quotes_comparison.json"
    economics_path = outputs_path / "economics.json"
    if quote_path.is_file():
        quote_comparison = _coerce_quote_comparison_payload(_read_json(quote_path))
    if economics_path.is_file():
        economics_summary = _coerce_economics_summary_payload(_read_json(economics_path))
    report_path = _report_html_path(run_id)
    if not report_path.is_file():
        report_path = _ensure_procurement_blocked_report_html(run_id)

    return TenderOperatorUploadedRunResponse(
        run_id=metadata["run_id"],
        created_at=datetime.fromisoformat(metadata["created_at"]),
        mode=metadata["mode"],
        tender_title=metadata["tender_title"],
        tender_category=metadata["tender_category"],
        customer_name=metadata["customer_name"],
        notes=metadata.get("notes"),
        status=TenderOperatorUploadedRunStatus(metadata["status"]),
        analysis_mode=metadata.get("analysis_mode", "not_started"),
        files=[TenderOperatorUploadedFile.model_validate(item) for item in metadata.get("files", [])],
        limitations=metadata.get("limitations", []),
        warnings=metadata.get("warnings", []),
        human_in_the_loop=metadata.get("human_in_the_loop", True),
        external_actions=metadata.get("external_actions", False),
        no_platform_submission=metadata.get("no_platform_submission", True),
        no_email_sending=metadata.get("no_email_sending", True),
        no_digital_signature=metadata.get("no_digital_signature", True),
        procurement_source=metadata.get("procurement_source"),
        procurement_id=metadata.get("procurement_id"),
        procurement_url=metadata.get("procurement_url"),
        procurement_query=metadata.get("procurement_query"),
        procurement_notice_number=metadata.get("notice_number"),
        procurement_law=metadata.get("law"),
        token_owner=metadata.get("token_owner"),
        soap_method=metadata.get("soap_method"),
        eis_ref_id=metadata.get("getdocs_ref_id"),
        archive_url_present=metadata.get("archive_url_present", False),
        archive_downloaded=metadata.get("archive_downloaded", False),
        archive_download_status=metadata.get("archive_download_status"),
        archive_download_attempts=metadata.get("archive_download_attempts", 0),
        archive_source_host=metadata.get("archive_source_host"),
        archive_source_path=metadata.get("archive_source_path"),
        documents_extracted_count=metadata.get("documents_extracted_count", 0),
        downloaded_files_count=metadata.get("downloaded_files_count", len(metadata.get("files", []))),
        manual_upload_required=metadata.get("manual_upload_required", False),
        attachments_status=metadata.get("attachments_status"),
        steps=steps,
        final_recommendation=final_recommendation,
        quote_comparison=quote_comparison,
        economics_summary=economics_summary,
        report_html_url=f"/demo/tender-agent/runs/{run_id}/report" if report_path and report_path.is_file() else None,
        report_download_url=f"/api/demo/tender-agent/runs/{run_id}/report/download" if report_path and report_path.is_file() else None,
        uploaded_files_note="Используются только локальные данные. Абсолютные server-path намеренно скрыты из интерфейса.",
        events=load_demo_run_events(run_id),
        document_relevance=metadata.get("document_relevance"),
    )
