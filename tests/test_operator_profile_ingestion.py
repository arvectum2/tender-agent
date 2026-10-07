from pathlib import Path

from scripts.run_tender_operator_pilot import (
    _bind_operator_supplier_profile,
    _read_operator_profile,
    _run_stub_economics,
)
from src.modules.tender_operator_agent_demo.decision_core import build_decision_core
from src.modules.tender_operator_agent_demo.supplier_profile import (
    SupplierProfile,
    parse_operator_profile_markdown,
)


FIXTURE_DIR = Path("tests/fixtures/local_pilot_runs/tender_operator_001")


def test_fixture_operator_profile_is_typed_and_structured_for_decision_core() -> None:
    parsed = _read_operator_profile(FIXTURE_DIR)
    profile = parsed["supplier_profile"]

    assert profile["supplier_id"] == "tender_operator_001"
    assert profile["name"] == "Test Tender Operator One"
    assert profile["criteria"]["categories"] == [
        "Industrial control equipment",
        "Electrical distribution equipment",
        "Automation systems",
    ]
    assert profile["criteria"]["excluded_categories"] == [
        "Medical equipment",
        "Pharmaceutical products",
    ]
    assert profile["criteria"]["regions"] == ["Russian Federation (all regions)"]
    assert profile["criteria"]["price_min"] == 1_000_000
    assert profile["criteria"]["price_max"] == 50_000_000
    assert profile["commercial"]["vat_mode"] == "with_vat"
    assert profile["commercial"]["target_margin_percent"] == 15
    assert profile["commercial"]["max_payment_delay_days"] == 45
    assert profile["commercial"]["max_contract_security_percent"] == 30
    assert profile["commercial"]["max_prepayment_gap"] is None
    assert profile["commercial"]["max_cash_gap"] == 5_000_000
    assert profile["qualification"]["licenses"] == []
    assert profile["qualification"]["sro_approvals"] == [
        "SRO approvals in construction/installation"
    ]
    assert profile["qualification"]["experience_years"] is None
    assert profile["risk_preferences"]["risky_categories"] == []
    assert profile["risk_preferences"]["forbidden_categories"] == []

    validated = SupplierProfile(**profile)
    assert validated.criteria.price_min == 1_000_000


def test_full_template_contract_maps_all_admitted_business_constraints() -> None:
    text = """
# Tender Operator Profile

## General Information
- **Operator Name**: Alpha Tender Desk
- **Company Name**: Alpha Trading LLC
- **Company Type**: tender-operator
- **Industry / Sectors**: electrical; automation
- **Tender Regions**: Moscow; Tula Region
- **Company Size** (approx. employees): 42

## Working Categories
- Low-voltage equipment
- Automation equipment

## Excluded Categories
- Pharmaceuticals
- Food

## Target NMCK Range
- **Minimum**: 500 000 RUB
- **Maximum**: 12 500 000 RUB

## VAT Mode
- [ ] Works with VAT
- [ ] Works without VAT (simplified taxation)
- [x] Both, depending on customer/region

## Financial Constraints
- **Target margin** (%): 17.5
- **Acceptable payment delay** (days): 60
- **Acceptable contract security** (% of contract value): 25
- **Maximum acceptable prepayment gap** (own funds available): 2 500 000 RUB
- **Maximum cash gap before customer payment**: 4 000 000 RUB

## Risk Preferences
- **Risky categories** (high-risk but may proceed with caution): custom fabrication; imported controls
- **Forbidden categories** (will not participate under any circumstances): medicines; food

## Licensing / SRO
- **Licenses held**: License A; License B
- **SRO approvals held**: SRO electrical; SRO installation
- **Experience required** (years in similar projects): 3

## Notes
Synthetic test contract. No fixed SKU, catalog or known supplier price.
"""
    profile = parse_operator_profile_markdown(text, supplier_id="alpha")
    assert profile is not None

    data = profile.model_dump(mode="json")
    assert data["name"] == "Alpha Trading LLC"
    assert data["short_name"] == "Alpha Tender Desk"
    assert data["criteria"]["categories"] == [
        "Low-voltage equipment",
        "Automation equipment",
    ]
    assert data["criteria"]["excluded_categories"] == ["Pharmaceuticals", "Food"]
    assert data["criteria"]["regions"] == ["Moscow", "Tula Region"]
    assert data["criteria"]["price_min"] == 500_000
    assert data["criteria"]["price_max"] == 12_500_000
    assert data["commercial"] == {
        "vat_mode": "both",
        "target_margin_percent": 17.5,
        "max_payment_delay_days": 60,
        "max_contract_security_percent": 25.0,
        "max_prepayment_gap": 2_500_000.0,
        "max_cash_gap": 4_000_000.0,
    }
    assert data["qualification"] == {
        "licenses": ["License A", "License B"],
        "sro_approvals": ["SRO electrical", "SRO installation"],
        "experience_years": 3.0,
    }
    assert data["risk_preferences"]["tolerance"] is None
    assert data["risk_preferences"]["require_certificates"] is None
    assert data["risk_preferences"]["risky_categories"] == [
        "custom fabrication",
        "imported controls",
    ]
    assert data["risk_preferences"]["forbidden_categories"] == ["medicines", "food"]
    assert data["metadata"]["employee_count"] == 42


def test_missing_malformed_and_contradictory_values_fail_closed(tmp_path: Path) -> None:
    (tmp_path / "operator_profile.md").write_text(
        """
# Operator Profile

## Target NMCK Range
- Minimum: 20 000 000 RUB
- Maximum: 10 000 000 RUB

## VAT Mode
- [x] Works with VAT
- [x] Works without VAT

## Financial Constraints
- Target margin: 120%
- Acceptable payment delay: 45.5 days
- Acceptable contract security: -1%
- Maximum acceptable prepayment gap: unknown
- Maximum cash gap: -500 RUB

## Licensing / SRO
- Experience required: n/a
""",
        encoding="utf-8",
    )

    profile = _read_operator_profile(tmp_path)["supplier_profile"]
    assert profile["criteria"]["price_min"] is None
    assert profile["criteria"]["price_max"] is None
    assert profile["commercial"]["vat_mode"] is None
    assert profile["commercial"]["target_margin_percent"] is None
    assert profile["commercial"]["max_payment_delay_days"] is None
    assert profile["commercial"]["max_contract_security_percent"] is None
    assert profile["commercial"]["max_prepayment_gap"] is None
    assert profile["commercial"]["max_cash_gap"] is None
    assert profile["qualification"]["experience_years"] is None


def test_analysis_context_binding_preserves_context_and_decision_core_safety() -> None:
    operator_profile = _read_operator_profile(FIXTURE_DIR)
    requirements = {"analysis_context": {"document_coverage": "complete"}}

    _bind_operator_supplier_profile(requirements, operator_profile)

    analysis_context = requirements["analysis_context"]
    assert analysis_context["document_coverage"] == "complete"
    profile = analysis_context["supplier_profile"]
    assert profile["criteria"]["price_min"] == 1_000_000

    model = {
        "nmck": 5_000_000,
        "field_evidence": {"nmck": ["eis_notice:nmck"]},
        "contract_draft_status": "missing",
    }
    decision = build_decision_core(model, supplier_profile=profile)
    readiness = {row["code"]: row for row in decision["readiness"]}
    assert readiness["SUPPLIER_PROFILE"]["status"] == "SATISFIED"
    assert readiness["SUPPLIER_PRICE_RANGE"]["status"] == "SATISFIED"
    assert decision["safety"] == {
        "bid_submission_allowed": False,
        "rfq_or_invitation_allowed": False,
        "winner_selection_allowed": False,
        "signing_allowed": False,
        "external_commercial_effect_allowed": False,
    }


def test_structured_margin_is_reused_by_stub_economics() -> None:
    operator_profile = _read_operator_profile(FIXTURE_DIR)
    economics = _run_stub_economics({"suppliers": []}, operator_profile)

    assert economics["target_margin"] == 15.0
    serialized = str(operator_profile["supplier_profile"]).lower()
    assert "sku" not in serialized
    assert "catalog" not in serialized
    assert "known_price" not in serialized
