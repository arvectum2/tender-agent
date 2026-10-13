"""Strict independent semantic reviewer handoff for locally produced model claims.

A source quote match proves occurrence, not legal meaning. No default reviewer is
configured; this module never calls a network service or grants commercial GO.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

_MAX_CLAIMS = 60


def review_model_claims(
    *,
    procurement_id: str | None,
    notice_purchase_number: str | None,
    claims: list[dict[str, Any]],
    reviewer: Callable[[dict[str, Any]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Review source-bound claims; require a separate callable for semantic decisions.

    Each claim must have literal evidence already established by the quote gate:
    evidence_id, exact_quote, interpretation and source_identity MATCH.
    The reviewer returns one verdict per claim with exactly matching evidence_id.
    This interface intentionally does not assert credentials, expertise, or a
    particular provider. Callers must separately attest provider identity.
    """
    identity_ok = bool(procurement_id) and notice_purchase_number == procurement_id
    safe_claims = isinstance(claims, list) and len(claims) <= _MAX_CLAIMS
    base = {
        "procurement_id": procurement_id,
        "reviewer_invoked": False,
        "semantic_status": "REVIEW_REQUIRED",
        "business_decision": "DEFER",
        "go_eligible": False,
        "claims": [],
    }
    if not identity_ok or not safe_claims:
        return {**base, "reason": "SOURCE_IDENTITY_UNKNOWN_OR_CONFLICT"}

    verified_inputs: list[dict[str, str]] = []
    for item in claims:
        if not isinstance(item, dict) or item.get("source_identity") != "MATCH":
            return {**base, "reason": "UNVERIFIED_SOURCE_EVIDENCE"}
        fields = ("evidence_id", "exact_quote", "interpretation")
        if any(not isinstance(item.get(k), str) or not item[k].strip() for k in fields):
            return {**base, "reason": "MISSING_CLAIM_OR_EVIDENCE"}
        if len(item["exact_quote"]) > 800 or len(item["interpretation"]) > 4000:
            return {**base, "reason": "CLAIM_EXCEEDS_BOUNDS"}
        verified_inputs.append({k: item[k] for k in fields})

    if not verified_inputs:
        return {**base, "reason": "NO_VERIFIABLE_CLAIMS"}
    if reviewer is None:
        return {**base, "reason": "INDEPENDENT_REVIEWER_UNAVAILABLE"}

    request = {"procurement_id": procurement_id, "claims": verified_inputs}
    try:
        response = reviewer(request)
    except Exception:  # noqa: BLE001 - contain provider failures, do not disclose secrets
        return {**base, "reviewer_invoked": True, "reason": "INDEPENDENT_REVIEW_FAILED"}
    if not isinstance(response, Mapping) or not isinstance(response.get("verdicts"), list):
        return {**base, "reviewer_invoked": True, "reason": "MALFORMED_EXPERT_RESPONSE"}

    verdicts = response["verdicts"]
    if len(verdicts) != len(verified_inputs):
        return {**base, "reviewer_invoked": True, "reason": "MISSING_OR_EXTRA_VERDICTS"}
    by_id: dict[str, dict[str, str]] = {}
    for verdict in verdicts:
        if not isinstance(verdict, dict):
            return {**base, "reviewer_invoked": True, "reason": "MALFORMED_EXPERT_RESPONSE"}
        evidence_id = verdict.get("evidence_id")
        decision = verdict.get("decision")
        reason = verdict.get("reason")
        if (
            not isinstance(evidence_id, str)
            or evidence_id in by_id
            or decision not in {"SUPPORTED", "CONTRADICTED", "UNKNOWN"}
            or not isinstance(reason, str)
            or not reason.strip()
            or len(reason) > 1200
        ):
            return {**base, "reviewer_invoked": True, "reason": "INVALID_EXPERT_VERDICT"}
        by_id[evidence_id] = {"evidence_id": evidence_id, "decision": decision, "reason": reason}
    expected_ids = [x["evidence_id"] for x in verified_inputs]
    if len(set(expected_ids)) != len(expected_ids) or set(by_id) != set(expected_ids):
        return {**base, "reviewer_invoked": True, "reason": "EXPERT_EVIDENCE_ID_MISMATCH"}

    ordered = [by_id[k] for k in expected_ids]
    fully_supported = all(x["decision"] == "SUPPORTED" for x in ordered)
    return {
        **base,
        "reviewer_invoked": True,
        "semantic_status": "EXPERT_SOURCE_CLAIMS_SUPPORTED" if fully_supported else "EXPERT_REVIEW_HAS_FINDINGS",
        "reason": "SEMANTICS_NOT_LEGAL_OR_COMMERCIAL_APPROVAL",
        "claims": ordered,
    }
