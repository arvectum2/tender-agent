"""Source-modality contradiction checks independent of JSON/LLM validation.

This deliberately implements only high-precision *negative* checks. Missing
contradictions are NOT positive semantic verification. Original evidence always
includes byte-identical normalized-text spans and SHA receipts.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from src.modules.tender_operator_agent_demo.full_corpus_clause_review import (
    index_original_numbered_clauses,
)

_EXCLUSIVE_PARTICIPANTS = re.compile(
    r"(?:участник(?:ами|ов|и)?\s+закуп\w*[^.\n]{0,130}?)?"
    r"(?:могут\s+быть\s+только|допускаются\s+только|"
    r"участвова\w*\s+могут\s+только)[^.\n]{0,170}",
    re.I,
)
_SMALL_BUSINESS = re.compile(
    r"(?:субъект\w*\s+малого\s+предпринимательств\w*|"
    r"\bСМП\b|\bСОНКО\b|социально\s+ориентирован\w*)",
    re.I,
)
_MODEL_PREFERENCE = re.compile(r"\b(?:preferen\w*|preferred|предпочтен\w*|преимуществ\w*)\b", re.I)
_MODEL_EXCLUSIVE = re.compile(
    r"\b(?:only|exclusively|limited\s+to|exclusiv\w*|"
    r"только|исключительно|лишь|ограничен\w*)\b", re.I,
)
_MODEL_SMALL_BIZ = re.compile(
    r"(?:\bSME\b|\bSMP\b|\bSONKO\b|\bСМП\b|\bСОНКО\b|"
    r"small\s+(?:business|enterpris\w*)|социально\s+ориентир\w*|малого\s+предпринимательств\w*)",
    re.I,
)
_SOURCE_ADJUSTMENT = re.compile(
    r"(?:по\s+соглашению\s+сторон|соглашени\w*\s+сторон)"
    r".{0,300}?(?:увеличени\w*|уменьшени\w*|изменени\w*)"
    r".{0,200}?(?:объем\w*|объ[её]м\w*)",
    re.I | re.S,
)
_SOURCE_PRICE = re.compile(r"цен[ауыео]\s+контракт\w*|цен[ауыео]\s+договора", re.I)
_MODEL_FIXED = re.compile(
    r"(?:fixed\s+price|price\s+is\s+fixed|cannot\s+(?:be\s+)?chang\w*|"
    r"цен[аыуе]\s+фиксирован\w*|цен[аыуе]\s+не\s+мож\w*\s+измен\w*)", re.I,
)
_MODEL_NO_SCOPE_CHANGE = re.compile(
    r"(?:without\s+chang\w*\s+(?:the\s+)?(?:volume|scope)|"
    r"без\s+изменени\w*\s+(?:объем\w*|объ[её]м\w*))", re.I,
)
_MODEL_PRICE_CONTEXT = re.compile(r"(?:price|contract|scope|цен\w*|контракт\w*|объем\w*|объ[её]м\w*)", re.I)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _source_hit(doc: Any, start: int, end: int, *, status: str) -> dict[str, Any]:
    body = str(getattr(doc, "text", "") or "")
    excerpt = body[start:end]
    file_id = str(getattr(doc, "file_id", "") or "")
    return {
        "file_id": file_id,
        "document": str(getattr(doc, "display_name", "") or file_id),
        "source_sha256": _sha(body),
        "start": start, "end": end,
        "source_ref": f"normalized:{file_id}:{start}-{end}",
        "quote": excerpt, "quote_sha256": _sha(excerpt),
        "source_modality": status,
    }


def audit_source_modalities(
    documents: list[Any],
    *,
    requirements: dict[str, Any] | None = None,
    risks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Detect some source/model contradictions; never claim positive entailment."""
    qualifications = (requirements or {}).get("qualification_requirements") or []
    qualifications = [q for q in qualifications if isinstance(q, str)]
    risks = risks or []
    exclusivity_hits: list[dict[str, Any]] = []
    for doc in documents:
        text = getattr(doc, "text", None)
        if not isinstance(text, str) or not text:
            continue
        if str(getattr(doc, "role", "") or "") not in {
            "notice", "contract_draft", "supporting", "technical_spec",
        }:
            continue
        for match in _EXCLUSIVE_PARTICIPANTS.finditer(text):
            quote = match.group()
            if _SMALL_BUSINESS.search(quote):
                exclusivity_hits.append(
                    _source_hit(doc, match.start(), match.end(), status="ONLY_RESTRICTED_PARTICIPANTS")
                )
                if len(exclusivity_hits) >= 12:
                    break

    findings: list[dict[str, Any]] = []
    for idx, text in enumerate(qualifications):
        if not (_MODEL_SMALL_BIZ.search(text) and exclusivity_hits):
            continue
        if _MODEL_PREFERENCE.search(text) and not _MODEL_EXCLUSIVE.search(text):
            status = "CONTRADICTED_BY_EXCLUSIVE_SOURCE"
        elif not _MODEL_EXCLUSIVE.search(text):
            status = "EXCLUSIVITY_OMITTED_REVIEW"
        else:
            status = "SOURCE_MODALITY_PRESENT_SEMANTICS_UNVERIFIED"
        findings.append({
            "type": "participant_exclusivity",
            "claim_index": idx, "claim": text[:500], "status": status,
            "source_evidence": exclusivity_hits[:4],
            "semantic_verification": "NOT_PERFORMED",
            "requires_human_review": True,
        })

    clauses = index_original_numbered_clauses(documents)
    by_clause: dict[str, list[dict[str, Any]]] = {}
    for clause in clauses:
        by_clause.setdefault(clause["clause"], []).append(clause)

    from src.modules.tender_operator_agent_demo.full_corpus_clause_review import (
        audit_model_contract_clause_references,
    )

    clause_reviews = audit_model_contract_clause_references(risks, documents)
    for review in clause_reviews:
        idx = review["risk_index"]
        risk = risks[idx]
        if not isinstance(risk, dict):
            continue
        cited = by_clause.get(str(review["model_clause_reference"]), [])
        if len(cited) != 1:
            continue
        clause = cited[0]
        source_text = clause["quote"]
        if not (_SOURCE_ADJUSTMENT.search(source_text) and _SOURCE_PRICE.search(source_text)):
            continue
        desc = " ".join(str(risk.get(k) or "") for k in ("description", "impact"))
        if _MODEL_FIXED.search(desc) and _MODEL_PRICE_CONTEXT.search(desc):
            status = "CONTRADICTED_BY_PRICE_ADJUSTMENT_CLAUSE"
        elif _MODEL_NO_SCOPE_CHANGE.search(desc):
            status = "CONTRADICTED_BY_SCOPE_ADJUSTMENT_CLAUSE"
        else:
            status = "SOURCE_PRICE_CHANGE_PRESENT_SEMANTICS_UNVERIFIED"
        findings.append({
            "type": "contract_price_adjustability",
            "claim_index": idx, "claim": desc[:600], "status": status,
            "source_evidence": [clause],
            "semantic_verification": "NOT_PERFORMED",
            "requires_human_review": True,
        })

    blockers = [
        finding for finding in findings
        if finding["status"].startswith("CONTRADICTED_BY_")
    ]
    return {
        "version": 1,
        "status": "SOURCE_CONTRADICTIONS_REVIEW_REQUIRED" if blockers else "NO_DETECTED_CONTRADICTIONS_NOT_VERIFIED",
        "contradiction_count": len(blockers),
        "findings": findings,
        "semantic_verification": "NOT_PERFORMED",
        "human_review_required": True,
        "bid_ready": False,
    }
