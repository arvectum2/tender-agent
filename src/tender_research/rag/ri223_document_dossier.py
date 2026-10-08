"""Review-only document evidence projection for verified public RI223 tenders.

Only cites quotes returned by the existing Data Platform RAG analyzer. This is
neither a new retriever nor a legal/commercial/risk scoring decision engine.
"""

from __future__ import annotations

from typing import Any

from src.tender_research.rag.schemas import TenderAnalysisSection

# Keep the canonical ten-section engine; this is a bounded view of relevant
# sections and of *retrieved evidence*, not a separate question registry.
_DOMAIN_SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("technical_scope", "Технический предмет и объём", "subject"),
    ("qualification", "Требования к участнику", "customer_requirements"),
    ("application", "Состав заявки", "application_composition"),
    ("evaluation", "Критерии оценки", "evaluation_criteria"),
    ("contract", "Условия договора", "contract_terms"),
    ("participation", "Ограничения участия", "restrictions_benefits"),
    ("schedule", "Сроки подачи и исполнения", "deadlines"),
)
_MAX_SOURCES_PER_DOMAIN = 3
_MAX_EXCERPT_CHARS = 420
_MAX_FILE_NAME_CHARS = 180
_MAX_CHUNK_ID_CHARS = 128


def build_ri223_document_dossier(
    *,
    law_type: str | None,
    registry_number: str,
    sections: list[TenderAnalysisSection],
    source_facts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return a fixed, source-cited review matrix or an empty non-RI223 result.

    REQUIREMENTS_ARE_UNVERIFIED is intentional even with cited excerpts:
    finding the right fragment does not establish legal applicability or fit.
    """
    if (
        law_type != "223fz"
        or not source_facts
        or not registry_number
        or not any(
            isinstance(fact, dict)
            and fact.get("interpretation") == "XML_SOURCE_OBSERVATION_ONLY"
            and isinstance(fact.get("evidence"), dict)
            and fact["evidence"].get("source") == "RI223_getDocsIP"
            for fact in source_facts
        )
    ):
        return []

    lots = {
        (fact.get("fields") or {}).get("ordinal_number")
        for fact in source_facts
        if isinstance(fact, dict)
        and fact.get("kind") == "lot"
        and isinstance(fact.get("fields"), dict)
        and (fact["fields"].get("ordinal_number"))
    }
    lot_scope = "UNRESOLVED_MULTI_LOT" if len(lots) > 1 else "LOT_SCOPE_NOT_CONFIRMED"
    section_by_id = {section.id: section for section in sections}
    result: list[dict[str, Any]] = []

    for key, title, section_id in _DOMAIN_SECTIONS:
        section = section_by_id.get(section_id)
        references: list[dict[str, str]] = []
        seen_chunks: set[str] = set()
        if section is not None:
            for source in section.sources:
                if source.registry_number != registry_number:
                    continue
                chunk_id = str(source.chunk_id or "").strip()
                excerpt = " ".join(str(source.quote_preview or "").split())
                document_id = str(source.document_id or "").strip()
                file_name = str(source.document_file_name or "").strip()
                if not (chunk_id and excerpt and document_id and file_name):
                    continue
                if chunk_id in seen_chunks:
                    continue
                seen_chunks.add(chunk_id)
                references.append(
                    {
                        "registry_number": registry_number,
                        "document_id": document_id,
                        "document_file_name": file_name[:_MAX_FILE_NAME_CHARS],
                        "chunk_id": chunk_id[:_MAX_CHUNK_ID_CHARS],
                        "source_excerpt": excerpt[:_MAX_EXCERPT_CHARS],
                        "evidence_type": "DATA_PLATFORM_DOCUMENT_CHUNK",
                    }
                )
                if len(references) >= _MAX_SOURCES_PER_DOMAIN:
                    break
        result.append(
            {
                "domain": key,
                "title": title,
                "analysis_section_id": section_id,
                "analysis_section_status": section.status if section else "no_context",
                "status": "NEEDS_HUMAN_DOCUMENT_REVIEW"
                if references
                else "NO_CITED_DOCUMENT_EXCERPT",
                "requirements_verified": False,
                "supplier_fit": "UNKNOWN",
                "contract_risk": "NOT_ASSESSED",
                "decision": "NOT_DECIDED",
                "lot_scope": lot_scope,
                "source_excerpts": references,
            }
        )
    return result


def render_ri223_document_dossier(dossier: list[dict[str, Any]]) -> list[str]:
    if not dossier:
        return []
    lines = [
        "## Матрица документальных свидетельств для проверки (223-ФЗ)",
        "",
        (
            "Это найденные Data Platform фрагменты для экспертной проверки, "
            "а не установленные требования, проверка соответствия поставщика "
            "или решение GO/NO-GO. Отсутствие цитаты не доказывает отсутствие "
            "требования в документации."
        ),
        "",
    ]
    for item in dossier:
        lines.append("### " + item["title"])
        lines.append(
            "Статус: " + item["status"] + "; соответствие поставщика: UNKNOWN; "
            "оценка рисков: NOT_ASSESSED; решение: NOT_DECIDED."
        )
        if item["lot_scope"] == "UNRESOLVED_MULTI_LOT":
            lines.append(
                "Лот: применимость найденных фрагментов к отдельным лотам "
                "не подтверждена, требуется раздельная проверка."
            )
        if not item["source_excerpts"]:
            lines.append(
                "Документальная цитата не найдена в данном разделе поиска. "
                "Проверить полный комплект документации вручную."
            )
        for evidence in item["source_excerpts"]:
            lines.append(
                "- "
                + evidence["document_file_name"]
                + " (chunk_id: "
                + evidence["chunk_id"]
                + ", document_id: "
                + evidence["document_id"]
                + "): "
                + evidence["source_excerpt"]
            )
        lines.append("")
    return lines
