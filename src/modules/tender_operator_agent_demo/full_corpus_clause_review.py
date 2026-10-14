"""Clause-number evidence binding for contract-risk drafts.

Locating the *real source clause* is not legal/semantic verification. Multiple
copies of a clause number, unknown revisions or ambiguous matches are review
gates, never silently resolved in favor of the model.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

_SECTION = re.compile(
    r"(?<![\w.])(?P<number>\d{1,2}(?:\.\d{1,2}){1,5})\.\s+"
    r"(?=[A-Za-zА-Яа-яЁё])",
)
_MODEL_SECTION = re.compile(
    r"(?<![\d.])(?P<number>\d{1,2}(?:\.\d{1,2}){1,5})(?![\d.])",
)
_REVIEW_STATUSES = {
    "CLAUSE_LOCATED_NOT_SEMANTICALLY_VERIFIED",
    "AMBIGUOUS_CLAUSE_REFERENCE",
    "CLAUSE_NOT_FOUND",
    "NO_NUMBERED_CLAUSE_REFERENCE",
}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def index_original_numbered_clauses(documents: list[Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for doc in documents:
        role = str(getattr(doc, "role", "") or "")
        if role not in {"contract_draft", "technical_spec"}:
            continue
        text = getattr(doc, "text", None)
        if not isinstance(text, str) or not text.strip():
            continue
        source_sha = _hash(text)
        file_id = str(getattr(doc, "file_id", "") or "")
        matches = list(_SECTION.finditer(text))
        for i, found in enumerate(matches):
            start = found.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            if end <= start:
                continue
            excerpt = text[start:min(end, start + 1550)]
            entries.append({
                "clause": found.group("number"),
                "file_id": file_id, "role": role,
                "document": str(getattr(doc, "display_name", "") or file_id),
                "source_sha256": source_sha,
                "start": start, "end": end,
                "source_ref": f"normalized:{file_id}:{start}-{end}",
                "quote": excerpt, "quote_sha256": _hash(excerpt),
                "quote_truncated": len(excerpt) < end - start,
                "status": "SOURCE_CLAUSE_NOT_SEMANTICALLY_VERIFIED",
            })
    return entries


def audit_model_contract_clause_references(
    risks: list[dict[str, Any]], documents: list[Any],
) -> list[dict[str, Any]]:
    clauses = index_original_numbered_clauses(documents)
    results: list[dict[str, Any]] = []
    for index, risk in enumerate(risks):
        if not isinstance(risk, dict):
            continue
        label = str(risk.get("clause") or "")
        identified = _MODEL_SECTION.search(label)
        reference = identified.group("number") if identified else None
        hits = [entry for entry in clauses if entry["clause"] == reference] if reference else []
        if not reference:
            status = "NO_NUMBERED_CLAUSE_REFERENCE"
        elif not hits:
            status = "CLAUSE_NOT_FOUND"
        elif len(hits) > 1:
            status = "AMBIGUOUS_CLAUSE_REFERENCE"
        else:
            status = "CLAUSE_LOCATED_NOT_SEMANTICALLY_VERIFIED"
        results.append({
            "risk_index": index,
            "model_clause_reference": reference,
            "status": status,
            "evidence": hits[:6],
            "requires_human_review": True,
            "semantic_verification": "NOT_PERFORMED",
        })
        assert status in _REVIEW_STATUSES
    return results
