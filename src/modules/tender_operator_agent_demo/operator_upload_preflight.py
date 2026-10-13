"""Side-effect-free bounded preflight for batches of tender operator uploads.

Reject the whole batch before filesystem writes so a later rejected attachment
cannot leave a partial run or an attachment not reflected in run metadata.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from fastapi import HTTPException


def validate_operator_upload_batch(
    uploads: Sequence[tuple[str, str, bytes]],
    *,
    existing_file_count: int,
    existing_total_bytes: int,
    max_file_count: int,
    max_file_size_bytes: int,
    max_total_upload_bytes: int,
    sanitize_name: Callable[[str, int], tuple[str, str]],
) -> None:
    if not uploads:
        raise HTTPException(status_code=400, detail="At least one file must be uploaded")
    if existing_file_count + len(uploads) > max_file_count:
        raise HTTPException(status_code=400, detail=f"Too many files. Limit: {max_file_count}")
    total_bytes = sum(len(content) for _name, _content_type, content in uploads)
    if existing_total_bytes + total_bytes > max_total_upload_bytes:
        raise HTTPException(
            status_code=400,
            detail="Total upload size exceeds the allowed limit",
        )
    for index, (filename, _content_type, content) in enumerate(
        uploads, start=existing_file_count + 1
    ):
        if len(content) > max_file_size_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds the allowed size limit: {filename}",
            )
        sanitize_name(filename, index)
