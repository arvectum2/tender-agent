"""Projection of validated-schema LLM output as UNVERIFIED review candidates.

A schema-valid model answer is never synonymous with a source-attested fact.
This adapter only applies to the legacy controlled operator LLM mode. Frozen
R7/deterministic outputs and R10.1 claim-bound evidence logic are unchanged.
"""

from __future__ import annotations

from typing import Any


def _safe_text(value: Any, *, limit: int = 450) -> str | None:
    if not isinstance(value, str):
        return None
    clean = " ".join(value.split())
    return clean[:limit] if clean else None


def candidate_requirement_rows(payload: dict[str, Any]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for field, category in (
        ("technical_requirements", "техническое"),
        ("document_requirements", "документы"),
        ("qualification_requirements", "квалификация"),
    ):
        values = payload.get(field)
        if not isinstance(values, list):
            continue
        for raw in values:
            title = _safe_text(raw)
            if not title or title.casefold() in seen:
                continue
            seen.add(title.casefold())
            results.append({
                "title": "[LLM — проверить по ТЗ] " + title,
                "detail": "Неподтверждённое предложение модели; нужна цитата и ссылка на исходный файл.",
                "source": "unverified_llm",
                "verification_status": "unverified",
                "type": category,
            })
            if len(results) >= 18:
                return results
    return results


def candidate_risks(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for risk in payload:
        if not isinstance(risk, dict):
            continue
        clause = _safe_text(risk.get("clause"))
        if not clause:
            continue
        results.append({
            "clause": "[Гипотеза LLM — проверить договор] " + clause,
            "impact": _safe_text(risk.get("impact")) or "Оценить влияние после проверки договора.",
            "mitigation": _safe_text(risk.get("mitigation")) or "Проверить условия по оригиналу.",
            # Never turn a model-only prediction into an automatic hard blocker.
            "classification": "commercially_material_risk",
            "source_status": "unverified_llm",
            "evidence_ids": "",
            "evidence_locators": [],
        })
        if len(results) >= 16:
            break
    return results


def candidate_supplier_questions(payload: list[dict[str, Any]]) -> list[str]:
    questions: list[str] = []
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        q = _safe_text(item.get("question"))
        if not q or q.casefold() in seen:
            continue
        seen.add(q.casefold())
        questions.append("[LLM — согласовать перед отправкой] " + q)
        if len(questions) >= 15:
            break
    return questions


def candidate_rfq_sections(payload: dict[str, Any]) -> list[str]:
    if not isinstance(payload, dict):
        return []
    result: list[str] = []
    for field in ("intro", "closing_note"):
        item = _safe_text(payload.get(field))
        if item:
            result.append("[Черновик LLM — согласовать] " + item)
    for field in ("requirements_summary", "supplier_questions", "requested_response_items", "commercial_terms"):
        entries = payload.get(field)
        if not isinstance(entries, list):
            continue
        for item in entries:
            text = _safe_text(item)
            if text:
                result.append("[Черновик LLM — согласовать] " + text)
            if len(result) >= 20:
                break
        if len(result) >= 20:
            break
    return result
