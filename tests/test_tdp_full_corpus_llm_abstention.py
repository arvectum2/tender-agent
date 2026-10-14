"""Tender operator prompts and schemas must permit honest abstention."""
from src.modules.controlled_llm_prebid.schemas import (
    LLMTenderOperatorContractRiskMemoDraft,
    LLMTenderOperatorRequirementsDraft,
)
from src.modules.controlled_llm_prebid.service import TENDER_OPERATOR_PROMPT_SPECS


def test_no_source_defined_bid_scoring_does_not_force_fake_criteria():
    raw = {
        "tender_summary": "Историческое извещение, требуется проверка ЕИС",
        "technical_requirements": ["Сайт должен поддерживать доступность."],
        "qualification_requirements": [],
        "document_requirements": [],
        "evaluation_criteria": [],
        "procurement_categories": [],
    }
    assert LLMTenderOperatorRequirementsDraft.model_validate(raw).evaluation_criteria == []
    schema = LLMTenderOperatorRequirementsDraft.model_json_schema()
    assert schema["properties"]["evaluation_criteria"].get("minItems", 0) == 0
    assert schema["properties"]["qualification_requirements"].get("minItems", 0) == 0
    assert "evaluation_criteria" in schema["required"]


def test_no_supported_contract_risk_can_abstain_instead_of_fabricating():
    assert LLMTenderOperatorContractRiskMemoDraft.model_validate(
        {"contract_risks": []}
    ).contract_risks == []
    schema = LLMTenderOperatorContractRiskMemoDraft.model_json_schema()
    assert schema["properties"]["contract_risks"].get("minItems", 0) == 0


def test_versioned_prompt_discourages_false_official_scoring_and_bidder_status():
    prompt = TENDER_OPERATOR_PROMPT_SPECS["requirements"]
    text = prompt.template
    assert prompt.asset_key.endswith("-source-v2")
    assert "only" in text.lower()
    assert "evaluation_criteria" in text
    assert "[]" in text
    assert "СМП/СОНКО" in text


def test_contract_risk_prompt_requires_clause_exceptions_and_allows_abstention():
    prompt = TENDER_OPERATOR_PROMPT_SPECS["contract_risk_memo"]
    assert prompt.asset_key.endswith("-source-v2")
    assert "exact original paragraph" in prompt.template
    assert "price is fixed" in prompt.template
    assert "Use []" in prompt.template
