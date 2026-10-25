"""Product-owned operator append-files orchestration.

The original entire body is preserved to keep upload validation, persisted
metadata/status transitions and historical event ordering unchanged.
"""
from __future__ import annotations

from typing import Any


def append_files_to_demo_run(
    *,
    run_id: str,
    uploads: list[tuple[str, str, bytes]],
    _load_metadata: Any,
    validate_operator_upload_batch: Any,
    MAX_FILE_COUNT: Any,
    MAX_FILE_SIZE_BYTES: Any,
    MAX_TOTAL_UPLOAD_BYTES: Any,
    sanitize_demo_filename: Any,
    _input_dir: Any,
    Path: Any,
    build_demo_file_descriptor: Any,
    _derive_role_hint: Any,
    append_demo_run_event: Any,
    TenderOperatorUploadedRunStatus: Any,
    save_demo_run_metadata: Any,
    TenderOperatorUploadedRunCreateResponse: Any,
    datetime: Any,
) -> Any:
    metadata = _load_metadata(run_id)
    existing_files = metadata.get("files", [])
    validate_operator_upload_batch(
        uploads,
        existing_file_count=len(existing_files),
        existing_total_bytes=sum(int(item.get("size_bytes", 0)) for item in existing_files),
        max_file_count=MAX_FILE_COUNT,
        max_file_size_bytes=MAX_FILE_SIZE_BYTES,
        max_total_upload_bytes=MAX_TOTAL_UPLOAD_BYTES,
        sanitize_name=sanitize_demo_filename,
    )

    input_dir = _input_dir(run_id)
    warnings = list(metadata.get("warnings", []))
    start_index = len(existing_files) + 1
    added_files = 0

    for index, (filename, content_type, content) in enumerate(uploads, start=start_index):
        original_name, stored_name = sanitize_demo_filename(filename, index)
        file_id = f"FILE-{index:02d}"
        (input_dir / stored_name).write_bytes(content)
        if Path(filename).name != filename or ".." in filename.replace("\\", "/"):
            warnings.append(f"Filename '{filename}' was normalized for safe local storage.")
        existing_files.append(
            build_demo_file_descriptor(
                file_id=file_id,
                original_name=original_name,
                stored_name=stored_name,
                role_hint=_derive_role_hint(stored_name),
                size_bytes=len(content),
                content_type=content_type,
                source="manual_upload",
            )
        )
        append_demo_run_event(
            run_id,
            "attachment_saved",
            f"Документ '{original_name}' добавлен в прогон вручную.",
            {"stored_name": stored_name, "source": "manual_upload"},
        )
        added_files += 1

    metadata["files"] = existing_files
    metadata["warnings"] = sorted(set(warnings))
    if metadata.get("status") == TenderOperatorUploadedRunStatus.DOCS_REQUIRED.value:
        metadata["status"] = TenderOperatorUploadedRunStatus.READY_TO_ANALYZE.value
    if metadata.get("attachments_status") in {"manual_upload_required", "unavailable_in_demo", "source_requires_authorization"}:
        metadata["attachments_status"] = "manual_upload_received"
    metadata["downloaded_files_count"] = len(existing_files)
    metadata["manual_upload_required"] = False
    save_demo_run_metadata(run_id, metadata)
    append_demo_run_event(
        run_id,
        "manual_upload_received",
        "Оператор добавил документы в существующий run.",
        {"added_files": added_files},
    )
    return TenderOperatorUploadedRunCreateResponse(
        run_id=run_id,
        status=TenderOperatorUploadedRunStatus(metadata["status"]),
        created_at=datetime.fromisoformat(metadata["created_at"]),
        file_count=len(existing_files),
        warnings=metadata.get("warnings", []),
        limitations=metadata.get("limitations", []),
    )
