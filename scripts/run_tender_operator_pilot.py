#!/usr/bin/env python3
"""
Run a tender operator pilot from a local folder (RFQ-first workflow).

The runner supports tender/operator companies who do not have fixed product
catalogs or known supplier prices.  Workflow:

    tender docs -> extract requirements -> supplier questions -> RFQ draft
    -> collect TKP (optional) -> compare TKP -> economics -> bid decision

Usage:
    .venv/bin/python scripts/run_tender_operator_pilot.py \
        --operator-id tender_operator_001 \
        --tender-dir local_pilot_runs/tender_operator_001/tender_001 \
        --provider stub \
        --output-dir local_pilot_runs/tender_operator_001/tender_001/05_system_output
"""

import argparse
import copy
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.modules.partner_export.service import (
    approve_for_delivery,
    generate_export_package,
    mark_delivered_manually,
    render_export_json,
    render_export_markdown,
)
from src.modules.partner_workspace.schemas import IntakeSourceType, RedactionStatus
from src.modules.partner_workspace.service import (
    add_intake_record,
    approve_for_pilot_use,
    create_workspace,
    generate_redaction_checklist,
    mark_redacted_for_partner,
    require_redaction,
)
from src.modules.pilot_access_boundary.schemas import VisibilityLevel
from src.modules.pilot_feedback.schemas import FeedbackSource, FeedbackType, FinalDecision, NextAction
from src.modules.pilot_feedback.service import create_feedback, create_outcome
from src.modules.quote_repository.tkp_normalization import (
    build_tkp_comparison_from_normalized_quotes,
    build_tkp_llm_inputs,
    build_tkp_normalization_report,
    normalize_tkp_quotes,
)
from src.modules.tender_operator_review.service import (
    build_human_review_checklist_markdown,
    build_human_review_pack,
    build_operator_decision_form_markdown,
    update_run_summary_with_human_review,
)
from src.shared.config.settings import get_settings


# ---------------------------------------------------------------------------
# Folder validation
# ---------------------------------------------------------------------------

def _validate_tender_dir(tender_dir: Path) -> None:
    if not tender_dir.is_dir():
        print(f"ERROR: Tender directory does not exist: {tender_dir}")
        sys.exit(1)

    extracted_dir = tender_dir / "02_extracted_text"
    if not extracted_dir.is_dir():
        print(f"ERROR: Missing '02_extracted_text/' subdirectory in {tender_dir}")
        sys.exit(1)

    required = ["notice.txt", "technical_spec.txt", "contract_draft.txt"]
    missing = [f for f in required if not (extracted_dir / f).is_file()]
    if missing:
        print(f"ERROR: Missing required extracted text files in {extracted_dir}:")
        for f in missing:
            print(f"  - {f}")
        sys.exit(1)


def _ensure_output_dirs(*dirs: Path) -> None:
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _clip_text(text: str, *, max_chars: int = 12000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated for controlled analysis]..."


SUPPORTED_PROVIDER_FLAGS = [
    "stub",
    "llm",
    "openai_compatible",
    "gigachat",
    "yandex",
    "alice",
    "cloudru",
]


def _canonical_provider_name(provider_name: str) -> str:
    normalized = provider_name.strip().lower()
    if normalized in {"openai", "openai-compatible", "openai_compatible"}:
        return "openai_compatible"
    if normalized in {"gigachat", "sber", "sber_gigachat"}:
        return "gigachat"
    if normalized in {"yandex", "yandex_ai_studio"}:
        return "yandex"
    if normalized in {"alice", "alice_ai"}:
        return "alice"
    if normalized in {"cloudru", "cloud.ru", "cloud_ru"}:
        return "cloudru"
    return normalized


def _resolve_provider_request(requested_provider: str, env_provider: str) -> tuple[str, str]:
    requested = _canonical_provider_name(requested_provider)
    if requested == "stub":
        return "stub", "stub"
    if requested == "llm":
        resolved = _canonical_provider_name(env_provider or "stub")
        return ("stub" if resolved == "stub" else "llm"), resolved
    return "llm", requested


# ---------------------------------------------------------------------------
# Operator profile
# ---------------------------------------------------------------------------

def _profile_value(text: str, label: str) -> str | None:
    match = re.search(rf"^- (?:\*\*)?{re.escape(label)}(?:\*\*)?\s*:\s*(.+?)\s*$", text, re.MULTILINE | re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _profile_number(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"[-+]?\d[\d\s,._]*", value)
    if not match:
        return None
    raw = match.group(0).replace(" ", "").replace("_", "")
    if raw.count(",") == 1 and "." not in raw and len(raw.split(",", 1)[1]) <= 2:
        raw = raw.replace(",", ".")
    else:
        raw = raw.replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _profile_section(text: str, heading: str) -> str:
    match = re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.MULTILINE | re.IGNORECASE)
    if not match:
        return ""
    rest = text[match.end():]
    next_heading = re.search(r"^##\s+", rest, re.MULTILINE)
    return rest[: next_heading.start()] if next_heading else rest


def _profile_list(section: str) -> list[str]:
    values: list[str] = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line.startswith("-") or line.startswith("- ["):
            continue
        value = line[1:].strip()
        if not value or value.endswith(":") or re.match(r"^Category\s+\d+\s*:\s*$", value, re.IGNORECASE):
            continue
        if ":" in value:
            _, candidate = value.split(":", 1)
            value = candidate.strip()
        if value:
            values.append(value)
    return values


def _read_operator_profile(operator_dir: Path) -> dict[str, Any]:
    profile_path = operator_dir / "operator_profile.md"
    if not profile_path.is_file():
        return {"found": False, "line_count": 0, "has_vat_info": False, "has_margin_info": False, "has_categories": False, "preview": "", "supplier_profile": {}}

    text = profile_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    categories = _profile_list(_profile_section(text, "Working Categories"))
    regions_raw = _profile_value(text, "Tender Regions") or _profile_value(text, "Regions")
    regions = [part.strip() for part in re.split(r"[,;]", regions_raw or "") if part.strip()]
    price_min = _profile_number(_profile_value(text, "Minimum"))
    price_max = _profile_number(_profile_value(text, "Maximum"))
    margin = _profile_number(_profile_value(text, "Target margin"))
    payment_delay = _profile_number(_profile_value(text, "Acceptable payment delay"))
    contract_security = _profile_number(_profile_value(text, "Acceptable contract security"))
    licenses = _profile_value(text, "Licenses held")
    sro = _profile_value(text, "SRO approvals held")
    experience = _profile_number(_profile_value(text, "Experience required"))
    vat_mode = None
    vat_section = _profile_section(text, "VAT Mode")
    checked = [line.lower() for line in vat_section.splitlines() if re.match(r"^\s*- \[x\]", line, re.IGNORECASE)]
    if any("both" in line for line in checked): vat_mode = "both"
    elif any("without vat" in line for line in checked): vat_mode = "without_vat"
    elif any("with vat" in line for line in checked): vat_mode = "with_vat"

    supplier_profile = {
        "criteria": {"categories": categories, "regions": regions, "price_min": price_min, "price_max": price_max},
        "commercial": {"vat_mode": vat_mode, "target_margin_percent": margin, "max_payment_delay_days": payment_delay, "max_contract_security_percent": contract_security},
        "qualification": {"licenses": licenses, "sro_approvals": sro, "experience_years": experience},
    }
    return {
        "found": True, "line_count": len(lines), "has_vat_info": vat_mode is not None,
        "has_margin_info": margin is not None, "has_categories": bool(categories),
        "preview": " ".join(lines[:5])[:200], "supplier_profile": supplier_profile,
    }


def _read_supplier_candidates_notes(tender_dir: Path) -> dict[str, Any]:
    path = tender_dir / "03_supplier_search" / "supplier_candidates.md"
    if not path.is_file():
        return {
            "found": False,
            "path": str(path),
            "line_count": 0,
            "preview": "",
        }

    text = path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return {
        "found": True,
        "path": str(path),
        "line_count": len(lines),
        "preview": " ".join(lines[:8])[:280],
    }


# ---------------------------------------------------------------------------
# TKP detection
# ---------------------------------------------------------------------------

def _detect_tkp_files(tender_dir: Path) -> list[Path]:
    tkp_dir = tender_dir / "04_tkp"
    if not tkp_dir.is_dir():
        return []
    return sorted(tkp_dir.iterdir())


# ---------------------------------------------------------------------------
# Stub analysis — RFQ-first, no product catalog
# ---------------------------------------------------------------------------

def _run_stub_requirements_extraction(
    notice_text: str,
    technical_spec_text: str,
    contract_draft_text: str,
) -> dict[str, Any]:
    return {
        "tender_title": notice_text.split("\n")[0].strip().replace("# ", "").replace("NOTICE", "").strip() if notice_text else "Unknown",
        "tender_summary": f"Tender notice: {notice_text[:150]}...",
        "technical_requirements": [
            "Compliance with specified technical standards required",
            "Equipment/goods must match stated specifications",
            "Acceptance testing per contract terms",
            "Warranty and post-delivery support required",
        ],
        "qualification_requirements": [
            "Valid business registration in relevant jurisdiction",
            "Relevant industry certifications or SRO approvals",
            "Prior experience in similar contracts (reference letters)",
            "Financial stability (audited statements if above threshold)",
        ],
        "document_requirements": [
            "Company registration certificate",
            "Tax clearance certificate",
            "Technical proposal with specifications",
            "Financial guarantee or contract security",
            "Declaration of conformity",
        ],
        "evaluation_criteria": [
            "Price (weight varies per tender)",
            "Delivery timeline",
            "Warranty period",
            "Qualification and experience",
        ],
        "procurement_categories": [
            "Equipment and machinery",
            "Technical services",
            "Installation and commissioning",
        ],
    }


def _run_stub_calibrated_contract_risk(contract_draft_text: str) -> list[dict[str, Any]]:
    return [
        {
            "clause": "Penalties for delay",
            "description": "Standard penalty at 1/300 of key rate per day of delay, capped at contract value.",
            "classification": "market_standard_harsh_term",
            "impact": "Manageable. Include in project planning.",
            "mitigation": "Ensure realistic delivery timeline. Include buffer.",
            "operator_decision_required": False,
        },
        {
            "clause": "Post-payment after acceptance",
            "description": "Payment within 30 business days after signing acceptance certificate.",
            "classification": "market_standard_harsh_term",
            "impact": "Standard for public procurement. Requires working capital.",
            "mitigation": "Factor into cash flow planning. Consider contract security reduction.",
            "operator_decision_required": False,
        },
        {
            "clause": "Unilateral termination right",
            "description": "Customer may terminate contract unilaterally if supplier delays beyond 30 days.",
            "classification": "market_standard_harsh_term",
            "impact": "Standard clause. Manageable with proper project management.",
            "mitigation": "Track milestones diligently. Communicate proactively.",
            "operator_decision_required": False,
        },
        {
            "clause": "Contract security requirement",
            "description": "Contract security at 30% of contract value, to be returned after warranty period.",
            "classification": "commercially_material_risk",
            "impact": "Binds significant working capital. Reduces available margin.",
            "mitigation": "Include cost of security (bank guarantee fee) in pricing. Negotiate reduction if possible.",
            "operator_decision_required": True,
        },
        {
            "clause": "Short delivery timeline",
            "description": "Delivery within 30 calendar days from signing. May be tight depending on supplier availability.",
            "classification": "commercially_material_risk",
            "impact": "Requires supplier with stock or short manufacturing lead time.",
            "mitigation": "Verify supplier availability before bidding. Consider partial delivery.",
            "operator_decision_required": True,
        },
        {
            "clause": "Required license/SRO/experience",
            "description": "Supplier must hold specific SRO approval and 3 years of similar contract experience.",
            "classification": "deal_breaker_candidate",
            "impact": "If operator/supplier cannot meet these, participation is impossible.",
            "mitigation": "Verify requirements early. Check if equivalents are accepted.",
            "operator_decision_required": True,
        },
    ]


def _run_stub_supplier_questions() -> list[dict[str, Any]]:
    return [
        {
            "question": "Can you supply the exact item matching the specification? If not, what analog do you propose?",
            "category": "spec_match",
        },
        {
            "question": "What is your price per unit with VAT and without VAT?",
            "category": "price",
        },
        {
            "question": "What is the delivery cost to the specified location?",
            "category": "delivery",
        },
        {
            "question": "What is the delivery time from order confirmation?",
            "category": "delivery_time",
        },
        {
            "question": "Is the item in stock or made to order? If made to order, what is the manufacturing lead time?",
            "category": "availability",
        },
        {
            "question": "Do you have the required certificates and declarations of conformity?",
            "category": "certificates",
        },
        {
            "question": "What warranty do you provide?",
            "category": "warranty",
        },
        {
            "question": "Do you offer an analog that meets the specification? If so, provide details.",
            "category": "analog",
        },
        {
            "question": "What are your payment terms? Do you require prepayment?",
            "category": "payment",
        },
        {
            "question": "How long is your offer valid?",
            "category": "validity",
        },
        {
            "question": "Is installation/assembly included? If not, what are the additional costs?",
            "category": "installation",
        },
        {
            "question": "Is packaging, delivery, and unloading included? If not, what are the additional costs?",
            "category": "logistics",
        },
    ]


def _run_stub_tkp_comparison(tkp_files: list[Path]) -> dict[str, Any]:
    suppliers: list[dict[str, Any]] = []
    for tf in tkp_files:
        label = tf.stem
        suppliers.append({
            "supplier_label": label,
            "price_per_unit": "unknown",
            "price_total": "unknown",
            "currency": "RUB",
            "price_with_vat": "unknown",
            "price_without_vat": "unknown",
            "delivery_cost": "unknown",
            "delivery_time_days": "unknown",
            "warranty_months": "unknown",
            "payment_terms": "unknown",
            "offer_validity_days": "unknown",
            "has_certificates": "unknown",
            "installation_included": "unknown",
            "source_file": str(tf),
            "status": "needs_operator_input",
        })
    return {
        "suppliers": suppliers,
        "comparison_generated_at": datetime.now(UTC).isoformat(),
        "method": "rule_based_placeholder",
        "note": "TKP values are placeholders. Operator must fill actual values from supplier offers.",
    }


def _extract_numeric_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text in {"unknown", "n/a", "none", "null"}:
        return None
    normalized = text.replace("\u00a0", "").replace(" ", "").replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", normalized)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _run_stub_economics(tkp_comparison: dict[str, Any], operator_profile: dict[str, Any]) -> dict[str, Any]:
    suppliers = tkp_comparison.get("suppliers", [])
    target_margin = None
    if operator_profile.get("found") and operator_profile.get("has_margin_info"):
        target_margin = "needs_extraction"

    price_values: list[float] = []
    for supplier in suppliers:
        for field_name in (
            "total_amount",
            "total_amount_without_vat",
            "price_total",
            "price_with_vat",
            "price_without_vat",
            "price_per_unit",
        ):
            parsed = _extract_numeric_value(supplier.get(field_name))
            if parsed is not None:
                price_values.append(parsed)
                break

    lowest_price: str | float = "unknown"
    highest_price: str | float = "unknown"
    average_price: str | float = "unknown"
    if price_values:
        lowest_price = min(price_values)
        highest_price = max(price_values)
        average_price = round(sum(price_values) / len(price_values), 2)

    economics_status = "needs_operator_review" if price_values else "insufficient_data"
    status = "preliminary" if price_values else "blocked"
    return {
        "supplier_count": len(suppliers),
        "target_margin": target_margin or "unknown",
        "lowest_price": lowest_price,
        "highest_price": highest_price,
        "average_price": average_price,
        "margin_at_lowest": "unknown",
        "margin_at_average": "unknown",
        "contract_security_cost": "unknown",
        "financing_cost": "unknown",
        "logistics_cost": "unknown",
        "total_estimated_cost": "unknown",
        "recommended_bid_price": "unknown",
        "currency": "RUB",
        "method": "rule_based_placeholder",
        "economics_status": economics_status,
        "status": status,
        "human_review_required": True,
        "note": "Economics are placeholders. Operator must fill actual values from TKP data.",
        "generated_at": datetime.now(UTC).isoformat(),
    }


def _run_stub_bid_decision(
    tkp_comparison: dict[str, Any],
    economics: dict[str, Any],
    calibrated_risks: list[dict[str, Any]],
) -> dict[str, Any]:
    deal_breakers = [r for r in calibrated_risks if r.get("classification") == "deal_breaker_candidate"]
    material_risks = [r for r in calibrated_risks if r.get("classification") == "commercially_material_risk"]

    if deal_breakers:
        recommendation = "NEEDS_REVIEW"
        rationale = f"Deal-breaker candidates found: {len(deal_breakers)}. Requires operator escalation."
    elif material_risks:
        recommendation = "GO_WITH_CONDITIONS"
        rationale = f"Commercially material risks: {len(material_risks)}. Factor into pricing and timeline."
    else:
        recommendation = "GO"
        rationale = "No deal-breaker candidates or material risks identified."

    return {
        "preliminary_recommendation": recommendation,
        "rationale": rationale,
        "deal_breaker_count": len(deal_breakers),
        "material_risk_count": len(material_risks),
        "market_standard_count": len([r for r in calibrated_risks if r.get("classification") == "market_standard_harsh_term"]),
        "suppliers_with_offers": len(tkp_comparison.get("suppliers", [])),
        "status": "preliminary",
        "human_review_required": True,
        "note": "Preliminary recommendation only. Final decision requires human review.",
    }


def _build_llm_control_payload(result: Any) -> dict[str, Any]:
    return {
        "analysis_mode": result.analysis_mode,
        "resolved_provider": result.resolved_provider,
        "overall_review_status": result.overall_review_status,
        "trace_ids": result.trace_ids,
        "sections": {
            section_name: {
                "validation_status": section.get("validation_status"),
                "review_status": section.get("review_status"),
                "trace_id": section.get("trace_id"),
                "input_redaction": section.get("input_redaction"),
            }
            for section_name, section in result.sections.items()
        },
    }


def _materialize_llm_bid_decision(
    llm_bid_decision: dict[str, Any],
    tkp_comparison: dict[str, Any] | None,
    calibrated_risks: list[dict[str, Any]],
) -> dict[str, Any]:
    deal_breakers = [r for r in calibrated_risks if r.get("classification") == "deal_breaker_candidate"]
    material_risks = [r for r in calibrated_risks if r.get("classification") == "commercially_material_risk"]
    market_standard = [r for r in calibrated_risks if r.get("classification") == "market_standard_harsh_term"]
    return {
        "preliminary_recommendation": llm_bid_decision.get("preliminary_recommendation", "NEEDS_REVIEW"),
        "rationale": llm_bid_decision.get("rationale", "Human review required."),
        "deal_breaker_count": len(deal_breakers),
        "material_risk_count": len(material_risks),
        "market_standard_count": len(market_standard),
        "suppliers_with_offers": len(tkp_comparison.get("suppliers", [])) if tkp_comparison else 0,
        "status": "preliminary",
        "human_review_required": bool(llm_bid_decision.get("human_review_required", True)),
        "next_actions": llm_bid_decision.get("next_actions", []),
        "note": "Preliminary recommendation only. Final decision requires human review.",
    }


def _try_llm_workflow_analysis(
    operator_id: str,
    operator_profile: dict[str, Any],
    notice_text: str,
    technical_spec_text: str,
    contract_draft_text: str,
    tkp_files: list[Path],
    *,
    provider_mode: str,
    resolved_provider: str,
) -> dict[str, Any] | None:
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from src.shared.db.base import Base
        from src.shared.db import models as _db_models  # noqa: F401

        settings = get_settings()
        if not settings.database_url:
            return None

        engine = create_engine(settings.database_url)
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            from src.modules.controlled_llm_prebid.service import run_controlled_tender_operator_workflow

            tkp_inputs = build_tkp_llm_inputs([tkp_file for tkp_file in tkp_files if tkp_file.is_file()])
            llm_context = {
                "deal_id": f"PP1R-{datetime.now(UTC).strftime('%Y%m%d')}",
                "operator_id": operator_id,
                "operator_profile": operator_profile,
                "documents": {
                    "notice_text": _clip_text(notice_text),
                    "technical_spec_text": _clip_text(technical_spec_text),
                    "contract_draft_text": _clip_text(contract_draft_text),
                },
                "workflow_guardrails": {
                    "manual_only": True,
                    "no_email_send": True,
                    "no_platform_submission": True,
                    "human_review_required": True,
                },
                "tkp_inputs": tkp_inputs,
            }
            result = run_controlled_tender_operator_workflow(
                session,
                provider_mode=provider_mode,
                context=llm_context,
                include_quote_normalization=bool(tkp_inputs),
                include_bid_decision=bool(tkp_inputs),
                provider_name_override=None if resolved_provider == "stub" else resolved_provider,
            )
            return {
                "analysis_mode": result.analysis_mode,
                "resolved_provider": result.resolved_provider,
                "overall_review_status": result.overall_review_status,
                "requirements": result.requirements,
                "supplier_questions": result.supplier_questions,
                "rfq_draft": result.rfq_draft,
                "contract_risks": result.contract_risks,
                "quote_normalization": result.quote_normalization,
                "bid_decision": result.bid_decision,
                "llm_control": _build_llm_control_payload(result),
            }
    except Exception as exc:
        print(f"WARNING: LLM analysis unavailable, falling back to stub: {exc}")
        return None


def _build_supplier_sourcing_summary(requirements: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from src.modules.supplier_search.service import get_supplier_sourcing_snapshot
        from src.shared.db import models as _db_models  # noqa: F401
        from src.shared.db.base import Base
        from src.shared.db.session import SessionLocal, engine

        Base.metadata.create_all(engine)
        with SessionLocal() as session:
            return get_supplier_sourcing_snapshot(session, requirements, top_n=5)
    except Exception as exc:
        print(f"WARNING: Supplier sourcing snapshot unavailable: {exc}")
        return None


# ---------------------------------------------------------------------------
# Report builders
# ---------------------------------------------------------------------------

def _build_internal_operator_analysis(
    requirements: dict[str, Any],
    calibrated_risks: list[dict[str, Any]],
    supplier_questions: list[dict[str, Any]],
    operator_profile: dict[str, Any],
    supplier_candidates_notes: dict[str, Any],
    supplier_sourcing: dict[str, Any] | None,
    normalized_quotes: list[dict[str, Any]] | None,
    tkp_comparison: dict[str, Any] | None,
    economics: dict[str, Any] | None,
    bid_decision: dict[str, Any] | None,
    records: list[dict[str, Any]],
    notice_text: str,
    technical_spec_text: str,
    contract_draft_text: str,
) -> str:
    lines: list[str] = [
        "# Internal Tender Operator Analysis",
        "",
        f"**Generated**: {datetime.now(UTC).isoformat()}",
        f"**Workflow**: RFQ-first (tender operator)",
        "",
        "---",
        "## Operator Profile",
        "",
    ]
    if operator_profile["found"]:
        lines.append(f"Profile found: {operator_profile['preview']}")
        lines.append(f"  VAT info: {'Yes' if operator_profile.get('has_vat_info') else 'No'}")
        lines.append(f"  Margin info: {'Yes' if operator_profile.get('has_margin_info') else 'No'}")
        lines.append(f"  Categories: {'Yes' if operator_profile.get('has_categories') else 'No'}")
    else:
        lines.append("No operator profile found (optional).")

    lines += [
        "",
        "---",
        "## Source Documents",
        "",
        f"- Notice: {len(notice_text)} chars",
        f"- Technical Spec: {len(technical_spec_text)} chars",
        f"- Contract Draft: {len(contract_draft_text)} chars",
        "",
        "---",
        "## Supplier Sourcing",
        "",
    ]

    if supplier_candidates_notes.get("found"):
        lines.append(
            f"- Manual candidates file: {supplier_candidates_notes['path']} ({supplier_candidates_notes['line_count']} lines)"
        )
        if supplier_candidates_notes.get("preview"):
            lines.append(f"- Manual notes preview: {supplier_candidates_notes['preview']}")
    else:
        lines.append("- Manual candidates file: not provided")

    if supplier_sourcing:
        lines.append(f"- Registry suppliers available: {supplier_sourcing.get('registry_supplier_count', 0)}")
        lines.append(f"- Vendor-list suppliers tagged: {supplier_sourcing.get('vendor_list_supplier_count', 0)}")
        top_suppliers = supplier_sourcing.get("top_suppliers", [])
        if top_suppliers:
            lines += ["", "Top ranked suppliers:"]
            for supplier in top_suppliers:
                lines.append(
                    f"- {supplier.get('display_name') or supplier.get('supplier_id')}: "
                    f"{supplier.get('inclusion_reason', 'No reason available')}"
                )
    else:
        lines.append("- Structured registry shortlist: unavailable")

    lines += [
        "",
        "---",
        "## Tender Summary",
        "",
        requirements.get("tender_summary", "No summary generated"),
        "",
    ]

    if normalized_quotes:
        lines += ["## TKP Normalization", ""]
        for quote in normalized_quotes:
            lines.append(
                f"- {quote.get('supplier_label', 'unknown')}: "
                f"status={quote.get('normalization_status', 'unknown')}; "
                f"confidence={quote.get('extraction_confidence', 'unknown')}; "
                f"total={quote.get('total_amount', 'unknown')} {quote.get('currency_code', 'RUB')}; "
                f"review={', '.join(quote.get('fields_needing_review', [])) or 'none'}"
            )
        lines += [""]

    tech_reqs = requirements.get("technical_requirements", [])
    if tech_reqs:
        lines += ["## Technical Requirements", ""]
        lines += [f"- {r}" for r in tech_reqs]
        lines += [""]

    qual_reqs = requirements.get("qualification_requirements", [])
    if qual_reqs:
        lines += ["## Qualification Requirements", ""]
        lines += [f"- {q}" for q in qual_reqs]
        lines += [""]

    doc_reqs = requirements.get("document_requirements", [])
    if doc_reqs:
        lines += ["## Document Requirements", ""]
        lines += [f"- {d}" for d in doc_reqs]
        lines += [""]

    eval_criteria = requirements.get("evaluation_criteria", [])
    if eval_criteria:
        lines += ["## Evaluation Criteria", ""]
        lines += [f"- {e}" for e in eval_criteria]
        lines += [""]

    lines += [
        "---",
        "## Calibrated Contract Risk Memo",
        "",
        "### Methodology",
        "",
        "Risks are classified into three tiers:",
        "- **Market-standard harsh term**: Not an automatic no-go.",
        "- **Commercially material risk**: Factor into pricing/timeline.",
        "- **Deal-breaker candidate**: Escalate before proceeding.",
        "",
    ]
    for risk in calibrated_risks:
        classification = risk.get("classification", "unknown")
        icon = {
            "market_standard_harsh_term": "[STANDARD]",
            "commercially_material_risk": "[MATERIAL]",
            "deal_breaker_candidate": "[DEAL-BREAKER]",
        }.get(classification, "[UNKNOWN]")
        lines.append(f"### {icon} {risk.get('clause', 'Unknown clause')}")
        lines.append(f"- **Risk**: {risk.get('description', '')}")
        lines.append(f"- **Classification**: {classification}")
        lines.append(f"- **Impact**: {risk.get('impact', '')}")
        lines.append(f"- **Mitigation**: {risk.get('mitigation', '')}")
        lines.append(f"- **Operator decision required**: {risk.get('operator_decision_required', False)}")
        lines.append("")

    lines += [
        "---",
        "## Supplier Questions for RFQ",
        "",
    ]
    for sq in supplier_questions:
        lines.append(f"- [{sq.get('category', 'general')}] {sq.get('question', '')}")
    lines += [""]

    lines += [
        "---",
        "## RFQ Status",
        "",
        "The following RFQ milestone applies:",
    ]

    has_tkp = tkp_comparison is not None and tkp_comparison.get("suppliers")
    if has_tkp:
        lines.append("- **Status**: tkp_received / economics_ready")
        lines.append(f"- **Suppliers with offers**: {len(tkp_comparison.get('suppliers', []))}")
    else:
        lines.append("- **Status**: rfq_ready / collect_tkp")
        lines.append("- **Action**: Send RFQ to suppliers and collect TKP offers.")
    lines += [""]

    if economics:
        lines += [
            "---",
            "## Economics Summary",
            "",
            f"- Supplier count: {economics.get('supplier_count', 'N/A')}",
            f"- Target margin: {economics.get('target_margin', 'unknown')}",
            f"- Lowest price: {economics.get('lowest_price', 'unknown')}",
            f"- Highest price: {economics.get('highest_price', 'unknown')}",
            f"- Total estimated cost: {economics.get('total_estimated_cost', 'unknown')}",
            f"- Recommended bid price: {economics.get('recommended_bid_price', 'unknown')}",
            f"- Method: {economics.get('method', 'N/A')}",
            "",
        ]

    lines += [
        "---",
        "## Intake Records",
        "",
    ]
    for r in records:
        lines.append(f"- {r['source_label']}: status={r['redaction_status']}, visibility={r['visibility_level']}")
    lines += [""]

    records_data = [r.get("record") for r in records if "record" in r]
    if records_data:
        lines += ["## Redaction Checklist", ""]
        checklist = generate_redaction_checklist(records_data)
        for item in checklist:
            lines.append(
                f"- {item.get('source_label', item.get('intake_record_id', '?'))}: "
                f"needs_redaction={item.get('needs_redaction', '?')}, "
                f"can_use_in_pilot={item.get('can_use_in_pilot', '?')}, "
                f"can_appear_in_report={item.get('can_appear_in_partner_report', '?')}"
            )
        lines += [""]

    return "\n".join(lines)


def _build_operator_operator_report_sections(
    requirements: dict[str, Any],
    calibrated_risks: list[dict[str, Any]],
    tkp_comparison: dict[str, Any] | None,
    bid_decision: dict[str, Any] | None,
    has_tkp: bool,
    analysis_mode: str,
) -> dict[str, str]:
    tech = "\n".join(f"- {r}" for r in requirements.get("technical_requirements", []))
    qual = "\n".join(f"- {q}" for q in requirements.get("qualification_requirements", []))
    docs = "\n".join(f"- {d}" for d in requirements.get("document_requirements", []))
    summary = requirements.get("tender_summary", "No summary available.")

    customer_report = (
        f"# Tender Operator Report\n\n"
        f"## Tender Summary\n{summary}\n\n"
        f"## Technical Requirements\n{tech}\n\n"
        f"## Qualification Requirements\n{qual}\n\n"
        f"## Required Documents\n{docs}\n"
    )

    if has_tkp and bid_decision:
        rec = bid_decision.get("preliminary_recommendation", "No recommendation")
        customer_report += (
            f"\n## Preliminary Bid Recommendation\n"
            f"{rec}\n\n"
            f"*Human review required before any bid decision.*\n"
        )

    customer_report += f"\n*Analysis mode: {analysis_mode} | RFQ-first workflow | Manual delivery only*\n"

    sections: dict[str, str] = {
        "customer_report": customer_report,
        "summary": "Tender operator pilot summary.",
        "technical_analysis": (
            "## Technical Analysis\n"
            f"### Technical Requirements\n{tech}\n"
            f"### Qualification Requirements\n{qual}\n"
        ),
        "contract_risks_overview": (
            "## Contract Risk Overview\n"
            + "\n".join(
                f"- [{r.get('classification', 'unknown')}] {r.get('clause', '')}"
                for r in calibrated_risks
            )
        ),
        "runtime_trace": (
            "DEBUG: trace_id=PP1R-internal | Internal processing metadata. "
            "Operator: system | Timestamp: internal"
        ),
        "sensitive_internal_notes": (
            "INTERNAL: This section contains privileged analysis. "
            "Not for external distribution."
        ),
        "operator_decision": (
            "Operator decision: Analysis reviewed on "
            f"{datetime.now(UTC).isoformat()}. Final human approval required before delivery."
        ),
    }
    return sections


def _write_outputs(
    output_dir: Path,
    export_dir: Path,
    *,
    operator_id: str,
    tender_dir_str: str,
    ws_id: str,
    records: list[dict[str, Any]],
    requirements: dict[str, Any],
    calibrated_risks: list[dict[str, Any]],
    supplier_questions: list[dict[str, Any]],
    tkp_comparison: dict[str, Any] | None,
    economics: dict[str, Any] | None,
    bid_decision: dict[str, Any] | None,
    normalized_quotes: list[dict[str, Any]] | None,
    tkp_normalization_report_md: str | None,
    internal_analysis_md: str,
    rfq_request_draft_md: str,
    package_id: str,
    export_md: str,
    export_json: dict[str, Any],
    delivery_status: str,
    has_tkp: bool,
    analysis_mode: str,
    requested_provider: str,
    resolved_provider: str,
    supplier_candidates_notes: dict[str, Any],
    supplier_sourcing: dict[str, Any] | None,
) -> None:
    pilot_status = "tkp_received_economics_ready" if has_tkp else "rfq_ready_collect_tkp"

    summary: dict[str, Any] = {
        "operator_id": operator_id,
        "tender_dir": tender_dir_str,
        "workspace_id": ws_id,
        "export_package_id": package_id,
        "delivery_status": delivery_status,
        "pilot_status": pilot_status,
        "analysis_mode": analysis_mode,
        "requested_provider": requested_provider,
        "resolved_provider": resolved_provider,
        "workflow": "rfq_first",
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "source_files": {
            "notice_txt": requirements.get("_notice_chars", 0),
            "technical_spec_txt": requirements.get("_spec_chars", 0),
            "contract_draft_txt": requirements.get("_contract_chars", 0),
        },
        "intake_records": [
            {
                "source_label": r["source_label"],
                "source_type": r["source_type"].value if hasattr(r["source_type"], "value") else str(r["source_type"]),
                "redaction_status": r["redaction_status"].value if hasattr(r["redaction_status"], "value") else str(r["redaction_status"]),
                "visibility_level": r["visibility_level"].value if hasattr(r["visibility_level"], "value") else str(r["visibility_level"]),
            }
            for r in records
        ],
        "tkp_found": has_tkp,
        "tkp_supplier_count": len(tkp_comparison.get("suppliers", [])) if tkp_comparison and has_tkp else 0,
        "tkp_normalized_quotes_count": len(normalized_quotes) if normalized_quotes and has_tkp else 0,
        "requirements_extracted": bool(requirements.get("technical_requirements")),
        "supplier_questions_generated": len(supplier_questions),
        "calibrated_risks": [
            {"clause": r.get("clause"), "classification": r.get("classification")}
            for r in calibrated_risks
        ],
        "bid_decision": {
            "recommendation": bid_decision.get("preliminary_recommendation") if bid_decision else None,
            "status": bid_decision.get("status") if bid_decision else None,
        } if bid_decision and has_tkp else None,
        "included_sections": export_json.get("included_sections", []),
        "redacted_sections": export_json.get("redacted_sections", []),
        "blocked_sections": export_json.get("blocked_sections", []),
        "supplier_sourcing": {
            "manual_candidates_file_found": bool(supplier_candidates_notes.get("found")),
            "manual_candidates_file": supplier_candidates_notes.get("path"),
            "manual_candidates_line_count": supplier_candidates_notes.get("line_count", 0),
            "registry_supplier_count": supplier_sourcing.get("registry_supplier_count", 0) if supplier_sourcing else 0,
            "vendor_list_supplier_count": supplier_sourcing.get("vendor_list_supplier_count", 0) if supplier_sourcing else 0,
            "top_suppliers": supplier_sourcing.get("top_suppliers", []) if supplier_sourcing else [],
        },
    }

    (output_dir / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "internal_operator_analysis.md").write_text(internal_analysis_md, encoding="utf-8")
    (output_dir / "requirements.json").write_text(json.dumps(requirements, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "supplier_questions.json").write_text(json.dumps(supplier_questions, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "rfq_request_draft.md").write_text(rfq_request_draft_md, encoding="utf-8")
    (output_dir / "calibrated_contract_risk_memo.md").write_text(
        _build_risk_memo_markdown(calibrated_risks), encoding="utf-8"
    )

    if has_tkp and normalized_quotes is not None:
        (output_dir / "tkp_normalized_quotes.json").write_text(
            json.dumps(normalized_quotes, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if has_tkp and tkp_normalization_report_md is not None:
        (output_dir / "tkp_normalization_report.md").write_text(tkp_normalization_report_md, encoding="utf-8")
    if has_tkp and tkp_comparison:
        (output_dir / "tkp_comparison.json").write_text(json.dumps(tkp_comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    if has_tkp and economics:
        (output_dir / "economics_summary.json").write_text(json.dumps(economics, ensure_ascii=False, indent=2), encoding="utf-8")
    if has_tkp and bid_decision:
        (output_dir / "bid_decision_recommendation.md").write_text(
            _build_bid_decision_markdown(bid_decision, economics), encoding="utf-8"
        )

    (export_dir / "operator_report.md").write_text(export_md, encoding="utf-8")
    (export_dir / "export_summary.json").write_text(json.dumps(export_json, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  Run summary:               {output_dir / 'run_summary.json'}")
    print(f"  Internal analysis:          {output_dir / 'internal_operator_analysis.md'}")
    print(f"  Requirements:               {output_dir / 'requirements.json'}")
    print(f"  Supplier questions:         {output_dir / 'supplier_questions.json'}")
    print(f"  RFQ draft:                  {output_dir / 'rfq_request_draft.md'}")
    print(f"  Contract risk memo:         {output_dir / 'calibrated_contract_risk_memo.md'}")
    if has_tkp:
        print(f"  TKP normalized quotes:      {output_dir / 'tkp_normalized_quotes.json'}")
        print(f"  TKP normalization report:   {output_dir / 'tkp_normalization_report.md'}")
        print(f"  TKP comparison:             {output_dir / 'tkp_comparison.json'}")
        print(f"  Economics summary:          {output_dir / 'economics_summary.json'}")
        print(f"  Bid decision:               {output_dir / 'bid_decision_recommendation.md'}")
    print(f"  Partner report:             {export_dir / 'operator_report.md'}")
    print(f"  Export summary:             {export_dir / 'export_summary.json'}")


def _build_rfq_draft_markdown(supplier_questions: list[dict[str, Any]]) -> str:
    lines = [
        "# RFQ / TKP Request Draft",
        "",
        "**Generated**: " + datetime.now(UTC).isoformat(),
        "",
        "---",
        "## Supplier Questions",
        "",
        "Please confirm the following for the subject tender:",
        "",
    ]
    for i, sq in enumerate(supplier_questions, 1):
        lines.append(f"{i}. {sq.get('question', '')}")
    lines += [
        "",
        "---",
        "*This draft was generated for manual sending. No automatic email is sent.*",
        "*Review and customize before sending to suppliers.*",
    ]
    return "\n".join(lines)


def _build_structured_rfq_draft_markdown(rfq_draft: dict[str, Any]) -> str:
    lines = [
        "# RFQ / TKP Request Draft",
        "",
        "**Generated**: " + datetime.now(UTC).isoformat(),
        "",
        f"**Subject**: {rfq_draft.get('email_subject', 'RFQ / TKP request')}",
        "",
        "---",
        "## Intro",
        "",
        rfq_draft.get("intro", "Please confirm your ability to support this tender request."),
        "",
        "## Requirements Summary",
        "",
    ]
    for item in rfq_draft.get("requirements_summary", []):
        lines.append(f"- {item}")
    lines += [
        "",
        "## Supplier Questions",
        "",
    ]
    for i, question in enumerate(rfq_draft.get("supplier_questions", []), 1):
        lines.append(f"{i}. {question}")
    lines += [
        "",
        "## Requested Response Items",
        "",
    ]
    for item in rfq_draft.get("requested_response_items", []):
        lines.append(f"- {item}")
    lines += [
        "",
        "## Commercial Terms to Clarify",
        "",
    ]
    for item in rfq_draft.get("commercial_terms", []):
        lines.append(f"- {item}")
    lines += [
        "",
        "---",
        rfq_draft.get("closing_note", "Human review is required before any external communication."),
        "*This draft was generated for manual sending. No automatic email is sent.*",
        "*Review and customize before sending to suppliers.*",
    ]
    return "\n".join(lines)


def _build_risk_memo_markdown(calibrated_risks: list[dict[str, Any]]) -> str:
    lines = [
        "# Calibrated Contract Risk Memo",
        "",
        f"**Generated**: {datetime.now(UTC).isoformat()}",
        "",
        "## Methodology",
        "",
        "Risks are classified into three tiers:",
        "- **Market-standard harsh term**: Common in public procurement, not automatic no-go.",
        "- **Commercially material risk**: Factor into pricing, timeline, and supplier selection.",
        "- **Deal-breaker candidate**: Escalate before proceeding.",
        "",
        "---",
        "",
    ]
    for risk in calibrated_risks:
        classification = risk.get("classification", "unknown")
        icon = {
            "market_standard_harsh_term": "STANDARD",
            "commercially_material_risk": "MATERIAL",
            "deal_breaker_candidate": "DEAL-BREAKER",
        }.get(classification, "UNKNOWN")
        lines.append(f"### [{icon}] {risk.get('clause', 'Unknown')}")
        lines.append(f"")
        lines.append(f"- **Risk**: {risk.get('description', '')}")
        lines.append(f"- **Classification**: {classification}")
        lines.append(f"- **Impact**: {risk.get('impact', '')}")
        lines.append(f"- **Mitigation**: {risk.get('mitigation', '')}")
        lines.append(f"- **Operator decision required**: {risk.get('operator_decision_required', False)}")
        lines.append(f"")
    lines += [
        "---",
        "## Important Note",
        "",
        "Harsh customer contract terms are often market-standard in public procurement. ",
        "Typical penalties, post-payment, one-sided acceptance, and unilateral termination ",
        "are **not** automatic no-go. No-go should be reserved for execution-breaking risks.",
    ]
    return "\n".join(lines)


def _build_bid_decision_markdown(
    bid_decision: dict[str, Any],
    economics: dict[str, Any] | None,
) -> str:
    lines = [
        "# Bid Decision Recommendation",
        "",
        f"**Generated**: {datetime.now(UTC).isoformat()}",
        f"**Status**: {bid_decision.get('status', 'unknown')}",
        "",
        "---",
        "## Preliminary Recommendation",
        "",
        f"**{bid_decision.get('preliminary_recommendation', 'No recommendation')}**",
        "",
        f"**Rationale**: {bid_decision.get('rationale', '')}",
        "",
        "---",
        "## Risk Summary",
        "",
        f"- Deal-breaker candidates: {bid_decision.get('deal_breaker_count', 0)}",
        f"- Commercially material risks: {bid_decision.get('material_risk_count', 0)}",
        f"- Market-standard harsh terms: {bid_decision.get('market_standard_count', 0)}",
        f"- Suppliers with offers: {bid_decision.get('suppliers_with_offers', 0)}",
        "",
    ]
    if economics:
        lines += [
            "---",
            "## Economics",
            "",
            f"- Supplier count: {economics.get('supplier_count', 'N/A')}",
            f"- Lowest price: {economics.get('lowest_price', 'unknown')}",
            f"- Highest price: {economics.get('highest_price', 'unknown')}",
            f"- Average price: {economics.get('average_price', 'unknown')}",
            f"- Total estimated cost: {economics.get('total_estimated_cost', 'unknown')}",
            f"- Recommended bid price: {economics.get('recommended_bid_price', 'unknown')}",
            f"- Target margin: {economics.get('target_margin', 'unknown')}",
            "",
        ]
    lines += [
        "---",
        "*This is a preliminary recommendation only. Final bid decision requires human review.*",
        "*Final submission remains fully manual.*",
    ]
    return "\n".join(lines)


def _create_export_package_and_deliver(
    ws_id: str,
    sections: dict[str, str],
    intake_records: list,
    tender_label: str,
) -> tuple:
    package = generate_export_package(
        partner_workspace_id=ws_id,
        scenario_or_tender_id=tender_label,
        report_sections=sections,
        intake_records=intake_records,
    )
    print(f"  Export package: {package.export_package_id}")
    print(f"  Status: {package.export_status.value}")
    print(f"  Included: {package.included_sections}")
    print(f"  Redacted: {package.redacted_sections}")
    print(f"  Blocked: {package.blocked_sections}")

    if package.export_status.value != "blocked":
        approved = approve_for_delivery(package)
        delivered = mark_delivered_manually(approved)
        print(f"  Approved & marked delivered: {delivered.export_status.value}")
    else:
        print("  WARNING: Export blocked due to restricted sections. Manual review required.")
        delivered = package

    return package, delivered


def _record_feedback_and_outcome(ws_id: str, package_id: str) -> tuple:
    feedback = create_feedback(
        partner_workspace_id=ws_id,
        export_package_id_or_pilot_run_id=package_id,
        feedback_source=FeedbackSource.internal_review,
        feedback_type=FeedbackType.positive,
        usefulness_score=4,
        clarity_score=4,
        trust_score=4,
        would_pay_signal=None,
        operator_notes="PP1R tender operator run completed. Awaiting real partner feedback.",
        next_action=NextAction.iterate_report,
    )
    print(f"  Feedback recorded: {feedback.feedback_id}")

    outcome = create_outcome(
        partner_workspace_id=ws_id,
        pilot_run_id=package_id,
        final_decision=FinalDecision.continue_design_partner,
        decision_reason="Tender operator folder processed. Awaiting partner review.",
        conversion_readiness="not_assessed",
        recommended_next_step="Send RFQ to suppliers and collect TKP.",
    )
    print(f"  Outcome recorded: {outcome.outcome_id}")
    return feedback, outcome


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a tender operator pilot from a local folder (RFQ-first workflow)."
    )
    parser.add_argument("--operator-id", required=True, help="Operator identifier (e.g., tender_operator_001)")
    parser.add_argument("--tender-dir", required=True, type=Path, help="Path to the tender folder")
    parser.add_argument("--provider", required=True, choices=SUPPORTED_PROVIDER_FLAGS, help="Analysis provider")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory (default: <tender-dir>/05_system_output)")
    args = parser.parse_args()
    settings = get_settings()
    requested_provider = _canonical_provider_name(args.provider)
    execution_provider_mode, configured_resolved_provider = _resolve_provider_request(
        requested_provider,
        settings.llm_provider,
    )
    resolved_provider = configured_resolved_provider

    tender_dir: Path = args.tender_dir.resolve()
    operator_id: str = args.operator_id
    tender_label: str = tender_dir.name
    operator_dir: Path = tender_dir.parent

    if args.output_dir:
        output_dir = args.output_dir.resolve()
    else:
        output_dir = tender_dir / "05_system_output"

    export_dir = tender_dir / "06_partner_export"

    print("=== Tender Operator Pilot Runner (PP1R) ===")
    print(f"  Operator ID:  {operator_id}")
    print(f"  Tender dir:   {tender_dir}")
    print(f"  Requested provider: {requested_provider}")
    print(f"  Resolved provider:  {resolved_provider}")
    print(f"  Output dir:   {output_dir}")
    print()

    # Step 1: Validate folder structure
    print("[1] Validating folder structure...")
    _validate_tender_dir(tender_dir)
    _ensure_output_dirs(output_dir, export_dir)
    print("  OK")

    # Step 2: Read operator profile
    print("[2] Reading operator profile...")
    operator_profile = _read_operator_profile(operator_dir)
    if operator_profile["found"]:
        print(f"  Profile found: {operator_profile['line_count']} lines")
    else:
        print("  No operator profile found (optional)")

    supplier_candidates_notes = _read_supplier_candidates_notes(tender_dir)
    if supplier_candidates_notes["found"]:
        print(
            f"  Supplier candidates notes found: {supplier_candidates_notes['line_count']} lines"
        )

    # Step 3: Read extracted text files
    print("[3] Reading extracted text files...")
    extracted_dir = tender_dir / "02_extracted_text"
    notice_text = _read_text_file(extracted_dir / "notice.txt")
    technical_spec_text = _read_text_file(extracted_dir / "technical_spec.txt")
    contract_draft_text = _read_text_file(extracted_dir / "contract_draft.txt")
    print(f"  notice.txt:          {len(notice_text)} chars")
    print(f"  technical_spec.txt:  {len(technical_spec_text)} chars")
    print(f"  contract_draft.txt:  {len(contract_draft_text)} chars")

    # Step 4: Create workspace
    print("[4] Creating workspace...")
    ws = create_workspace(
        partner_label=operator_id,
        created_by="pp1r.tender.operator.runner",
        data_handling_notes=f"PP1R run for tender {tender_label}. Tender operator workflow.",
    )
    print(f"  Workspace: {ws.partner_workspace_id}")

    # Step 5: Create intake records
    print("[5] Creating intake records...")
    records_info: list[dict[str, Any]] = []
    intake_records: list = []

    notice_record = add_intake_record(
        partner_workspace_id=ws.partner_workspace_id,
        source_type=IntakeSourceType.notice_text,
        source_label=f"notice.txt ({tender_label})",
        contains_sensitive_data=False,
        redaction_status=RedactionStatus.not_required,
    )
    notice_record = approve_for_pilot_use(notice_record)
    records_info.append({
        "source_label": notice_record.source_label,
        "source_type": notice_record.source_type,
        "redaction_status": notice_record.redaction_status,
        "visibility_level": notice_record.visibility_level,
    })
    intake_records.append(notice_record)
    print(f"  Notice record: {notice_record.intake_record_id}")

    for src_type, label, filename in [
        (IntakeSourceType.technical_spec_text, f"technical_spec.txt ({tender_label})", "technical_spec.txt"),
        (IntakeSourceType.contract_draft_text, f"contract_draft.txt ({tender_label})", "contract_draft.txt"),
    ]:
        record = add_intake_record(
            partner_workspace_id=ws.partner_workspace_id,
            source_type=src_type,
            source_label=label,
            contains_sensitive_data=True,
            redaction_status=RedactionStatus.raw_received,
        )
        record = require_redaction(record)
        record = mark_redacted_for_partner(record)
        records_info.append({
            "source_label": record.source_label,
            "source_type": record.source_type,
            "redaction_status": record.redaction_status,
            "visibility_level": record.visibility_level,
        })
        intake_records.append(record)
        print(f"  {filename} record: {record.intake_record_id} (redacted for partner)")

    # Step 6: Run analysis
    print(f"[6] Running analysis (provider={requested_provider})...")
    requirements = _run_stub_requirements_extraction(notice_text, technical_spec_text, contract_draft_text)
    requirements["_notice_chars"] = len(notice_text)
    requirements["_spec_chars"] = len(technical_spec_text)
    requirements["_contract_chars"] = len(contract_draft_text)
    if operator_profile.get("supplier_profile"):
        requirements.setdefault("analysis_context", {})["supplier_profile"] = operator_profile["supplier_profile"]
    analysis_mode = "stub"

    calibrated_risks = _run_stub_calibrated_contract_risk(contract_draft_text)
    supplier_questions = _run_stub_supplier_questions()
    rfq_request_draft_md = _build_rfq_draft_markdown(supplier_questions)

    tkp_files = _detect_tkp_files(tender_dir)
    has_tkp = len(tkp_files) > 0
    llm_result: dict[str, Any] | None = None
    normalized_quotes_payload: list[dict[str, Any]] | None = None
    tkp_normalization_report_md: str | None = None
    tkp_comparison: dict[str, Any] | None = None
    economics: dict[str, Any] | None = None
    bid_decision: dict[str, Any] | None = None

    if has_tkp:
        print(f"  TKP files found: {len(tkp_files)}")
    else:
        print("  No TKP files found. Run will stop at rfq_ready / collect_tkp.")

    if requested_provider != "stub":
        llm_result = _try_llm_workflow_analysis(
            operator_id,
            operator_profile,
            notice_text,
            technical_spec_text,
            contract_draft_text,
            tkp_files,
            provider_mode=execution_provider_mode,
            resolved_provider=resolved_provider,
        )
        if llm_result:
            analysis_mode = llm_result.get("analysis_mode", "llm")
            resolved_provider = llm_result.get("resolved_provider", resolved_provider)
            llm_requirements = llm_result.get("requirements") or {}
            requirements.update(llm_requirements)
            if operator_profile.get("supplier_profile"):
                requirements.setdefault("analysis_context", {})["supplier_profile"] = operator_profile["supplier_profile"]
            requirements["llm_control"] = llm_result.get("llm_control", {})

            if llm_result.get("supplier_questions"):
                supplier_questions = llm_result["supplier_questions"]
            if llm_result.get("rfq_draft"):
                rfq_request_draft_md = _build_structured_rfq_draft_markdown(llm_result["rfq_draft"])
            if llm_result.get("contract_risks"):
                calibrated_risks = llm_result["contract_risks"]
            print(f"  Controlled workflow mode: {analysis_mode}")
        else:
            resolved_provider = "stub"
            print("  -> Falling back to stub analysis")

    if has_tkp:
        from src.shared.db import models as _db_models  # noqa: F401
        from src.shared.db.base import Base
        from src.shared.db.session import SessionLocal, engine

        Base.metadata.create_all(engine)
        llm_quotes = None
        if llm_result and llm_result.get("quote_normalization"):
            llm_quotes = llm_result["quote_normalization"].get("quotes", [])
        with SessionLocal() as session:
            normalized_quotes = normalize_tkp_quotes(session, tkp_files=tkp_files, llm_quotes=llm_quotes)
        normalized_quotes_payload = [quote.model_dump() for quote in normalized_quotes]
        tkp_normalization_report_md = build_tkp_normalization_report(normalized_quotes)
        tkp_method = (
            "llm_normalized"
            if any(quote.parser_mode in {"llm", "hybrid"} for quote in normalized_quotes)
            else "deterministic_normalized"
        )
        tkp_comparison = build_tkp_comparison_from_normalized_quotes(
            normalized_quotes,
            analysis_mode=analysis_mode,
            method=tkp_method,
        )
        economics = _run_stub_economics(tkp_comparison, operator_profile)
        if llm_result and llm_result.get("bid_decision"):
            bid_decision = _materialize_llm_bid_decision(
                llm_result["bid_decision"],
                tkp_comparison,
                calibrated_risks,
            )
        else:
            bid_decision = _run_stub_bid_decision(tkp_comparison, economics, calibrated_risks)
        print(f"  TKP normalization generated: {len(normalized_quotes_payload)} files")
        print(f"  TKP comparison generated: {len(tkp_comparison.get('suppliers', []))} suppliers")
        print("  Economics summary generated")
        print(f"  Bid decision: {bid_decision.get('preliminary_recommendation', 'N/A')}")

    supplier_sourcing = _build_supplier_sourcing_summary(requirements)
    if supplier_sourcing:
        print(
            "  Supplier sourcing snapshot:"
            f" registry={supplier_sourcing.get('registry_supplier_count', 0)},"
            f" vendor_list={supplier_sourcing.get('vendor_list_supplier_count', 0)},"
            f" top={len(supplier_sourcing.get('top_suppliers', []))}"
        )

    records_with_refs = copy.deepcopy(records_info)
    for r, rec in zip(records_with_refs, intake_records):
        r["record"] = rec

    # Step 7: Build internal operator analysis
    print("[7] Building internal operator analysis...")
    internal_md = _build_internal_operator_analysis(
        requirements, calibrated_risks, supplier_questions,
        operator_profile, supplier_candidates_notes, supplier_sourcing,
        normalized_quotes_payload, tkp_comparison, economics, bid_decision,
        records_with_refs, notice_text, technical_spec_text, contract_draft_text,
    )

    # Step 8: Build partner export sections
    print("[8] Building partner export sections...")
    sections = _build_operator_operator_report_sections(
        requirements, calibrated_risks, tkp_comparison, bid_decision, has_tkp, analysis_mode,
    )

    # Step 9: Generate export package
    print("[9] Generating export package...")
    package, delivered = _create_export_package_and_deliver(
        ws.partner_workspace_id, sections, intake_records, tender_label,
    )

    # Step 10: Render export outputs
    print("[10] Rendering export outputs...")
    export_md = render_export_markdown(package)
    export_json = render_export_json(package)

    # Step 11: Write output files
    print("[11] Writing output files...")
    _write_outputs(
        output_dir, export_dir,
        operator_id=operator_id,
        tender_dir_str=str(tender_dir),
        ws_id=ws.partner_workspace_id,
        records=records_info,
        requirements=requirements,
        calibrated_risks=calibrated_risks,
        supplier_questions=supplier_questions,
        tkp_comparison=tkp_comparison,
        economics=economics,
        bid_decision=bid_decision,
        normalized_quotes=normalized_quotes_payload,
        tkp_normalization_report_md=tkp_normalization_report_md,
        internal_analysis_md=internal_md,
        rfq_request_draft_md=rfq_request_draft_md,
        package_id=package.export_package_id,
        export_md=export_md,
        export_json=export_json,
        delivery_status=delivered.export_status.value if hasattr(delivered, "export_status") else "unknown",
        has_tkp=has_tkp,
        analysis_mode=analysis_mode,
        requested_provider=requested_provider,
        resolved_provider=resolved_provider,
        supplier_candidates_notes=supplier_candidates_notes,
        supplier_sourcing=supplier_sourcing,
    )

    print("[11A] Building human review pack...")
    review_pack = build_human_review_pack(
        output_dir,
        operator_id=operator_id,
        tender_label=tender_label,
    )
    human_review_json_path = output_dir / "human_review_required.json"
    human_review_md_path = output_dir / "human_review_checklist.md"
    operator_decision_form_path = output_dir / "operator_decision_form.md"
    human_review_json_path.write_text(
        json.dumps(review_pack.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    human_review_md_path.write_text(build_human_review_checklist_markdown(review_pack), encoding="utf-8")
    operator_decision_form_path.write_text(build_operator_decision_form_markdown(review_pack), encoding="utf-8")
    update_run_summary_with_human_review(output_dir, review_pack)
    print(f"  Human review pack:          {human_review_json_path}")
    print(f"  Human review checklist:     {human_review_md_path}")
    print(f"  Operator decision form:     {operator_decision_form_path}")

    # Step 12: Record feedback and outcome
    print("[12] Recording feedback and outcome...")
    _record_feedback_and_outcome(ws.partner_workspace_id, package.export_package_id)

    pilot_status = "tkp_received_economics_ready" if has_tkp else "rfq_ready_collect_tkp"
    print()
    print(f"=== PP1R Run Complete (status: {pilot_status}) ===")
    print(f"  Operator ID:  {operator_id}")
    print(f"  Tender dir:   {tender_dir}")
    print(f"  Output dir:   {output_dir}")
    print(f"  Export dir:   {export_dir}")


if __name__ == "__main__":
    main()
