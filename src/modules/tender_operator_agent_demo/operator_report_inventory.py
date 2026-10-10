"""Product report inventory projection from persisted upload metadata.

Do not invent extracted text, official source provenance, or document status.
"""

from __future__ import annotations

from typing import Any


def document_type_label(item: dict[str, Any]) -> str:
    role = str(item.get("role_hint") or item.get("document_kind") or "").strip().lower()
    labels = {
        "notice": "электронное извещение ЕИС",
        "eis_notice": "электронное извещение ЕИС",
        "technical_spec": "техническое задание / техническая часть",
        "technical_specification": "техническое задание / техническая часть",
        "procurement_object_description": "описание объекта закупки",
        "contract_draft": "проект контракта",
        "specification": "спецификация",
        "estimate": "смета",
        "form": "форма",
        "attachment": "приложение",
        "supporting": "вспомогательный документ",
    }
    return labels.get(role, "документ закупки")


def build_downloaded_documents_inventory(metadata: dict[str, Any]) -> list[dict[str, str]]:
    inventory: list[dict[str, str]] = []
    for item in metadata.get("files", []):
        inventory.append(
            {
                "name": str(item.get("display_name") or item.get("original_name") or "Документ"),
                "type": document_type_label(item),
                "download_status": "downloaded",
                "text_status": "extracted" if item.get("extracted_text_available") else str(item.get("text_extraction_status") or "pending"),
                "source": str(item.get("source_type") or item.get("source") or "runtime"),
            }
        )
    return inventory
