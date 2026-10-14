from pydantic import BaseModel, Field

from src.modules.quote_repository.tkp_normalization_schemas import NormalizedTKPQuoteBatch


class LLMTenderSummaryDraft(BaseModel):
    tender_summary: str = Field(min_length=1)
    why_relevant: str = Field(min_length=1)


class LLMTechnicalRequirementsDraft(BaseModel):
    technical_requirements: list[str] = Field(min_length=1)


class LLMParticipantRequirementsDraft(BaseModel):
    participant_requirements: list[str] = Field(min_length=1)


class LLMContractRisksDraft(BaseModel):
    contract_risks: list[str] = Field(min_length=1)


class LLMBidDecisionDraft(BaseModel):
    recommendation: str = Field(pattern="^(GO|GO_WITH_CONDITIONS|NEEDS_REVIEW|NO_GO)$")
    rationale: str = Field(min_length=1)
    next_actions: list[str] = Field(min_length=1)


class LLMTenderOperatorRequirementsDraft(BaseModel):
    tender_summary: str = Field(min_length=1)
    # Unknown/absent requirements are valid empty sets. Forcing min_length=1
    # makes the model fabricate bid criteria and qualifications from TЗ prose.
    technical_requirements: list[str] = Field()
    qualification_requirements: list[str] = Field()
    document_requirements: list[str] = Field()
    evaluation_criteria: list[str] = Field()
    procurement_categories: list[str] = Field()


class LLMSupplierQuestionDraft(BaseModel):
    question: str = Field(min_length=1)
    category: str = Field(min_length=1)


class LLMSupplierQuestionsDraft(BaseModel):
    supplier_questions: list[LLMSupplierQuestionDraft] = Field(min_length=1)


class LLMTenderOperatorRFQDraft(BaseModel):
    email_subject: str = Field(min_length=1)
    intro: str = Field(min_length=1)
    requirements_summary: list[str] = Field(min_length=1)
    supplier_questions: list[str] = Field(min_length=1)
    requested_response_items: list[str] = Field(min_length=1)
    commercial_terms: list[str] = Field(min_length=1)
    closing_note: str = Field(min_length=1)


class LLMContractRiskItemDraft(BaseModel):
    clause: str = Field(min_length=1)
    description: str = Field(min_length=1)
    classification: str = Field(
        pattern="^(market_standard_harsh_term|commercially_material_risk|deal_breaker_candidate)$"
    )
    impact: str = Field(min_length=1)
    mitigation: str = Field(min_length=1)
    operator_decision_required: bool


class LLMTenderOperatorContractRiskMemoDraft(BaseModel):
    # The model must be free to abstain when it finds no verified risk clause.
    contract_risks: list[LLMContractRiskItemDraft] = Field()


class LLMQuoteNormalizationDraft(NormalizedTKPQuoteBatch):
    pass


class LLMTenderOperatorBidDecisionDraft(BaseModel):
    preliminary_recommendation: str = Field(pattern="^(GO|GO_WITH_CONDITIONS|NEEDS_REVIEW|NO_GO)$")
    rationale: str = Field(min_length=1)
    next_actions: list[str] = Field(min_length=1)
    human_review_required: bool = True
