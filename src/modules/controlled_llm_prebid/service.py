import json
import re
import uuid
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.agent_registry.models import AgentRegistryRecord
from src.modules.agent_registry.schemas import BuildAgentRegistryEntryInput, BuildAgentRegistryRequest
from src.modules.agent_registry.service import build_agent_registry
from src.modules.controlled_llm_prebid.schemas import (
    LLMBidDecisionDraft,
    LLMContractRisksDraft,
    LLMParticipantRequirementsDraft,
    LLMQuoteNormalizationDraft,
    LLMSupplierQuestionsDraft,
    LLMTechnicalRequirementsDraft,
    LLMTenderOperatorBidDecisionDraft,
    LLMTenderOperatorContractRiskMemoDraft,
    LLMTenderOperatorRequirementsDraft,
    LLMTenderOperatorRFQDraft,
    LLMTenderSummaryDraft,
)
from src.modules.prompt_schema_library.models import PromptSchemaRecord
from src.modules.prompt_schema_library.schemas import BuildPromptSchemaAssetInput, BuildPromptSchemaLibraryRequest
from src.modules.prompt_schema_library.service import build_prompt_schema_library
from src.modules.runtime_control_traces.schemas import CreateRuntimeControlTraceRequest
from src.modules.runtime_control_traces.service import create_runtime_control_trace
from src.shared.config.settings import Settings, get_settings
from src.shared.enums import (
    AgentActivationState,
    HumanReviewStatus,
    PromptRiskClass,
    PromptSchemaAssetStatus,
    PromptSchemaAssetType,
    PromptValidationMode,
    RuntimeTraceActionType,
    RuntimeTraceActorType,
    RuntimeTraceDisposition,
    RuntimeTraceValidationStatus,
)
from src.shared.errors import ValidationError


PROMPT_VERSION = "v1"


class _PromptSpec:
    def __init__(self, asset_key: str, purpose: str, output_schema_ref: str, template: str) -> None:
        self.asset_key = asset_key
        self.purpose = purpose
        self.output_schema_ref = output_schema_ref
        self.template = template


@dataclass(frozen=True)
class _PromptBundle:
    agent_key: str
    agent_label: str
    runtime_context: str
    runtime_slice: str
    target_module: str
    source_entity: str
    description: str
    analysis_mode_stub: str
    analysis_mode_provider: str
    prompt_specs: dict[str, _PromptSpec]
    output_models: dict[str, Any]


COMMERCIAL_PREBID_PROMPT_SPECS = {
    "tender_summary": _PromptSpec(
        asset_key="commercial-prebid-tender-summary",
        purpose="Generate a bounded summary and relevance statement for internal pre-bid analysis.",
        output_schema_ref="LLMTenderSummaryDraft",
        template=(
            "Summarize the tender for an internal operator. "
            "Return JSON with keys tender_summary and why_relevant."
        ),
    ),
    "technical_requirements": _PromptSpec(
        asset_key="commercial-prebid-technical-requirements",
        purpose="Extract a bounded list of technical requirements for internal review.",
        output_schema_ref="LLMTechnicalRequirementsDraft",
        template="Return JSON with key technical_requirements as a list of strings.",
    ),
    "participant_requirements": _PromptSpec(
        asset_key="commercial-prebid-participant-requirements",
        purpose="Extract bidder or participant requirements for internal review.",
        output_schema_ref="LLMParticipantRequirementsDraft",
        template="Return JSON with key participant_requirements as a list of strings.",
    ),
    "contract_risks": _PromptSpec(
        asset_key="commercial-prebid-contract-risks",
        purpose="Highlight contract-risk themes without making final legal decisions.",
        output_schema_ref="LLMContractRisksDraft",
        template="Return JSON with key contract_risks as a list of strings.",
    ),
    "bid_decision": _PromptSpec(
        asset_key="commercial-prebid-bid-decision",
        purpose="Draft a bounded recommendation for internal review only.",
        output_schema_ref="LLMBidDecisionDraft",
        template=(
            "Return JSON with keys recommendation, rationale, and next_actions. "
            "Recommendation must be GO, GO_WITH_CONDITIONS, NEEDS_REVIEW, or NO_GO."
        ),
    ),
}

COMMERCIAL_PREBID_OUTPUT_MODELS = {
    "tender_summary": LLMTenderSummaryDraft,
    "technical_requirements": LLMTechnicalRequirementsDraft,
    "participant_requirements": LLMParticipantRequirementsDraft,
    "contract_risks": LLMContractRisksDraft,
    "bid_decision": LLMBidDecisionDraft,
}

COMMERCIAL_PREBID_BUNDLE = _PromptBundle(
    agent_key="commercial-prebid-analyst",
    agent_label="Commercial Pre-Bid Analyst",
    runtime_context="COMMERCIAL_PREBID_ANALYSIS",
    runtime_slice="COMMERCIAL_MVP_V1",
    target_module="commercial_prebid_demo",
    source_entity="COMMERCIAL_PREBID_LLM_ANALYSIS",
    description="Bounded commercial pre-bid drafting profile with mandatory human review.",
    analysis_mode_stub="llm_controlled_stub",
    analysis_mode_provider="llm_controlled_provider",
    prompt_specs=COMMERCIAL_PREBID_PROMPT_SPECS,
    output_models=COMMERCIAL_PREBID_OUTPUT_MODELS,
)

TENDER_OPERATOR_PROMPT_SPECS = {
    "requirements": _PromptSpec(
        asset_key="tender-operator-requirements",
        purpose="Extract structured RFQ-first requirements from tender documents.",
        output_schema_ref="LLMTenderOperatorRequirementsDraft",
        template=(
            "Return JSON with keys tender_summary, technical_requirements, qualification_requirements, "
            "document_requirements, evaluation_criteria, and procurement_categories. "
            "Keep each list concise and operator-friendly."
        ),
    ),
    "supplier_questions": _PromptSpec(
        asset_key="tender-operator-supplier-questions",
        purpose="Prepare supplier clarification questions for RFQ-first outreach.",
        output_schema_ref="LLMSupplierQuestionsDraft",
        template=(
            "Return JSON with key supplier_questions. Each item must contain question and category. "
            "Focus on spec match, delivery, certificates, warranty, pricing, payment, and analogs."
        ),
    ),
    "rfq_draft": _PromptSpec(
        asset_key="tender-operator-rfq-draft",
        purpose="Draft a manual-review RFQ request package for supplier outreach.",
        output_schema_ref="LLMTenderOperatorRFQDraft",
        template=(
            "Return JSON with keys email_subject, intro, requirements_summary, supplier_questions, "
            "requested_response_items, commercial_terms, and closing_note. "
            "requirements_summary, supplier_questions, requested_response_items, and commercial_terms "
            "must each be JSON arrays of strings, never numbered or newline-formatted strings. "
            "The draft must not instruct autonomous sending."
        ),
    ),
    "contract_risk_memo": _PromptSpec(
        asset_key="tender-operator-contract-risk-memo",
        purpose="Draft a calibrated contract risk memo for internal operator review.",
        output_schema_ref="LLMTenderOperatorContractRiskMemoDraft",
        template=(
            "Return JSON with key contract_risks. Each item must contain clause, description, "
            "classification, impact, mitigation, and operator_decision_required. "
            "Use only these classifications: market_standard_harsh_term, commercially_material_risk, deal_breaker_candidate."
        ),
    ),
    "quote_normalization": _PromptSpec(
        asset_key="tender-operator-quote-normalization",
        purpose="Normalize supplier TKP/quote data into a comparison-friendly structure.",
        output_schema_ref="LLMQuoteNormalizationDraft",
        template=(
            "Return JSON with key quotes. Each item must contain supplier_label, supplier_id, source_file, "
            "normalization_status, quote_date, valid_until, currency_code, vat_included, vat_rate, total_amount, "
            "total_amount_without_vat, delivery_cost, delivery_time_days, payment_terms, warranty_months, "
            "availability, includes_delivery, includes_installation, certificates_available, contact_email, "
            "contact_phone, line_items, extraction_confidence, fields_needing_review, warnings, parser_mode, "
            "and human_review_required=true. Unknown values must be null, not free-form placeholder strings."
        ),
    ),
    "bid_decision": _PromptSpec(
        asset_key="tender-operator-bid-decision",
        purpose="Draft a preliminary bid recommendation from normalized quote and risk context.",
        output_schema_ref="LLMTenderOperatorBidDecisionDraft",
        template=(
            "Return JSON with keys preliminary_recommendation, rationale, next_actions, and human_review_required. "
            "Recommendation must be GO, GO_WITH_CONDITIONS, NEEDS_REVIEW, or NO_GO. "
            "Do not recommend external execution without human review."
        ),
    ),
}

TENDER_OPERATOR_OUTPUT_MODELS = {
    "requirements": LLMTenderOperatorRequirementsDraft,
    "supplier_questions": LLMSupplierQuestionsDraft,
    "rfq_draft": LLMTenderOperatorRFQDraft,
    "contract_risk_memo": LLMTenderOperatorContractRiskMemoDraft,
    "quote_normalization": LLMQuoteNormalizationDraft,
    "bid_decision": LLMTenderOperatorBidDecisionDraft,
}

TENDER_OPERATOR_BUNDLE = _PromptBundle(
    agent_key="tender-operator-rfq-analyst",
    agent_label="Tender Operator RFQ Analyst",
    runtime_context="TENDER_OPERATOR_RFQ_WORKFLOW",
    runtime_slice="TENDER_OPERATOR_RFQ_V1",
    target_module="tender_operator_pilot",
    source_entity="TENDER_OPERATOR_LLM_ANALYSIS",
    description="Bounded tender-operator RFQ-first drafting profile with mandatory human review.",
    analysis_mode_stub="llm_tender_operator_stub",
    analysis_mode_provider="llm_tender_operator_provider",
    prompt_specs=TENDER_OPERATOR_PROMPT_SPECS,
    output_models=TENDER_OPERATOR_OUTPUT_MODELS,
)


@dataclass
class ControlledLLMAnalysisResult:
    analysis_mode: str
    resolved_provider: str
    overall_review_status: str
    sections: dict[str, dict[str, Any]]
    trace_ids: list[str]


@dataclass
class ControlledTenderOperatorWorkflowResult:
    analysis_mode: str
    resolved_provider: str
    overall_review_status: str
    requirements: dict[str, Any]
    supplier_questions: list[dict[str, Any]]
    rfq_draft: dict[str, Any]
    contract_risks: list[dict[str, Any]]
    quote_normalization: dict[str, Any] | None
    bid_decision: dict[str, Any] | None
    sections: dict[str, dict[str, Any]]
    trace_ids: list[str]


@dataclass(frozen=True)
class _PreparedContext:
    context: dict[str, Any]
    redaction_applied: bool
    input_chars_before: int
    input_chars_after: int


def _find_agent(session: Session, agent_key: str) -> AgentRegistryRecord | None:
    return session.scalar(select(AgentRegistryRecord).where(AgentRegistryRecord.agent_key == agent_key))


def _find_prompt(session: Session, asset_key: str) -> PromptSchemaRecord | None:
    return session.scalar(
        select(PromptSchemaRecord).where(
            PromptSchemaRecord.asset_key == asset_key,
            PromptSchemaRecord.version_tag == PROMPT_VERSION,
        )
    )


def _ensure_metadata(session: Session, bundle: _PromptBundle) -> tuple[AgentRegistryRecord, dict[str, PromptSchemaRecord]]:
    agent = _find_agent(session, bundle.agent_key)
    if agent is None:
        registry_set = build_agent_registry(
            session,
            BuildAgentRegistryRequest(
                registry_scope="INTERNAL",
                entries=[
                    BuildAgentRegistryEntryInput(
                        agent_key=bundle.agent_key,
                        agent_label=bundle.agent_label,
                        owner_operator="Runtime Owner",
                        reviewer_role="Commercial Reviewer",
                        activation_state=AgentActivationState.REVIEWED,
                        allowed_action_classes=["DRAFT_ANALYSIS", "STRUCTURE_METADATA"],
                        forbidden_action_classes=[
                            "AUTONOMOUS_SUBMISSION",
                            "SUPPLIER_OUTREACH",
                            "EXTERNAL_EXECUTION",
                        ],
                        description=bundle.description,
                    )
                ],
            ),
        )
        agent_records = session.scalars(
            select(AgentRegistryRecord).where(AgentRegistryRecord.agent_registry_set_id == registry_set.agent_registry_set_id)
        ).all()
        agent = list(agent_records)[0]

    prompts: dict[str, PromptSchemaRecord] = {}
    missing_sections: list[str] = []
    for section, spec in bundle.prompt_specs.items():
        prompt = _find_prompt(session, spec.asset_key)
        if prompt is None:
            missing_sections.append(section)
        else:
            prompts[section] = prompt

    if missing_sections:
        assets: list[BuildPromptSchemaAssetInput] = []
        for section in missing_sections:
            spec = bundle.prompt_specs[section]
            output_schema = bundle.output_models[section].model_json_schema()
            assets.append(
                BuildPromptSchemaAssetInput(
                    asset_key=spec.asset_key,
                    prompt_name=spec.asset_key,
                    asset_type=PromptSchemaAssetType.PROMPT_TEMPLATE,
                    prompt_version=PROMPT_VERSION,
                    owner_operator="Runtime Owner",
                    reviewer_role="Commercial Reviewer",
                    asset_status=PromptSchemaAssetStatus.REVIEWED,
                    prompt_purpose=spec.purpose,
                    associated_runtime_slice=bundle.runtime_slice,
                    input_schema_ref=f"{bundle.runtime_context}_INPUT_V1",
                    output_schema_ref=spec.output_schema_ref,
                    validation_mode=PromptValidationMode.STRICT,
                    allowed_use_contexts=[bundle.runtime_context],
                    forbidden_use_contexts=[
                        "AUTONOMOUS_SUBMISSION",
                        "SUPPLIER_OUTREACH",
                        "LEGAL_FINAL_DECISION",
                        "PROCUREMENT_PLATFORM_EXECUTION",
                    ],
                    human_review_required=True,
                    risk_class=PromptRiskClass.HIGH,
                    notes="Controlled LLM drafting only.",
                    rationale="Bounded draft-generation only; all outputs require human review.",
                    asset_payload_json={
                        "template": spec.template,
                        "output_schema_json": output_schema,
                    },
                    linked_agent_registry_ids=[agent.agent_registry_id],
                )
            )
        build_prompt_schema_library(
            session,
            BuildPromptSchemaLibraryRequest(library_scope="INTERNAL", assets=assets),
        )
        for section, spec in bundle.prompt_specs.items():
            prompts[section] = _find_prompt(session, spec.asset_key)  # type: ignore[assignment]

    return agent, prompts


class _CommercialPreBidStubProvider:
    def __init__(self, invalid: bool = False) -> None:
        self.invalid = invalid

    def generate(self, section: str, context: dict[str, Any]) -> dict[str, Any]:
        if self.invalid and section == "bid_decision":
            return {"recommendation": "AUTO_SUBMIT"}
        if section == "tender_summary":
            return {
                "tender_summary": f"{context['title']} for {context['customer_name']} with a staged delivery scope.",
                "why_relevant": "Matches the company's electrical-supply profile and supports a bounded pre-bid review.",
            }
        if section == "technical_requirements":
            return {
                "technical_requirements": [
                    "Provide low-voltage switchgear cabinets.",
                    "Support staged delivery and commissioning-ready labeling.",
                    "Include warranty and technical-passport package.",
                ]
            }
        if section == "participant_requirements":
            return {
                "participant_requirements": context["participant_requirements"],
            }
        if section == "contract_risks":
            return {
                "contract_risks": [
                    "Payment timing must be reviewed manually.",
                    "Delay penalties should be reconciled with delivery assumptions.",
                    "Acceptance flow must be clarified before bid drafting.",
                ]
            }
        if section == "bid_decision":
            return {
                "recommendation": "GO_WITH_CONDITIONS",
                "rationale": "Technically relevant, but contract/payment assumptions still require manual review.",
                "next_actions": [
                    "Confirm contract payment terms.",
                    "Validate acceptance package and staged delivery assumptions.",
                ],
            }
        raise ValidationError(f"Unsupported stub analysis section '{section}'")


class _TenderOperatorStubProvider:
    def __init__(self, invalid: bool = False) -> None:
        self.invalid = invalid

    def generate(self, section: str, context: dict[str, Any]) -> dict[str, Any]:
        documents = context.get("documents", {})
        notice_text = str(documents.get("notice_text", ""))
        title = notice_text.splitlines()[0].replace("#", "").strip() if notice_text else "Unknown tender"
        validated_sections = context.get("_validated_sections", {})

        if self.invalid and section == "bid_decision":
            return {"preliminary_recommendation": "AUTO_SUBMIT"}

        if section == "requirements":
            return {
                "tender_summary": f"Tender notice: {notice_text[:150]}..." if notice_text else "Tender summary unavailable.",
                "technical_requirements": [
                    "Compliance with specified technical standards required",
                    "Equipment or services must match stated specifications",
                    "Acceptance testing per contract terms",
                    "Warranty and post-delivery support required",
                ],
                "qualification_requirements": [
                    "Valid business registration in relevant jurisdiction",
                    "Relevant industry certifications or SRO approvals",
                    "Prior experience in similar contracts",
                    "Financial stability evidence where required",
                ],
                "document_requirements": [
                    "Company registration certificate",
                    "Tax clearance certificate",
                    "Technical proposal with specifications",
                    "Financial guarantee or contract security",
                    "Declaration of conformity",
                ],
                "evaluation_criteria": [
                    "Price",
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
        if section == "supplier_questions":
            return {
                "supplier_questions": [
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
                        "question": "Do you have the required certificates and declarations of conformity?",
                        "category": "certificates",
                    },
                    {
                        "question": "What warranty do you provide?",
                        "category": "warranty",
                    },
                    {
                        "question": "What are your payment terms? Do you require prepayment?",
                        "category": "payment",
                    },
                ]
            }
        if section == "rfq_draft":
            requirements = validated_sections.get("requirements", {})
            supplier_questions = validated_sections.get("supplier_questions", {}).get("supplier_questions", [])
            return {
                "email_subject": f"RFQ / TKP request: {title}",
                "intro": "Please review the tender scope below and confirm whether you can support this request.",
                "requirements_summary": requirements.get("technical_requirements", [])[:5] or [
                    "Review the attached specification and confirm exact compliance."
                ],
                "supplier_questions": [item["question"] for item in supplier_questions[:8]] or [
                    "Please confirm exact spec match, price, delivery timeline, certificates, and warranty."
                ],
                "requested_response_items": [
                    "Commercial offer / TKP",
                    "Delivery timeline",
                    "Certificates and declarations",
                    "Warranty terms",
                    "Payment terms",
                ],
                "commercial_terms": [
                    "Provide pricing with VAT and without VAT",
                    "State offer validity period",
                    "State whether logistics and installation are included",
                ],
                "closing_note": "This request remains subject to internal operator review and manual follow-up.",
            }
        if section == "contract_risk_memo":
            return {
                "contract_risks": [
                    {
                        "clause": "Penalties for delay",
                        "description": "Standard penalty exposure should be checked against realistic supplier lead times.",
                        "classification": "market_standard_harsh_term",
                        "impact": "Manageable with timeline buffer and supplier confirmation.",
                        "mitigation": "Validate supplier readiness and retain schedule contingency.",
                        "operator_decision_required": False,
                    },
                    {
                        "clause": "Contract security requirement",
                        "description": "Security requirement may lock working capital and reduce margin.",
                        "classification": "commercially_material_risk",
                        "impact": "Commercial pricing may need adjustment.",
                        "mitigation": "Price in guarantee cost and confirm financing capacity.",
                        "operator_decision_required": True,
                    },
                    {
                        "clause": "Required license or SRO",
                        "description": "Missing mandatory approvals may block participation entirely.",
                        "classification": "deal_breaker_candidate",
                        "impact": "Bid may be impossible without required approvals.",
                        "mitigation": "Verify capability and accepted equivalence before proceeding.",
                        "operator_decision_required": True,
                    },
                ]
            }
        if section == "quote_normalization":
            tkp_inputs = context.get("tkp_inputs", [])
            quotes: list[dict[str, Any]] = []
            for item in tkp_inputs:
                quotes.append(
                    {
                        "supplier_label": item.get("supplier_label", "unknown_supplier"),
                        "supplier_id": None,
                        "source_file": item.get("source_file", "unknown"),
                        "normalization_status": "needs_review",
                        "quote_date": None,
                        "valid_until": None,
                        "currency_code": "RUB",
                        "vat_included": None,
                        "vat_rate": None,
                        "total_amount": None,
                        "total_amount_without_vat": None,
                        "delivery_cost": None,
                        "delivery_time_days": None,
                        "payment_terms": None,
                        "warranty_months": None,
                        "availability": None,
                        "includes_delivery": None,
                        "includes_installation": None,
                        "certificates_available": None,
                        "contact_email": None,
                        "contact_phone": None,
                        "line_items": [],
                        "extraction_confidence": 0.2,
                        "fields_needing_review": ["total_amount", "delivery_time_days", "payment_terms", "line_items", "supplier_id"],
                        "warnings": ["stub_placeholder"],
                        "parser_mode": "llm",
                        "human_review_required": True,
                    }
                )
            if not quotes:
                quotes.append(
                    {
                        "supplier_label": "unknown_supplier",
                        "supplier_id": None,
                        "source_file": "unknown",
                        "normalization_status": "needs_review",
                        "quote_date": None,
                        "valid_until": None,
                        "currency_code": "RUB",
                        "vat_included": None,
                        "vat_rate": None,
                        "total_amount": None,
                        "total_amount_without_vat": None,
                        "delivery_cost": None,
                        "delivery_time_days": None,
                        "payment_terms": None,
                        "warranty_months": None,
                        "availability": None,
                        "includes_delivery": None,
                        "includes_installation": None,
                        "certificates_available": None,
                        "contact_email": None,
                        "contact_phone": None,
                        "line_items": [],
                        "extraction_confidence": 0.0,
                        "fields_needing_review": ["source_file", "line_items", "supplier_id"],
                        "warnings": ["no_tkp_inputs"],
                        "parser_mode": "llm",
                        "human_review_required": True,
                    }
                )
            return {"quotes": quotes}
        if section == "bid_decision":
            risks = validated_sections.get("contract_risk_memo", {}).get("contract_risks", [])
            deal_breakers = [
                risk for risk in risks if risk.get("classification") == "deal_breaker_candidate"
            ]
            material_risks = [
                risk for risk in risks if risk.get("classification") == "commercially_material_risk"
            ]
            recommendation = "NEEDS_REVIEW" if deal_breakers else "GO_WITH_CONDITIONS" if material_risks else "GO"
            return {
                "preliminary_recommendation": recommendation,
                "rationale": "Preliminary recommendation based on normalized quote context and calibrated contract risks.",
                "next_actions": [
                    "Validate quote assumptions and certificates manually.",
                    "Review contract risk items before any submission decision.",
                ],
                "human_review_required": True,
            }
        raise ValidationError(f"Unsupported tender-operator stub section '{section}'")


def _json_request(request: Request, *, attempts: int, timeout_seconds: int) -> dict[str, Any]:
    last_error: Exception | None = None
    for _attempt in range(max(attempts, 1)):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
    raise ValidationError(f"LLM provider call failed: {last_error}")


def _extract_message_content(payload: dict[str, Any]) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValidationError(f"Provider response does not include message content: {exc}") from exc

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
                elif isinstance(item.get("content"), str):
                    text_parts.append(item["content"])
        if text_parts:
            return "\n".join(text_parts)

    raise ValidationError("Provider did not return string content")


def _extract_json_object(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        return _extract_json_object(fenced.group(1))

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        snippet = text[start : end + 1]
        data = json.loads(snippet)
        if isinstance(data, dict):
            return data

    raise ValidationError("Provider response is not valid JSON object text")


def _count_string_chars(value: Any) -> int:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, dict):
        return sum(_count_string_chars(item) for item in value.values())
    if isinstance(value, list):
        return sum(_count_string_chars(item) for item in value)
    return 0


def _sanitize_text(text: str) -> tuple[str, bool]:
    sanitized = text
    sanitized = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", sanitized)
    sanitized = re.sub(r"(?:\+?\d[\d()\-\s]{7,}\d)", "[REDACTED_PHONE]", sanitized)
    sanitized = re.sub(r"\b\d{10,}\b", "[REDACTED_NUMBER]", sanitized)
    redaction_applied = sanitized != text
    return sanitized, redaction_applied


def _sanitize_value(value: Any) -> tuple[Any, bool]:
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, dict):
        changed = False
        result: dict[str, Any] = {}
        for key, item in value.items():
            sanitized_item, item_changed = _sanitize_value(item)
            result[key] = sanitized_item
            changed = changed or item_changed
        return result, changed
    if isinstance(value, list):
        changed = False
        result_list: list[Any] = []
        for item in value:
            sanitized_item, item_changed = _sanitize_value(item)
            result_list.append(sanitized_item)
            changed = changed or item_changed
        return result_list, changed
    return value, False


def _prepare_context_for_provider(context: dict[str, Any], *, settings: Settings, provider_mode: str) -> _PreparedContext:
    input_chars_before = _count_string_chars(context)
    if provider_mode != "llm" or settings.llm_allow_raw_partner_data:
        return _PreparedContext(
            context=deepcopy(context),
            redaction_applied=False,
            input_chars_before=input_chars_before,
            input_chars_after=input_chars_before,
        )

    sanitized_context, redaction_applied = _sanitize_value(deepcopy(context))
    input_chars_after = _count_string_chars(sanitized_context)
    return _PreparedContext(
        context=sanitized_context,
        redaction_applied=redaction_applied,
        input_chars_before=input_chars_before,
        input_chars_after=input_chars_after,
    )


class _BaseJSONProvider:
    provider_name: str = "unknown"

    def generate(self, section: str, context: dict[str, Any], prompt_record: PromptSchemaRecord) -> dict[str, Any]:
        raise NotImplementedError


class _OpenAICompatibleJSONProvider(_BaseJSONProvider):
    def __init__(
        self,
        *,
        settings: Settings,
        base_url: str,
        api_key: str,
        auth_scheme: str = "Bearer",
        provider_label: str = "OpenAI-compatible",
    ) -> None:
        self.settings = settings
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.auth_scheme = auth_scheme
        self.provider_label = provider_label
        self.provider_name = "openai_compatible"

    def generate(self, section: str, context: dict[str, Any], prompt_record: PromptSchemaRecord) -> dict[str, Any]:
        model = self.settings.llm_model
        if not model:
            raise ValidationError("AI_CORP_LLM_MODEL is required for LLM provider mode")

        prompt_template = prompt_record.asset_payload_json.get("template", "")
        body = {
            "model": model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a controlled internal procurement analysis assistant. "
                        "Return valid JSON only. Match the supplied output schema exactly, including array/object/scalar types. "
                        "Do not coerce JSON arrays into formatted strings. "
                        "Do not suggest autonomous external actions."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": section,
                            "prompt_template": prompt_template,
                            "output_schema": prompt_record.asset_payload_json.get("output_schema_json", {}),
                            "context": context,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        request = Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"{self.auth_scheme} {self.api_key}",
            },
            method="POST",
        )
        payload = _json_request(
            request,
            attempts=self.settings.llm_max_retries,
            timeout_seconds=self.settings.llm_timeout_seconds,
        )
        return _extract_json_object(_extract_message_content(payload))


class _YandexJSONProvider(_OpenAICompatibleJSONProvider):
    def __init__(self, settings: Settings) -> None:
        if settings.yandex_api_key:
            api_key = settings.yandex_api_key
            auth_scheme = "Api-Key"
        elif settings.yandex_iam_token:
            api_key = settings.yandex_iam_token
            auth_scheme = "Bearer"
        else:
            raise ValidationError(
                "Yandex AI Studio provider requires AI_CORP_YANDEX_API_KEY or AI_CORP_YANDEX_IAM_TOKEN"
            )
        super().__init__(
            settings=settings,
            base_url=settings.yandex_base_url,
            api_key=api_key,
            auth_scheme=auth_scheme,
            provider_label="Yandex AI Studio",
        )
        self.provider_name = "yandex"


class _CloudRuJSONProvider(_OpenAICompatibleJSONProvider):
    def __init__(self, settings: Settings) -> None:
        if not settings.cloudru_api_key:
            raise ValidationError("Cloud.ru provider requires AI_CORP_CLOUDRU_API_KEY")
        super().__init__(
            settings=settings,
            base_url=settings.cloudru_base_url,
            api_key=settings.cloudru_api_key,
            provider_label="Cloud.ru OpenAI-compatible",
        )
        self.provider_name = "cloudru"


class _GigaChatJSONProvider(_BaseJSONProvider):
    def __init__(self, settings: Settings) -> None:
        if not settings.gigachat_auth_key:
            raise ValidationError("GigaChat provider requires AI_CORP_GIGACHAT_AUTH_KEY")
        self.settings = settings
        self._access_token: str | None = None
        self._delegate: _OpenAICompatibleJSONProvider | None = None
        self.provider_name = "gigachat"

    def _ensure_delegate(self) -> _OpenAICompatibleJSONProvider:
        if self._delegate is not None and self._access_token:
            return self._delegate

        request = Request(
            url=self.settings.gigachat_oauth_url,
            data=urlencode({"scope": self.settings.gigachat_scope}).encode("utf-8"),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "RqUID": str(uuid.uuid4()),
                "Authorization": f"Basic {self.settings.gigachat_auth_key}",
            },
            method="POST",
        )
        payload = _json_request(
            request,
            attempts=self.settings.llm_max_retries,
            timeout_seconds=self.settings.llm_timeout_seconds,
        )
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ValidationError("GigaChat OAuth response did not return access_token")

        self._access_token = access_token
        self._delegate = _OpenAICompatibleJSONProvider(
            settings=self.settings,
            base_url=self.settings.gigachat_base_url,
            api_key=access_token,
            auth_scheme="Bearer",
            provider_label="GigaChat",
        )
        return self._delegate

    def generate(self, section: str, context: dict[str, Any], prompt_record: PromptSchemaRecord) -> dict[str, Any]:
        return self._ensure_delegate().generate(section, context, prompt_record)


def _canonical_provider_name(provider_name: str) -> str:
    normalized = provider_name.strip().lower()
    if normalized in {"openai", "openai_compatible", "openai-compatible"}:
        return "openai_compatible"
    if normalized in {"yandex", "yandex_ai_studio"}:
        return "yandex"
    if normalized in {"alice", "alice_ai"}:
        return "alice"
    if normalized in {"gigachat", "sber", "sber_gigachat"}:
        return "gigachat"
    if normalized in {"cloudru", "cloud.ru", "cloud_ru"}:
        return "cloudru"
    if normalized == "stub":
        return "stub"
    return normalized


def _build_provider_from_settings(settings: Settings, provider_name_override: str | None = None) -> _BaseJSONProvider:
    provider_name = _canonical_provider_name(provider_name_override or settings.llm_provider)
    if provider_name == "openai_compatible":
        if not settings.openai_api_key:
            raise ValidationError("OpenAI-compatible provider requires AI_CORP_OPENAI_API_KEY")
        return _OpenAICompatibleJSONProvider(
            settings=settings,
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
        )
    if provider_name in {"yandex", "alice"}:
        provider = _YandexJSONProvider(settings)
        provider.provider_name = provider_name
        return provider
    if provider_name == "gigachat":
        return _GigaChatJSONProvider(settings)
    if provider_name == "cloudru":
        return _CloudRuJSONProvider(settings)
    if provider_name == "stub":
        raise ValidationError("AI_CORP_LLM_PROVIDER=stub cannot be used with provider_mode='llm'")
    raise ValidationError(f"Unsupported AI_CORP_LLM_PROVIDER '{settings.llm_provider}'")


def _validate_output(bundle: _PromptBundle, section: str, raw_output: dict[str, Any]) -> dict[str, Any]:
    model = bundle.output_models[section]
    validated = model.model_validate(raw_output)
    return validated.model_dump()


def _trace_section(
    session: Session,
    *,
    bundle: _PromptBundle,
    agent: AgentRegistryRecord,
    prompt_record: PromptSchemaRecord,
    context: dict[str, Any],
    section: str,
    trace_output_summary: str,
    validation_status: RuntimeTraceValidationStatus,
    review_status: HumanReviewStatus,
    disposition: RuntimeTraceDisposition,
    redaction_applied: bool,
    input_chars_before: int,
    input_chars_after: int,
) -> str:
    trace = create_runtime_control_trace(
        session,
        CreateRuntimeControlTraceRequest(
            runtime_slice=bundle.runtime_slice,
            source_entity=bundle.source_entity,
            actor_type=RuntimeTraceActorType.AGENT_PROFILE,
            actor_ref=agent.agent_key,
            action_type=RuntimeTraceActionType.GENERATE_DRAFT,
            target_module=bundle.target_module,
            target_record_id=context["deal_id"],
            prompt_schema_ref=prompt_record.prompt_schema_id,
            agent_profile_ref=agent.agent_registry_id,
            input_summary=(
                f"Controlled analysis for section '{section}'"
                f" | redaction_applied={str(redaction_applied).lower()}"
                f" | input_chars_before={input_chars_before}"
                f" | input_chars_after={input_chars_after}"
            ),
            output_summary=trace_output_summary[:500],
            validation_status=validation_status,
            human_review_status=review_status,
            final_disposition=disposition,
        ),
    )
    return trace.runtime_trace_id


def _run_controlled_sections(
    session: Session,
    *,
    bundle: _PromptBundle,
    provider_mode: str,
    context: dict[str, Any],
    stub_provider: Any,
    active_sections: set[str] | None = None,
    provider_name_override: str | None = None,
) -> ControlledLLMAnalysisResult:
    agent, prompt_records = _ensure_metadata(session, bundle)
    settings = get_settings()

    if provider_mode == "stub":
        provider: Any = stub_provider
        analysis_mode = bundle.analysis_mode_stub
        resolved_provider = "stub"
    elif provider_mode == "llm":
        provider = _build_provider_from_settings(settings, provider_name_override)
        analysis_mode = bundle.analysis_mode_provider
        resolved_provider = provider.provider_name
    else:
        raise ValidationError(f"Unsupported provider_mode '{provider_mode}'")

    sections: dict[str, dict[str, Any]] = {}
    trace_ids: list[str] = []
    overall_review_status = HumanReviewStatus.NEEDS_HUMAN_REVIEW.value
    prepared_context = _prepare_context_for_provider(context, settings=settings, provider_mode=provider_mode)
    working_context = prepared_context.context
    working_context.setdefault("_validated_sections", {})

    for section, prompt_record in prompt_records.items():
        if active_sections is not None and section not in active_sections:
            continue
        try:
            if provider_mode == "stub":
                raw_output = provider.generate(section, working_context)
            else:
                raw_output = provider.generate(section, working_context, prompt_record)
            validated_output = _validate_output(bundle, section, raw_output)
            validation_status = RuntimeTraceValidationStatus.PASSED
            review_status = HumanReviewStatus.NEEDS_HUMAN_REVIEW
            disposition = RuntimeTraceDisposition.NEEDS_HUMAN_REVIEW
            working_context["_validated_sections"][section] = validated_output
        except Exception as exc:
            raw_output = {"error": str(exc)}
            validated_output = None
            validation_status = RuntimeTraceValidationStatus.FAILED
            review_status = HumanReviewStatus.VALIDATION_FAILED
            disposition = RuntimeTraceDisposition.NEEDS_HUMAN_REVIEW

        stored_raw_output = raw_output
        if provider_mode == "llm" and not settings.llm_store_raw_response:
            stored_raw_output = None

        if stored_raw_output is None:
            trace_output_summary = json.dumps(
                {
                    "raw_response_stored": False,
                    "validation_status": validation_status.value,
                    "review_status": review_status.value,
                },
                ensure_ascii=False,
            )
        else:
            trace_output_summary = json.dumps(stored_raw_output, ensure_ascii=False)

        trace_id = _trace_section(
            session,
            bundle=bundle,
            agent=agent,
            prompt_record=prompt_record,
            context=context,
            section=section,
            trace_output_summary=trace_output_summary,
            validation_status=validation_status,
            review_status=review_status,
            disposition=disposition,
            redaction_applied=prepared_context.redaction_applied,
            input_chars_before=prepared_context.input_chars_before,
            input_chars_after=prepared_context.input_chars_after,
        )
        trace_ids.append(trace_id)
        sections[section] = {
            "prompt_schema_id": prompt_record.prompt_schema_id,
            "prompt_version": prompt_record.version_tag,
            "output_schema_ref": prompt_record.output_schema_ref,
            "validation_status": validation_status.value,
            "review_status": review_status.value,
            "requires_human_review": True,
            "trace_id": trace_id,
            "raw_output": stored_raw_output,
            "validated_output": validated_output,
            "input_redaction": {
                "redaction_applied": prepared_context.redaction_applied,
                "input_chars_before": prepared_context.input_chars_before,
                "input_chars_after": prepared_context.input_chars_after,
            },
        }

    return ControlledLLMAnalysisResult(
        analysis_mode=analysis_mode,
        resolved_provider=resolved_provider,
        overall_review_status=overall_review_status,
        sections=sections,
        trace_ids=trace_ids,
    )


def run_controlled_llm_prebid_analysis(
    session: Session,
    *,
    provider_mode: str,
    context: dict[str, Any],
    simulate_invalid_output: bool = False,
) -> ControlledLLMAnalysisResult:
    return _run_controlled_sections(
        session,
        bundle=COMMERCIAL_PREBID_BUNDLE,
        provider_mode=provider_mode,
        context=context,
        stub_provider=_CommercialPreBidStubProvider(invalid=simulate_invalid_output),
        provider_name_override=None,
    )


def run_controlled_tender_operator_workflow(
    session: Session,
    *,
    provider_mode: str,
    context: dict[str, Any],
    include_quote_normalization: bool,
    include_bid_decision: bool,
    simulate_invalid_output: bool = False,
    provider_name_override: str | None = None,
) -> ControlledTenderOperatorWorkflowResult:
    active_sections = {"requirements", "supplier_questions", "rfq_draft", "contract_risk_memo"}
    if include_quote_normalization:
        active_sections.add("quote_normalization")
    if include_bid_decision:
        active_sections.add("bid_decision")

    analysis = _run_controlled_sections(
        session,
        bundle=TENDER_OPERATOR_BUNDLE,
        provider_mode=provider_mode,
        context=context,
        stub_provider=_TenderOperatorStubProvider(invalid=simulate_invalid_output),
        active_sections=active_sections,
        provider_name_override=provider_name_override,
    )

    requirements = analysis.sections["requirements"]["validated_output"] or {}
    supplier_questions_payload = analysis.sections["supplier_questions"]["validated_output"] or {"supplier_questions": []}
    rfq_draft = analysis.sections["rfq_draft"]["validated_output"] or {}
    contract_risk_payload = analysis.sections["contract_risk_memo"]["validated_output"] or {"contract_risks": []}

    quote_normalization = None
    if include_quote_normalization and "quote_normalization" in analysis.sections:
        quote_normalization = analysis.sections["quote_normalization"]["validated_output"]
    bid_decision = None
    if include_bid_decision and "bid_decision" in analysis.sections:
        bid_decision = analysis.sections["bid_decision"]["validated_output"]

    return ControlledTenderOperatorWorkflowResult(
        analysis_mode=analysis.analysis_mode,
        resolved_provider=analysis.resolved_provider,
        overall_review_status=analysis.overall_review_status,
        requirements=requirements,
        supplier_questions=supplier_questions_payload.get("supplier_questions", []),
        rfq_draft=rfq_draft,
        contract_risks=contract_risk_payload.get("contract_risks", []),
        quote_normalization=quote_normalization,
        bid_decision=bid_decision,
        sections=analysis.sections,
        trace_ids=analysis.trace_ids,
    )
