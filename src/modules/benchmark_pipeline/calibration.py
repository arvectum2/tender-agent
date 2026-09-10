from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime
from typing import Any

from .contract import (
    CONTRACT_VERSION,
    BenchmarkContractError,
    canonical_sha256,
    validate_artifact,
    validate_case_manifest_consistency,
)


DISCOVERY_CONTEXT_KEY = "benchmark_discovery_context"
DISCOVERY_CONTEXT_HASH_REF = "discovery_context_sha256"
NORMALIZATION_AUDIT_VERSION = "1"

_DISCOVERY_PURPOSES = {"SUPPLIER_RELEVANCE"}
_SELECTION_MODES = {"EXACT_REGISTRY_NUMBER", "SEARCH_RESULT"}
_FINAL_RECOMMENDATION_FIELDS = {
    "economics",
    "key_requirements",
    "label",
    "manual_checks",
    "open_questions",
    "rationale",
    "recommendation",
    "risks",
    "trace",
}
_PRESERVED_LIST_FIELDS = {
    "economics": "MATERIAL",
    "key_requirements": "MATERIAL",
    "risks": "MATERIAL",
    "rationale": "NON_MATERIAL",
}
_IGNORED_RECOMMENDATION_FIELDS = {
    "label": "workflow_decision_not_document_fact",
    "manual_checks": "operator_instruction_not_document_fact",
    "open_questions": "interrogative_not_asserted_fact",
    "recommendation": "workflow_decision_not_document_fact",
    "trace": "runtime_trace_not_document_fact",
}


def build_discovery_context(
    *,
    supplier_profile: dict[str, Any],
    registry_number: str,
    source: str,
    law: str,
    as_of: str,
    query: str | None = None,
    purpose: str = "SUPPLIER_RELEVANCE",
    selection_mode: str = "EXACT_REGISTRY_NUMBER",
) -> dict[str, Any]:
    """Build immutable discovery semantics for a blind benchmark case.

    The context intentionally carries the complete sanitized supplier-profile
    snapshot, not only its id. That keeps relevance judgments reproducible even
    when the configured profile changes later.
    """

    if purpose not in _DISCOVERY_PURPOSES:
        raise BenchmarkContractError(f"unsupported discovery purpose: {purpose}")
    if selection_mode not in _SELECTION_MODES:
        raise BenchmarkContractError(f"unsupported candidate selection mode: {selection_mode}")
    if not isinstance(supplier_profile, dict) or not supplier_profile:
        raise BenchmarkContractError("discovery supplier profile must be a non-empty object")
    if not str(registry_number).strip():
        raise BenchmarkContractError("discovery registry number is required")
    if not str(source).strip() or not str(law).strip():
        raise BenchmarkContractError("discovery source and law are required")
    _require_timezone(as_of, "discovery as_of")

    profile_snapshot = deepcopy(supplier_profile)
    return {
        "version": 1,
        "purpose": purpose,
        "query": query,
        "candidate": {
            "selection_mode": selection_mode,
            "registry_number": str(registry_number).strip(),
        },
        "supplier_profile": profile_snapshot,
        "supplier_profile_sha256": canonical_sha256(profile_snapshot),
        "source": str(source).strip(),
        "law": str(law).strip(),
        "as_of": as_of,
    }


def validate_discovery_context(context: dict[str, Any]) -> None:
    if not isinstance(context, dict):
        raise BenchmarkContractError("benchmark discovery context must be an object")
    if context.get("version") != 1:
        raise BenchmarkContractError("benchmark discovery context version must be 1")
    if context.get("purpose") not in _DISCOVERY_PURPOSES:
        raise BenchmarkContractError("benchmark discovery context has unsupported purpose")
    candidate = context.get("candidate")
    if not isinstance(candidate, dict):
        raise BenchmarkContractError("benchmark discovery context candidate must be an object")
    if candidate.get("selection_mode") not in _SELECTION_MODES:
        raise BenchmarkContractError("benchmark discovery context has unsupported selection mode")
    if not str(candidate.get("registry_number") or "").strip():
        raise BenchmarkContractError("benchmark discovery context registry number is required")
    profile = context.get("supplier_profile")
    if not isinstance(profile, dict) or not profile:
        raise BenchmarkContractError("benchmark discovery context supplier profile is required")
    if context.get("supplier_profile_sha256") != canonical_sha256(profile):
        raise BenchmarkContractError("benchmark discovery supplier-profile digest is inconsistent")
    if not str(context.get("source") or "").strip() or not str(context.get("law") or "").strip():
        raise BenchmarkContractError("benchmark discovery context source and law are required")
    _require_timezone(str(context.get("as_of") or ""), "discovery as_of")


def bind_discovery_context(
    manifest: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """Return a validated manifest with discovery semantics frozen into procurement metadata."""

    validate_case_manifest_consistency(manifest)
    validate_discovery_context(context)
    bound = deepcopy(manifest)
    procurement = deepcopy(bound.get("procurement") or {})
    existing = procurement.get(DISCOVERY_CONTEXT_KEY)
    if existing is not None and canonical_sha256(existing) != canonical_sha256(context):
        raise BenchmarkContractError("case manifest already contains a different discovery context")
    procurement[DISCOVERY_CONTEXT_KEY] = deepcopy(context)
    bound["procurement"] = procurement
    validate_case_manifest_consistency(bound)
    return bound


def discovery_context_sha256(container: dict[str, Any]) -> str | None:
    procurement = container.get("procurement")
    if not isinstance(procurement, dict):
        return None
    context = procurement.get(DISCOVERY_CONTEXT_KEY)
    if context is None:
        return None
    validate_discovery_context(context)
    return canonical_sha256(context)


def discovery_context_is_bound(
    evaluator_bundle: dict[str, Any],
    sut_ref: dict[str, Any],
) -> bool:
    """Whether the SUT explicitly claims the exact frozen discovery context."""

    expected = discovery_context_sha256(evaluator_bundle)
    if expected is None:
        return False
    actual = (sut_ref.get("artifact_refs") or {}).get(DISCOVERY_CONTEXT_HASH_REF)
    return actual == expected


def verify_discovery_context_binding(
    evaluator_bundle: dict[str, Any],
    sut_ref: dict[str, Any],
) -> str:
    expected = discovery_context_sha256(evaluator_bundle)
    if expected is None:
        raise BenchmarkContractError("evaluator bundle has no benchmark discovery context")
    actual = (sut_ref.get("artifact_refs") or {}).get(DISCOVERY_CONTEXT_HASH_REF)
    if actual is None:
        raise BenchmarkContractError("Tender Agent output is not bound to discovery context")
    if actual != expected:
        raise BenchmarkContractError("Tender Agent output used a different discovery context")
    return expected


def infer_runtime_produced_at(runtime_response: dict[str, Any]) -> str:
    """Use the actual analysis completion event rather than response retrieval time."""

    preferred = ("analysis_completed", "llm_analysis_completed")
    events = [item for item in runtime_response.get("events") or [] if isinstance(item, dict)]
    for event_type in preferred:
        matches = [item for item in events if item.get("event_type") == event_type]
        if not matches:
            continue
        raw = str(matches[-1].get("timestamp") or matches[-1].get("created_at") or "").strip()
        if raw:
            _require_timezone(raw, "runtime produced_at")
            return raw
    raise BenchmarkContractError(
        "runtime response has no analysis completion timestamp; pass an explicit produced_at instead"
    )


def normalize_runtime_response(
    *,
    runtime_response: dict[str, Any],
    case_id: str,
    source_bundle_sha256: str,
    discovery_label: str = "UNCLEAR",
    ranking_delta: float | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Deterministically project the decision-bearing runtime response.

    Known canonical fields are mapped directly. Material recommendation claims
    that do not have a canonical benchmark field are preserved as explicit
    `runtime_claim.*` facts instead of disappearing from comparison. Questions,
    operator instructions and workflow decisions are recorded in the audit as
    intentionally ignored non-assertions.
    """

    if discovery_label not in {"RELEVANT", "PARTIALLY_RELEVANT", "IRRELEVANT", "UNCLEAR"}:
        raise BenchmarkContractError(f"invalid normalized discovery label: {discovery_label}")

    facts: list[dict[str, Any]] = []
    audit_entries: list[dict[str, Any]] = []
    used_fields: set[str] = set()

    def add_fact(field: str, value: Any, *, materiality: str, source_path: str, action: str) -> None:
        if field in used_fields:
            raise BenchmarkContractError(f"runtime normalization produced duplicate fact field: {field}")
        used_fields.add(field)
        facts.append(
            {
                "field": field,
                "value": value,
                "status": "ASSERTED",
                "materiality": materiality,
            }
        )
        audit_entries.append(
            {
                "source_path": source_path,
                "action": action,
                "normalized_field": field,
            }
        )

    title = runtime_response.get("tender_title")
    if isinstance(title, str) and title.strip():
        add_fact(
            "procurement_subject",
            title.strip(),
            materiality="MATERIAL",
            source_path="tender_title",
            action="MAPPED",
        )

    customer = runtime_response.get("customer_name")
    if isinstance(customer, str) and customer.strip():
        add_fact(
            "customer_name",
            customer.strip(),
            materiality="MATERIAL",
            source_path="customer_name",
            action="MAPPED",
        )

    runtime_analysis = runtime_response.get("runtime_analysis")
    analysis_context = runtime_analysis.get("analysis_context") if isinstance(runtime_analysis, dict) else None
    if isinstance(analysis_context, dict):
        payment_terms = analysis_context.get("payment_terms")
        if (
            isinstance(payment_terms, dict)
            and isinstance(payment_terms.get("payment"), str)
            and payment_terms["payment"].strip()
            and isinstance(payment_terms.get("deadline"), str)
            and payment_terms["deadline"].strip()
        ):
            add_fact(
                "payment_terms",
                payment_terms,
                materiality="MATERIAL",
                source_path="runtime_analysis.analysis_context.payment_terms",
                action="MAPPED",
            )

        advance_payment = analysis_context.get("advance_payment")
        if isinstance(advance_payment, bool):
            add_fact(
                "advance_payment",
                advance_payment,
                materiality="MATERIAL",
                source_path="runtime_analysis.analysis_context.advance_payment",
                action="MAPPED",
            )

        performance_security_percent = analysis_context.get("performance_security_percent")
        if isinstance(performance_security_percent, (int, float)) and not isinstance(
            performance_security_percent, bool
        ):
            add_fact(
                "performance_security_percent",
                performance_security_percent,
                materiality="MATERIAL",
                source_path="runtime_analysis.analysis_context.performance_security_percent",
                action="MAPPED",
            )

        acceptance_terms = analysis_context.get("acceptance_terms")
        if (
            isinstance(acceptance_terms, dict)
            and isinstance(acceptance_terms.get("executor_submission"), str)
            and acceptance_terms["executor_submission"].strip()
            and isinstance(acceptance_terms.get("customer_acceptance"), str)
            and acceptance_terms["customer_acceptance"].strip()
        ):
            add_fact(
                "acceptance_terms",
                acceptance_terms,
                materiality="MATERIAL",
                source_path="runtime_analysis.analysis_context.acceptance_terms",
                action="MAPPED",
            )

    recommendation = runtime_response.get("final_recommendation")
    if recommendation is None:
        recommendation = {}
    if not isinstance(recommendation, dict):
        raise BenchmarkContractError("final_recommendation must be an object for benchmark normalization")
    unknown_keys = sorted(set(recommendation) - _FINAL_RECOMMENDATION_FIELDS)
    if unknown_keys:
        raise BenchmarkContractError(
            "unclassified final_recommendation fields: " + ", ".join(unknown_keys)
        )

    for key in sorted(_PRESERVED_LIST_FIELDS):
        raw_items = recommendation.get(key) or []
        if not isinstance(raw_items, list):
            raise BenchmarkContractError(f"final_recommendation.{key} must be a list")
        for index, item in enumerate(raw_items):
            if not isinstance(item, str) or not item.strip():
                continue
            source_path = f"final_recommendation.{key}[{index}]"
            if key == "economics":
                nmck = _parse_nmck(item)
                if nmck is not None and "initial_max_price_rub" not in used_fields:
                    add_fact(
                        "initial_max_price_rub",
                        nmck,
                        materiality="MATERIAL",
                        source_path=source_path,
                        action="MAPPED",
                    )
                    continue
            add_fact(
                _runtime_claim_field(key, index),
                item.strip(),
                materiality=_PRESERVED_LIST_FIELDS[key],
                source_path=source_path,
                action="PRESERVED_EXTRA",
            )

    for key, reason in sorted(_IGNORED_RECOMMENDATION_FIELDS.items()):
        if key not in recommendation:
            continue
        value = recommendation.get(key)
        if isinstance(value, list):
            for index, item in enumerate(value):
                if item in (None, ""):
                    continue
                audit_entries.append(
                    {
                        "source_path": f"final_recommendation.{key}[{index}]",
                        "action": "IGNORED_NON_ASSERTION",
                        "reason": reason,
                    }
                )
        elif value not in (None, ""):
            audit_entries.append(
                {
                    "source_path": f"final_recommendation.{key}",
                    "action": "IGNORED_NON_ASSERTION",
                    "reason": reason,
                }
            )

    normalized = {
        "schema_version": CONTRACT_VERSION,
        "case_id": case_id,
        "source_bundle_sha256": source_bundle_sha256,
        "discovery": {
            "label": discovery_label,
            "ranking_delta": ranking_delta,
        },
        "facts": facts,
    }
    validate_artifact("normalized_sut_output", normalized)

    counts = {
        "mapped": sum(item["action"] == "MAPPED" for item in audit_entries),
        "preserved_extra": sum(item["action"] == "PRESERVED_EXTRA" for item in audit_entries),
        "ignored_non_assertion": sum(
            item["action"] == "IGNORED_NON_ASSERTION" for item in audit_entries
        ),
    }
    audit = {
        "version": NORMALIZATION_AUDIT_VERSION,
        "case_id": case_id,
        "source_bundle_sha256": source_bundle_sha256,
        "runtime_run_id": runtime_response.get("run_id"),
        "entries": audit_entries,
        "counts": counts,
        "normalized_output_sha256": canonical_sha256(normalized),
    }
    return normalized, audit


def build_sut_ref(
    *,
    normalized_output: dict[str, Any],
    freeze_receipt: dict[str, Any],
    runtime_version: str,
    runtime_response_ref: str,
    produced_at: str,
    normalization_audit_ref: str,
    normalization_audit_sha256: str,
    discovery_context_sha256_at_generation: str | None = None,
    extra_artifact_refs: dict[str, str] | None = None,
) -> dict[str, Any]:
    validate_artifact("normalized_sut_output", normalized_output)
    validate_artifact("frozen_label", freeze_receipt)
    _require_timezone(produced_at, "Tender Agent produced_at")
    refs = {
        "runtime_response": runtime_response_ref,
        "normalization_audit": normalization_audit_ref,
        "normalization_audit_sha256": normalization_audit_sha256,
    }
    if discovery_context_sha256_at_generation is not None:
        refs[DISCOVERY_CONTEXT_HASH_REF] = discovery_context_sha256_at_generation
    for key, value in (extra_artifact_refs or {}).items():
        if key in refs and refs[key] != value:
            raise BenchmarkContractError(f"conflicting SUT artifact ref: {key}")
        refs[key] = value
    artifact = {
        "schema_version": CONTRACT_VERSION,
        "case_id": normalized_output["case_id"],
        "runtime_version": runtime_version,
        "artifact_refs": refs,
        "produced_at": produced_at,
        "source_bundle_sha256": normalized_output["source_bundle_sha256"],
        "label_set_sha256_at_generation": freeze_receipt["label_set_sha256"],
        "normalized_output_sha256": canonical_sha256(normalized_output),
    }
    validate_artifact("tender_agent_output_ref", artifact)
    return artifact


def _runtime_claim_field(section: str, index: int) -> str:
    return f"runtime_claim.final_recommendation.{section}.{index}"


def _parse_nmck(value: str) -> float | None:
    match = re.match(r"^\s*НМЦК\s*:\s*([0-9\s\u00a0]+(?:[,.][0-9]{1,2})?)", value, flags=re.IGNORECASE)
    if not match:
        return None
    normalized = match.group(1).replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def _require_timezone(value: str, label: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BenchmarkContractError(f"{label} must be an ISO date-time") from exc
    if parsed.tzinfo is None:
        raise BenchmarkContractError(f"{label} must include a timezone")
