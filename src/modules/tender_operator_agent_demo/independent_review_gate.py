"""Fail-closed first-pass evidence gate for locally generated procurement claims.

Literal source verification is NOT independent semantic/legal review.
This module deliberately cannot produce GO or owner approval; those gates are
external and require independent review of the complete, current case.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .source_quote_binding import bind_literal_source_quote


def assess_claims_for_independent_review(
    *,
    procurement_id: str,
    notice_purchase_number: str | None,
    claims: list[dict[str, Any]],
    sources_by_file: Mapping[str, dict[str, Any]],
    chunks: list[dict[str, Any]],
    chunk_text_by_id: Mapping[str, str],
) -> dict[str, Any]:
    """Return machine-verifiable evidence only, with human/business gates locked."""
    identity_ok = (
        bool(procurement_id)
        and isinstance(notice_purchase_number, str)
        and notice_purchase_number == procurement_id
    )
    assessed: list[dict[str, Any]] = []
    for claim in claims:
        file_id = claim.get("file_id") if isinstance(claim, dict) else None
        exact_quote = claim.get("exact_quote") if isinstance(claim, dict) else None
        source = sources_by_file.get(file_id) if isinstance(file_id, str) else None
        evidence = (
            bind_literal_source_quote(
                exact_quote=exact_quote,
                file_id=file_id,
                source_record=source,
                chunks=chunks,
                chunk_text_by_id=chunk_text_by_id,
            )
            if identity_ok
            and isinstance(exact_quote, str)
            and isinstance(file_id, str)
            and isinstance(source, dict)
            else None
        )
        assessed.append(
            {
                "file_id": file_id,
                "quote_status": "LITERAL_MATCH" if evidence else "UNVERIFIED",
                "evidence": evidence,
                "semantic_review": "PENDING_INDEPENDENT_EXPERT",
                "legal_review": "UNKNOWN",
            }
        )
    verified = sum(x["quote_status"] == "LITERAL_MATCH" for x in assessed)
    return {
        "procurement_id": procurement_id,
        "source_identity": "MATCH" if identity_ok else "CONFLICT_OR_UNKNOWN",
        "claim_count": len(assessed),
        "literal_verified_count": verified,
        "claims": assessed,
        "review_status": "INDEPENDENT_REVIEW_REQUIRED",
        "business_decision": "DEFER",
        "go_eligible": False,
    }
