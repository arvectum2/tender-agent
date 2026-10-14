"""Opt-in product facade: full-corpus research without modifying frozen R3 analysis.

Wrap injected callables (not global monkeypatches), so existing tests and
module bootstrap keep their behavior. Source evidence remains unverified by
default even when the model JSON schema passes validation.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.modules.tender_operator_agent_demo.full_corpus_research import (
    build_research_brief,
    examine_llm_assertions,
    research_full_corpus,
)

_BASE_LIMITATION = (
    "Поиск выполнен по полным извлечённым оригиналам. Точное совпадение "
    "фрагмента и его SHA-256 подтверждает только происхождение текста, "
    "не правильность юридического толкования; PASSED LLM — проверка формата, "
    "а не достоверности. Требуется ручная проверка доказательств."
)


def _once(items: list[Any], message: str) -> None:
    if message not in items:
        items.append(message)


def _material_assertions(
    requirements: dict[str, Any], risks: list[dict[str, Any]],
) -> list[str]:
    values: list[str] = []
    for key in ("technical_requirements", "qualification_requirements",
                "document_requirements", "evaluation_criteria"):
        for value in requirements.get(key) or []:
            if isinstance(value, str) and value.strip():
                values.append(value)
    for item in risks:
        if isinstance(item, dict) and isinstance(item.get("description"), str):
            values.append(item["description"])
    return values


def run_with_full_corpus_research(
    handler: Callable[..., Any],
    run_id: str,
    **dependencies: Any,
) -> Any:
    """Wrap one actual run without changing AST-locked orchestration body."""
    collect_original = dependencies["_collect_documents"]
    project_original = dependencies["_build_output_payloads"]
    controlled_original = dependencies["_try_run_llm_workflow"]
    current_research: dict[str, Any] | None = None

    def collect(run: str, metadata: dict[str, Any]) -> list[Any]:
        nonlocal current_research
        documents = collect_original(run, metadata)
        report = research_full_corpus(documents, manifest=metadata.get("files"))
        metadata["source_research"] = report
        current_research = report
        limitations = metadata.setdefault("limitations", [])
        if not isinstance(limitations, list):
            limitations = []
            metadata["limitations"] = limitations
        _once(limitations, _BASE_LIMITATION)
        if report["unread_file_ids"]:
            _once(
                limitations,
                "Оригиналы без извлечённого текста: "
                + ", ".join(report["unread_file_ids"][:15])
                + ". Неустановленные требования считаются UNKNOWN, а не отсутствующими.",
            )
        if report["missing_research_topics"]:
            _once(
                limitations,
                "Не найдены явные фрагменты по темам: "
                + ", ".join(report["missing_research_topics"])
                + ". Это не подтверждает отсутствия соответствующих условий.",
            )
        return documents

    def controlled_model(**kwargs: Any) -> Any:
        import inspect

        if current_research is not None:
            params = inspect.signature(controlled_original).parameters
            if "source_research" in params:
                kwargs["source_research"] = build_research_brief(current_research)
        return controlled_original(**kwargs)

    def project(**kwargs: Any) -> dict[str, Any]:
        outputs = project_original(**kwargs)
        metadata = kwargs.get("metadata")
        if not isinstance(metadata, dict):
            return outputs
        research = metadata.get("source_research")
        if not isinstance(research, dict):
            return outputs
        requirements = kwargs.get("requirements")
        risks = kwargs.get("calibrated_risks")
        claims = _material_assertions(
            requirements if isinstance(requirements, dict) else {},
            risks if isinstance(risks, list) else [],
        )
        claim_index = examine_llm_assertions(research, claims)
        metadata["source_research_llm_claims"] = claim_index
        # Persist reviewable source locations separately from model assertions.
        # Existing outputs and public shape are preserved by adding optional
        # research keys in the existing trace and requirement payloads.
        trace = outputs.get("trace")
        if isinstance(trace, dict):
            trace["full_corpus_research"] = research
            trace["source_claim_assessment"] = claim_index
        requirement_payload = outputs.get("requirements")
        if isinstance(requirement_payload, dict):
            requirement_payload["full_corpus_research"] = research
            requirement_payload["source_claim_assessment"] = claim_index
        return outputs

    return handler(
        run_id,
        **{
            **dependencies,
            "_collect_documents": collect,
            "_try_run_llm_workflow": controlled_model,
            "_build_output_payloads": project,
        },
    )
