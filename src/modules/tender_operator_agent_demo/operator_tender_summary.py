"""Product-owned source-first tender summary projection.

The report generation timestamp is distinct from the verified submission
deadline. If no source contains a deadline, preserve null (UNKNOWN).
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


def build_operator_tender_summary(
    *,
    metadata: dict[str, Any],
    documents: list[Any],
    preliminary_analysis: dict[str, Any],
    analysis_mode: str,
    _safe_datetime: Callable[[], Any],
    submission_deadline_from_metadata: Callable[[dict[str, Any]], str | None],
) -> dict[str, Any]:
    return {
        "run_id": metadata["run_id"],
        "prepared_at": _safe_datetime(),
        "title": metadata["tender_title"],
        "procedure_type": "Поиск закупки + intake" if metadata.get("mode") == "procurement_search_intake" else "Загруженный demo run",
        "customer": metadata["customer_name"],
        "category": metadata["tender_category"],
        "submission_deadline": submission_deadline_from_metadata(metadata),
        "analysis_status": metadata["status"],
        "procurement_code": metadata.get("procurement_id") or metadata["run_id"].upper(),
        "documents": [
            {
                "name": doc.display_name,
                "role": doc.role,
                "pages": 1,
            }
            for doc in documents
        ],
        "document_signals": [
            f"Режим создания run: {metadata.get('mode', 'uploaded_demo')}.",
            f"Загружено файлов: {len(metadata.get('files', []))}.",
            f"Файлов с извлечённым текстом: {len([doc for doc in documents if doc.text])}.",
            f"Режим анализа: {analysis_mode}.",
        ],
        "preliminary_analysis": preliminary_analysis,
    }
