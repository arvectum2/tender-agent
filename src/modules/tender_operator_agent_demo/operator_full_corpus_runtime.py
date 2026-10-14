"""Opt-in product facade: full-corpus research without modifying frozen R3 analysis.

Wrap injected callables (not global monkeypatches), so existing tests and
module bootstrap keep their behavior. Source evidence remains unverified by
default even when the model JSON schema passes validation.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from src.modules.tender_operator_agent_demo.full_corpus_clause_review import (
    audit_model_contract_clause_references,
)
from src.modules.tender_operator_agent_demo.full_corpus_modality_audit import (
    audit_source_modalities,
)
from src.modules.tender_operator_agent_demo.source_claim_proof import (
    audit_model_eis_summary,
    bind_source_span,
)
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
        original_documents = kwargs.get("documents")
        # All downstream clause/model audits MUST share the same trust
        # boundary as full-corpus indexing. A document rejected for a
        # declared hash mismatch/duplicate ID cannot re-enter as "evidence".
        accepted = {
            (str(row["file_id"]).casefold(), str(row["text_sha256"]))
            for row in research.get("documents", [])
            if row.get("status") == "EXTRACTED" and row.get("text_sha256")
        }
        integrity_checked_documents = []
        if isinstance(original_documents, list):
            for document in original_documents:
                text = getattr(document, "text", None)
                if not isinstance(text, str) or not text.strip():
                    continue
                identity = (
                    str(getattr(document, "file_id", "") or "").casefold(),
                    hashlib.sha256(text.encode("utf-8")).hexdigest(),
                )
                if identity in accepted:
                    integrity_checked_documents.append(document)
        clause_reviews = audit_model_contract_clause_references(
            risks if isinstance(risks, list) else [],
            integrity_checked_documents,
        )
        metadata["source_research_clause_review"] = clause_reviews
        modality_audit = audit_source_modalities(
            integrity_checked_documents,
            requirements=requirements if isinstance(requirements, dict) else {},
            risks=risks if isinstance(risks, list) else [],
        )
        metadata["source_research_modality_audit"] = modality_audit
        typed_eis_audit = audit_model_eis_summary(
            research,
            requirements if isinstance(requirements, dict) else {},
        )
        metadata["source_research_typed_eis_audit"] = typed_eis_audit

        # Check concrete SHA/Unicode span of source research hits against
        # integrity-admitted original texts; no inferred PDF pages or cells.
        quote_proofs = []
        for theme in research.get("findings", []):
            for hit in theme.get("hits", [])[:1]:
                proof = bind_source_span(
                    integrity_checked_documents,
                    research,
                    file_id=str(hit["file_id"]),
                    start=hit["start"],
                    end=hit["end"],
                    quote=str(hit["quote"]),
                    expected_text_sha256=str(hit["source_sha256"]),
                )
                quote_proofs.append({
                    "theme": theme["key"],
                    "file_id": proof["file_id"],
                    "source_ref": proof.get("source_ref"),
                    "source_sha256": proof["source_sha256"],
                    "quote_sha256": proof.get("quote_sha256"),
                    "status": proof["status"],
                    "physical_locator_status": proof["physical_locator_status"],
                    "semantic_verification": "NOT_PERFORMED",
                })
        metadata["source_research_quote_proofs"] = quote_proofs
        invalid_proofs = sum(
            proof["status"] != "EXACT_NORMALIZED_SOURCE_TEXT"
            for proof in quote_proofs
        )
        unresolved = [
            item for item in clause_reviews
            if item["status"] != "CLAUSE_LOCATED_NOT_SEMANTICALLY_VERIFIED"
        ]
        # Source-first gate is independent of the model output schema. It
        # explicitly counts known gaps and NEVER returns a bid-ready verdict.
        quality_gate = {
            "status": (
                "CORPUS_INCOMPLETE" if research["unread_file_ids"]
                else "CONTRADICTION_REVIEW_REQUIRED"
                if (
                    modality_audit["contradiction_count"]
                    or typed_eis_audit["contradictions_count"]
                )
                else "EVIDENCE_INTEGRITY_REVIEW"
                if invalid_proofs
                else "SEMANTIC_REVIEW_REQUIRED"
            ),
            "documents_indexed": research["extracted_document_count"],
            "documents_total": research["document_count"],
            "missing_topics": list(research["missing_research_topics"]),
            "unlocated_claims": sum(
                item["status"] == "NO_MATCH_IN_INDEXED_SNIPPETS"
                for item in claim_index
            ),
            "ambiguous_or_missing_clause_refs": len(unresolved),
            "source_modality_contradictions": modality_audit["contradiction_count"],
            "historical_eis_value_contradictions": typed_eis_audit["contradictions_count"],
            "missing_eis_fields_in_llm_summary": typed_eis_audit["unmentioned_archived_eis_fields"],
            "source_quote_proof_failures": invalid_proofs,
            "claim_semantics_verified": False,
            "official_revision_current_attested": False,
            "bid_ready": False,
            "manual_review_required": True,
        }
        metadata["source_research_quality_gate"] = quality_gate
        if typed_eis_audit["contradictions_count"]:
            limitations = metadata.setdefault("limitations", [])
            if isinstance(limitations, list):
                _once(
                    limitations,
                    "Сумма НМЦК или срок подачи в ответе LLM противоречат "
                    "историческому оригиналу XML ЕИС. Нужна сверка актуальной "
                    "официальной редакции; допуск заблокирован.",
                )
        if invalid_proofs:
            limitations = metadata.setdefault("limitations", [])
            if isinstance(limitations, list):
                _once(
                    limitations,
                    "Некоторые найденные фрагменты не выдержали проверку "
                    "точного диапазона/хеша нормализованного оригинала.",
                )
        if modality_audit["contradiction_count"]:
            limitations = metadata.setdefault("limitations", [])
            if isinstance(limitations, list):
                _once(
                    limitations,
                    "Обнаружено противоречие выводов LLM обязательным "
                    "формулировкам первоисточников. Проверить ограничения "
                    "допуска и изменение условий договора по точным цитатам; "
                    "форматная валидация модели не отменяет блокировку.",
                )
        if unresolved:
            limitations = metadata.setdefault("limitations", [])
            if isinstance(limitations, list):
                _once(
                    limitations,
                    "У модели есть риски без однозначной ссылки на исходный "
                    "пункт договора; требуется ручная проверка ссылок, "
                    "содержания и редакций.",
                )
        # Never interpret a located paragraph as semantic approval. If a
        # numbered source clause is missing or repeated, keep it review-only.
        # Persist reviewable source locations separately from model assertions.
        # Existing outputs and public shape are preserved by adding optional
        # research keys in the existing trace and requirement payloads.
        trace = outputs.get("trace")
        if isinstance(trace, dict):
            trace["full_corpus_research"] = research
            trace["source_claim_assessment"] = claim_index
            trace["source_clause_review"] = clause_reviews
            trace["source_modality_audit"] = modality_audit
            trace["source_research_quality_gate"] = quality_gate
            trace["source_eis_typed_claims"] = typed_eis_audit
            trace["source_quote_proofs"] = quote_proofs
        requirement_payload = outputs.get("requirements")
        if isinstance(requirement_payload, dict):
            requirement_payload["full_corpus_research"] = research
            requirement_payload["source_claim_assessment"] = claim_index
            requirement_payload["source_clause_review"] = clause_reviews
            requirement_payload["source_modality_audit"] = modality_audit
            requirement_payload["source_research_quality_gate"] = quality_gate
            requirement_payload["source_eis_typed_claims"] = typed_eis_audit
            requirement_payload["source_quote_proofs"] = quote_proofs
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
