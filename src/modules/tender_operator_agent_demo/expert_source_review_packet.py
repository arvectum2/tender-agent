"""R4/R5 and ARV-001 review packet — evidence prefill, never human signoff.

This is a per-run index for independently assigned reviewers. Machine checks
MUST NOT be represented as human gold or product release authorization.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

_RUBRIC = {
    "official_notice_revision": ("identity", "submission"),
    "identity_subject_customer": ("identity",),
    "original_document_integrity": ("identity",),
    "quantities_units": ("scope",),
    "technical_requirements": ("scope", "functional_requirements"),
    "bidder_eligibility": ("eligibility",),
    "licenses_certifications": ("eligibility",),
    "submission_deadline": ("submission",),
    "nmck_and_price": ("price", "price_adjustment"),
    "contract_performance_security": ("performance_security",),
    "delivery_acceptance": ("delivery", "acceptance"),
    "penalties_and_liability": ("liability",),
    "payment_conditions": ("payment",),
    "intellectual_property": ("intellectual_property",),
    "warranty_service": ("warranty",),
    "official_bid_evaluation": ("bid_evaluation",),
}
_HUMAN_LABELS = {"VERIFIED", "UNKNOWN", "CONFLICT", "NOT_APPLICABLE"}


def _digest(value: Any) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_expert_source_review_packet(
    research: dict[str, Any],
    *,
    quote_proofs: list[dict[str, Any]] | None = None,
    typed_eis_claims: dict[str, Any] | None = None,
    source_modality_audit: dict[str, Any] | None = None,
    quality_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reproducible machine-only prefill matching existing R4/ARV-001 axes."""
    docs = research.get("documents") or []
    findings = {str(x.get("key")): x for x in research.get("findings") or []}
    notice_fact = research.get("structured_notice_facts") or []
    registries = {str(x.get("procurement_number") or "") for x in notice_fact if x.get("procurement_number")}
    registry = next(iter(registries)) if len(registries) == 1 else None
    receipts = [
        {
            "file_id": d.get("file_id"),
            "role": d.get("role"),
            "text_sha256": d.get("text_sha256"),
            "raw_sha256": d.get("raw_sha256"),
            "receipt_status": d.get("receipt_status", "NOT_VERIFIED"),
            "extraction_status": d.get("status"),
        }
        for d in sorted(docs, key=lambda item: str(item.get("file_id") or "").casefold())
    ]
    proofs = quote_proofs or []
    verified_refs = {
        proof.get("source_ref")
        for proof in proofs
        if proof.get("status") == "EXACT_NORMALIZED_SOURCE_TEXT"
        and proof.get("source_ref")
    }
    criteria = []
    for name, themes in _RUBRIC.items():
        matching = [findings[k] for k in themes if k in findings]
        refs = sorted({
            str(hit.get("source_ref"))
            for row in matching for hit in row.get("hits") or []
            if hit.get("source_ref")
        })[:8]
        # Source discovery is a reviewer pointer, not semantic proof of the
        # corresponding legal/economic requirement or a 4-level human label.
        attested_refs = sorted(ref for ref in refs if ref in verified_refs)
        criteria.append({
            "rubric_id": name,
            "source_topics": list(themes),
            "source_ref_candidates": refs,
            "source_proof_refs": attested_refs,
            "machine_source_status": (
                "SOURCE_NOT_INDEXED" if research.get("source_status") == "INCOMPLETE"
                else "SOURCE_REFERENCES_FOR_REVIEW" if refs
                else "NO_SOURCE_LOCATION_FOUND_NOT_PROOF_OF_ABSENCE"
            ),
            "human_label": None,
            "human_reviewer_id": None,
            "human_reviewed_at": None,
            "human_evidence_note": None,
            "needs_independent_review": True,
        })

    typed = typed_eis_claims or {}
    modality = source_modality_audit or {}
    gate = quality_gate or {}
    unresolved_reasons = []
    if research.get("source_status") == "INCOMPLETE":
        unresolved_reasons.append("ORIGINAL_DOCUMENTS_INCOMPLETE")
    if research.get("multiple_notices_require_revision_resolution"):
        unresolved_reasons.append("MULTIPLE_OFFICIAL_NOTICE_REVISIONS")
    if registry is None:
        unresolved_reasons.append("NO_UNIQUE_SOURCE_REGISTRY_NUMBER")
    if not proofs:
        unresolved_reasons.append("NO_SHA_EXACT_SOURCE_PROOF")
    if any(p.get("status") != "EXACT_NORMALIZED_SOURCE_TEXT" for p in proofs):
        unresolved_reasons.append("SOME_SOURCE_QUOTES_UNVERIFIED")
    if typed.get("contradictions_count", 0) or modality.get("contradiction_count", 0):
        unresolved_reasons.append("MODEL_SOURCE_CONTRADICTION")
    if typed.get("unmentioned_archived_eis_fields"):
        unresolved_reasons.append("MODEL_MISSED_SOURCE_FIELDS")
    # These owner/human gates stay open even if machine evidence is perfect.
    unresolved_reasons.extend([
        "CURRENT_OFFICIAL_REVISION_NOT_OWNER_ATTESTED",
        "NO_INDEPENDENT_HUMAN_GOLD_REVIEW",
        "ARV001_FREEZE_NOT_AUTHORIZED",
    ])
    case_manifest = {
        "registry_number_from_original_only": registry,
        "source_status": research.get("source_status"),
        "receipts": receipts,
    }
    return {
        "version": "r4_r5_expert_source_prefill_v1",
        "contract": "TDP_R4_R5_HUMAN_GOLD_PROTOCOL_2026-10-12+ARV-001",
        "registry_number_from_original_only": registry,
        "case_source_manifest_sha256": _digest(case_manifest),
        "source_inventory": receipts,
        "source_proof_count": len(verified_refs),
        "material_claim_contradictions": (
            int(modality.get("contradiction_count") or 0)
            + int(typed.get("contradictions_count") or 0)
        ),
        "source_quality_gate_status": gate.get("status", "NOT_EVALUATED"),
        "rubric": criteria,
        "allowed_human_labels": sorted(_HUMAN_LABELS),
        "human_reviews_completed": 0,
        "human_gold_attested": False,
        "current_official_revision_attested": False,
        "expert_signature_present": False,
        "arv001_release_gate": "NOT_READY",
        "bid_ready": False,
        "unresolved_reasons": sorted(set(unresolved_reasons)),
    }
