from __future__ import annotations

from copy import deepcopy

from src.modules.tender_operator_agent_demo.decision_core import (
    DECISION_CORE_CONTRACT_VERSION,
    build_decision_core,
)
from src.modules.tender_operator_agent_demo.report_model import (
    build_customer_report_projection,
    build_procurement_report_model,
)


def _profile(*, price_max: float = 2_000_000) -> dict:
    return {
        "supplier_id": "supplier-1",
        "name": "Supplier",
        "criteria": {"price_min": 100_000, "price_max": price_max},
        "risk_preferences": {"tolerance": "medium", "require_certificates": True},
    }


def _grounded_model() -> dict:
    return {
        "procurement_title": "Поставка электротехнического оборудования",
        "application_deadline": "2026-09-30T12:00:00+03:00",
        "deadline_status": "open",
        "nmck": 1_000_000,
        "field_evidence": {
            "procurement_title": "eis_notice:procurement_subject",
            "application_deadline": "eis_notice:application_deadline",
            "nmck": "eis_notice:initial_price",
        },
        "metadata": {
            "degraded_mode": False,
            "document_set_summary": {
                "status": "complete",
                "logical_documents": [
                    {"name": "Извещение.xml", "type": "извещение"},
                    {"name": "Проект контракта.docx", "type": "проект контракта"},
                ],
            },
        },
        "contract_draft_status": "present",
        "contract_draft_documents": ["Проект контракта.docx"],
        "contract_draft_evidence_ids": ["contract:contract-1"],
        "ai_runtime_provenance": {
            "producer": "production_llm_r10_1",
            "validated_result_hash": "validated-result",
        },
        "risks": [],
        "evidence_map": [],
        "contradictions": [],
    }


def test_complete_grounded_case_can_reach_go_without_external_authority() -> None:
    result = build_decision_core(_grounded_model(), supplier_profile=_profile())

    assert result["contract_version"] == DECISION_CORE_CONTRACT_VERSION
    assert result["decision"]["status"] == "GO"
    assert result["facts"]["application_deadline"]["status"] == "KNOWN"
    assert result["facts"]["application_deadline"]["evidence"][0]["excerpt"] == "2026-09-30T12:00:00+03:00"
    assert result["decision"]["external_action_allowed"] is False
    assert result["decision"]["human_control_required"] is True
    assert result["safety"]["bid_submission_allowed"] is False
    assert all(item["status"] == "SATISFIED" for item in result["readiness"])
    assert result["decision"]["evidence"]


def test_grounded_expired_deadline_is_hard_no_go() -> None:
    model = _grounded_model()
    model["deadline_status"] = "expired"

    result = build_decision_core(model, supplier_profile=_profile())

    assert result["decision"]["status"] == "NO_GO"
    assert [item["code"] for item in result["blockers"]] == [
        "APPLICATION_DEADLINE_EXPIRED"
    ]
    assert result["blockers"][0]["evidence"][0]["source_ref"] == (
        "eis_notice:application_deadline"
    )


def test_expired_deadline_without_source_binding_fails_closed_to_review() -> None:
    model = _grounded_model()
    model["deadline_status"] = "expired"
    model["field_evidence"].pop("application_deadline")

    result = build_decision_core(model, supplier_profile=_profile())

    assert result["decision"]["status"] == "NEEDS_REVIEW"
    assert result["facts"]["application_deadline"]["status"] == "UNKNOWN"
    assert not result["blockers"]
    application = next(
        item for item in result["readiness"] if item["code"] == "APPLICATION_WINDOW"
    )
    assert application["status"] == "UNKNOWN"


def test_source_grounded_deal_breaker_candidate_still_requires_human_review() -> None:
    model = _grounded_model()
    model["risks"] = [
        {
            "risk": "Одностороннее условие",
            "classification": "deal_breaker_candidate",
            "operator_decision_required": True,
        }
    ]
    model["evidence_map"] = [
        {
            "evidence_id": "risk:1:locator:1",
            "document": "Проект контракта.docx",
            "row": "раздел 7",
            "short_excerpt": "Одностороннее условие",
        }
    ]

    result = build_decision_core(model, supplier_profile=_profile())

    assert result["decision"]["status"] == "NEEDS_REVIEW"
    assert not result["blockers"]
    risk_review = next(
        item for item in result["readiness"] if item["code"] == "RISK_REVIEW"
    )
    assert risk_review["status"] == "REVIEW"
    assert risk_review["evidence"]


def test_unsupported_risk_never_becomes_a_hard_fact() -> None:
    model = _grounded_model()
    model["risks"] = [
        {
            "risk": "Неподтверждённый критический риск",
            "severity": "critical",
        }
    ]

    result = build_decision_core(model, supplier_profile=_profile())

    assert result["decision"]["status"] == "NEEDS_REVIEW"
    assert not result["blockers"]
    assert any(item["code"] == "RISK_1_EVIDENCE" for item in result["unknowns"])


def test_missing_contract_and_missing_supplier_profile_block_go_not_force_no_go() -> None:
    model = _grounded_model()
    model["contract_draft_status"] = "absent"
    model["contract_draft_documents"] = []
    model["contract_draft_evidence_ids"] = []

    result = build_decision_core(model)

    assert result["decision"]["status"] == "NEEDS_REVIEW"
    assert not result["blockers"]
    states = {item["code"]: item["status"] for item in result["readiness"]}
    assert states["CONTRACT_DRAFT"] == "MISSING"
    assert states["SUPPLIER_PROFILE"] == "MISSING"


def test_supplier_price_outside_profile_requires_review_not_no_go() -> None:
    result = build_decision_core(_grounded_model(), supplier_profile=_profile(price_max=500_000))

    assert result["decision"]["status"] == "NEEDS_REVIEW"
    price = next(
        item for item in result["readiness"] if item["code"] == "SUPPLIER_PRICE_RANGE"
    )
    assert price["status"] == "REVIEW"


def test_contradiction_requires_review() -> None:
    model = _grounded_model()
    model["contradictions"] = [{"field": "quantity", "values": [10, 20]}]

    result = build_decision_core(model, supplier_profile=_profile())

    assert result["decision"]["status"] == "NEEDS_REVIEW"
    assert any("противореч" in text.lower() for text in result["decision"]["rationale"])


def test_customer_projection_removes_internal_evidence_ids_and_source_refs() -> None:
    model = _grounded_model()
    model["deadline_status"] = "expired"
    model["decision_core"] = build_decision_core(model, supplier_profile=_profile())
    model["customer_decision"] = {}
    model["customer_documents"] = []
    model["line_items"] = []
    model["okpd2_codes"] = []
    model["customer_questions"] = []
    model["corpus_limitations"] = []
    model["delivery_place"] = "Москва"

    projection = build_customer_report_projection(model)
    serialized = str(projection["decision_core"])

    assert projection["decision_core"]["decision"]["status"] == "NO_GO"
    assert "eis_notice:application_deadline" not in serialized
    assert "source_ref" not in serialized
    assert "evidence_id" not in serialized
    assert projection["decision_core"]["decision"]["evidence"] == [
        {"document_label": "Извещение о закупке", "location": "application_deadline"}
    ]


def test_canonical_report_builder_attaches_fail_closed_decision_core() -> None:
    metadata = {
        "run_id": "decision-core-test",
        "procurement_id": "0123456789012345678",
        "procurement_title": "Тестовая закупка",
        "files": [],
        "_field_evidence": {
            "procurement_title": "eis_notice:procurement_subject",
            "application_deadline": "eis_notice:application_deadline",
            "nmck": "eis_notice:initial_price",
        },
        "deadline": "30.09.2026 12:00 +03:00",
        "analysis_completed_at": "15.09.2026T12:00:00+00:00",
    }
    outputs = {
        "requirements": {
            "preliminary_analysis": {
                "supply_items": [],
                "item_coverage": {},
                "next_actions": [],
            },
            "analysis_context": {
                "procurement_subject": "Тестовая закупка",
                "nmck": 1_000_000,
                "currency": "RUB",
                "document_coverage": "partial",
                "missing_documents": ["draft_contract"],
                "supplier_profile": deepcopy(_profile()),
            },
        },
        "final_recommendation": {
            "recommendation": "needs_review",
            "rationale": [],
            "manual_checks": [],
        },
        "contract_risks": {"risks": []},
        "economics": {"metrics": [], "warnings": []},
        "supplier_questions": {"questions": []},
        "quotes_comparison": {"highlights": []},
    }

    model = build_procurement_report_model(metadata, outputs)

    assert model["decision_core"]["contract_version"] == DECISION_CORE_CONTRACT_VERSION
    assert model["decision_core"]["decision"]["status"] == "NEEDS_REVIEW"
    assert model["bid_decision"]["status"] == "needs_review"
    assert model["decision_core"]["supplier_profile_bound"] is True
