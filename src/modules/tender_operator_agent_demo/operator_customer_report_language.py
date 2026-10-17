"""Operator report user-facing language and diagnostic separation.

Human-readable reports cannot display internal execution IDs, adapter names,
transport exceptions or internal machine statuses. Evidence/retrieval audit
is preserved in original structured metadata; never delete that audit.
"""
from __future__ import annotations

import re

_INTERNAL_STATUS = re.compile(
    r"(?:\bno_data\b|\bgetDocsIP\b|\bSOURCE_UNAVAILABLE\b|"
    r"\bHTTP\s+[345]\d\d\b|\bTraceback\b|"
    r"\b(?:JSONDecodeError|KeyError|RuntimeError|TypeError)\b|"
    r"\bfallback_deterministic_adapter\b|\barchive_download_failed\b|"
    r"\bSOURCE_RECORD_ID_MISMATCH\b)",
    re.IGNORECASE,
)
_PREFIX_FIELDS = (
    "- Run ID:", "- Режим анализа:", "- Код рекомендации:",
    "- Статус:", "- Статус скачивания:", "- Ручная загрузка требовалась:",
)
_STATUS_NOTE = (
    "Часть сведений не удалось подтвердить по исходным документам. "
    "Для заключения требуется дополнительная проверка первоисточника."
)


def readable_document_text_state(value: str | None) -> str:
    return (
        "Текст документа доступен для анализа"
        if str(value or "").casefold() == "extracted"
        else "Содержание документа требует проверки"
    )


def readable_document_origin(value: str | None) -> str:
    origin = str(value or "").lower()
    if "eis" in origin or "zakupki" in origin:
        return "Официальный источник ЕИС"
    if "upload" in origin or "local" in origin:
        return "Файл, предоставленный для анализа"
    return "Источник документа требует уточнения"


def readable_source(value: str | None) -> str:
    source = str(value or "").lower()
    if "getdocs_ip" in source or "zakupki" in source or "eis" in source:
        return "Единая информационная система в сфере закупок"
    if source in {"demo_local", "upload", "uploaded"}:
        return "Документы, предоставленные для анализа"
    return "Источник требует подтверждения"


def customer_narrative(value: str | None) -> str:
    text = str(value or "").strip()
    return _STATUS_NOTE if _INTERNAL_STATUS.search(text) else text


def sanitize_customer_report_markdown(report: str) -> str:
    """Keep substantive sections and limitations, rewrite only machine internals."""
    lines = []
    for original in report.splitlines():
        line = original.strip()
        if line.startswith(_PREFIX_FIELDS):
            continue
        if line.startswith("- Источник:"):
            lines.append("- Источник: " + readable_source(line.partition(":")[2].strip()))
            continue
        if re.search(r"\bdownload=[^|]*\|\s*text=[^|]*\|\s*source=", line):
            head, _, rest = original.partition("|")
            text_state = re.search(r"\btext=([^|\s]+)", rest)
            origin = re.search(r"\bsource=([^|\s]+)", rest)
            lines.append(
                f"{head.strip()} — {readable_document_text_state(text_state.group(1) if text_state else None)}; "
                f"{readable_document_origin(origin.group(1) if origin else None)}"
            )
            continue
        if _INTERNAL_STATUS.search(line):
            if line.startswith(("- ", "* ")):
                prefix=line[:2]
                lines.append(prefix + _STATUS_NOTE)
            else:
                lines.append(_STATUS_NOTE)
            continue
        lines.append(original.replace("# Отчёт по загруженному прогону тендерного агента", "# Анализ закупки"))
    output="\n".join(lines).strip()+"\n"
    if _INTERNAL_STATUS.search(output):
        raise ValueError("internal execution status must not reach client report")
    return output
