"""Product-owned operator run creation workflow.

Entire original body preserved, including fail-closed upload batch preflight,
economics input validation before filesystem writes, metadata and event order.
"""
from __future__ import annotations

from typing import Any


def create_uploaded_demo_run(
    *,
    tender_title: str,
    tender_category: str,
    customer_name: str,
    notes: str | None,
    target_margin_percent: float | None,
    logistics_reserve_percent: float | None,
    risk_reserve_percent: float | None,
    payment_delay_days: int | None,
    uploads: list[tuple[str, str, bytes]],
    HTTPException: Any,
    validate_operator_upload_batch: Any,
    MAX_FILE_COUNT: Any,
    MAX_FILE_SIZE_BYTES: Any,
    MAX_TOTAL_UPLOAD_BYTES: Any,
    sanitize_demo_filename: Any,
    _sanitize_percent: Any,
    DEFAULT_TARGET_MARGIN_PERCENT: Any,
    DEFAULT_LOGISTICS_RESERVE_PERCENT: Any,
    DEFAULT_RISK_RESERVE_PERCENT: Any,
    _sanitize_delay_days: Any,
    DEFAULT_PAYMENT_DELAY_DAYS: Any,
    make_demo_run_id: Any,
    ensure_demo_run_structure: Any,
    Path: Any,
    build_demo_file_descriptor: Any,
    _derive_role_hint: Any,
    _safe_datetime: Any,
    TenderOperatorUploadedRunStatus: Any,
    save_demo_run_metadata: Any,
    append_demo_run_event: Any,
    TenderOperatorUploadedRunCreateResponse: Any,
    datetime: Any,
) -> Any:
    if not tender_title.strip():
        raise HTTPException(status_code=400, detail="tender_title is required")
    validate_operator_upload_batch(
        uploads,
        existing_file_count=0,
        existing_total_bytes=0,
        max_file_count=MAX_FILE_COUNT,
        max_file_size_bytes=MAX_FILE_SIZE_BYTES,
        max_total_upload_bytes=MAX_TOTAL_UPLOAD_BYTES,
        sanitize_name=sanitize_demo_filename,
    )

    target_margin_percent = _sanitize_percent(
        target_margin_percent,
        default=DEFAULT_TARGET_MARGIN_PERCENT,
        field_name="target_margin_percent",
    )
    logistics_reserve_percent = _sanitize_percent(
        logistics_reserve_percent,
        default=DEFAULT_LOGISTICS_RESERVE_PERCENT,
        field_name="logistics_reserve_percent",
    )
    risk_reserve_percent = _sanitize_percent(
        risk_reserve_percent,
        default=DEFAULT_RISK_RESERVE_PERCENT,
        field_name="risk_reserve_percent",
    )
    payment_delay_days = _sanitize_delay_days(payment_delay_days, default=DEFAULT_PAYMENT_DELAY_DAYS)

    run_id = make_demo_run_id()
    structure = ensure_demo_run_structure(run_id, exist_ok=False)
    input_dir = structure["input_dir"]

    warnings: list[str] = []
    files: list[dict[str, Any]] = []

    for index, (filename, content_type, content) in enumerate(uploads, start=1):
        original_name, stored_name = sanitize_demo_filename(filename, index)
        file_id = f"FILE-{index:02d}"
        target = input_dir / stored_name
        target.write_bytes(content)
        if Path(filename).name != filename or ".." in filename.replace("\\", "/"):
            warnings.append(f"Filename '{filename}' was normalized for safe local storage.")
        files.append(
            build_demo_file_descriptor(
                file_id=file_id,
                original_name=original_name,
                stored_name=stored_name,
                role_hint=_derive_role_hint(stored_name),
                size_bytes=len(content),
                content_type=content_type,
            )
        )

    metadata = {
        "run_id": run_id,
        "created_at": _safe_datetime(),
        "mode": "uploaded_demo",
        "tender_title": tender_title.strip(),
        "tender_category": tender_category.strip() or "Электротехническое оборудование",
        "customer_name": customer_name.strip() or "Промышленный заказчик",
        "notes": notes.strip() if notes and notes.strip() else None,
        "status": TenderOperatorUploadedRunStatus.READY_TO_ANALYZE.value,
        "analysis_mode": "not_started",
        "economics_inputs": {
            "target_margin_percent": target_margin_percent,
            "logistics_reserve_percent": logistics_reserve_percent,
            "risk_reserve_percent": risk_reserve_percent,
            "payment_delay_days": payment_delay_days,
        },
        "files": files,
        "warnings": warnings,
        "limitations": [
            "Только демо- и пилотный режим.",
            "Без внешних действий, без отправки писем, без подачи на площадку, без ЭЦП.",
        ],
        "human_in_the_loop": True,
        "external_actions": False,
        "no_platform_submission": True,
        "no_email_sending": True,
        "no_digital_signature": True,
    }
    save_demo_run_metadata(run_id, metadata)
    append_demo_run_event(
        run_id,
        "run_created",
        "Создан демонстрационный прогон с ручной загрузкой документов.",
        {"mode": "uploaded_demo", "file_count": len(files)},
    )
    return TenderOperatorUploadedRunCreateResponse(
        run_id=run_id,
        status=TenderOperatorUploadedRunStatus.READY_TO_ANALYZE,
        created_at=datetime.fromisoformat(metadata["created_at"]),
        file_count=len(files),
        warnings=warnings,
        limitations=metadata["limitations"],
    )
