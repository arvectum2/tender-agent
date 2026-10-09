"""Read-only projection of explicitly UNVERIFIED model suggestions for export.

Never creates or edits original procurement evidence, and never interprets
unsourced LLM statements as legally or commercially verified facts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_LIMITS = (
    ("requirements", "Требования для проверки", 12),
    ("contract_risks", "Гипотезы рисков для проверки", 8),
    ("supplier_questions", "Вопросы для согласования", 10),
    ("rfq_draft", "Черновик RFQ для согласования", 12),
)


def _safe_line(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    return text[:360] if text else None


def review_only_export_sections(output_dir: Path) -> list[tuple[str, list[str]]]:
    """Return headings and bounded labels only if stored review tags are present."""
    sections: list[tuple[str, list[str]]] = []
    for stem, heading, limit in _LIMITS:
        path = output_dir / f"{stem}.json"
        if not path.is_file() or path.is_symlink():
            continue
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue
        values: list[str] = []
        if stem == "requirements":
            for row in obj.get("requirements", []):
                if not isinstance(row, dict) or row.get("verification_status") != "unverified" or row.get("source") != "unverified_llm":
                    continue
                if (line := _safe_line(row.get("title"))):
                    values.append(line)
        elif stem == "contract_risks":
            for row in obj.get("risks", []):
                if not isinstance(row, dict) or row.get("source_status") != "unverified_llm" or row.get("status") != "requires_review":
                    continue
                if (line := _safe_line(row.get("risk"))):
                    values.append(line)
        elif stem == "supplier_questions":
            for row in obj.get("questions", []):
                if (line := _safe_line(row)) and line.startswith("[LLM"):
                    values.append(line)
        else:
            for row in obj.get("sections", []):
                if (line := _safe_line(row)) and line.startswith("[Черновик LLM"):
                    values.append(line)
        if values:
            sections.append((heading, values[:limit]))
    return sections
