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
    assert result["procurement_regime"] == "unknown"
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
    assert "Одностороннее условие" in risk_review["summary"]
    assert any("Одностороннее условие" in item for item in result["decision"]["rationale"])


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


def test_needs_review_rationale_names_unresolved_readiness_items() -> None:
    model = _grounded_model()
    result = build_decision_core(model)

    assert result["decision"]["status"] == "NEEDS_REVIEW"
    rationale = " ".join(result["decision"]["rationale"])
    assert "Профиль поставщика:" in rationale


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
        "law": "44-ФЗ",
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
    assert model["decision_core"]["procurement_regime"] == "44fz"
    assert model["procurement_regime"] == "44fz"
    assert model["decision_core"]["decision"]["status"] == "NEEDS_REVIEW"
    assert model["bid_decision"]["status"] == "needs_review"
    assert model["decision_core"]["supplier_profile_bound"] is True


def test_canonical_report_builder_reconciles_legacy_customer_decision() -> None:
    metadata = {
        "run_id": "decision-consistency-test",
        "procurement_id": "0123456789012345678",
        "procurement_title": "Тестовая закупка",
        "files": [
            {"display_name": "Техническое задание.docx", "role_hint": "technical_spec"},
            {"display_name": "Проект контракта.docx", "role_hint": "contract_draft"},
        ],
        "_field_evidence": {
            "procurement_title": "eis_notice:procurement_subject",
            "application_deadline": "eis_notice:application_deadline",
            "nmck": "eis_notice:initial_price",
        },
        "deadline": "2026-09-30T12:00:00+03:00",
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
                "document_coverage": "complete",
                "missing_documents": [],
                "contract_draft_status": "present",
                "contract_draft_documents": ["Проект контракта.docx"],
                "contract_draft_evidence_ids": ["contract:contract-1"],
            },
        },
        "final_recommendation": {
            "recommendation": "participate",
            "rationale": [],
            "manual_checks": [],
        },
        "contract_risks": {"risks": []},
        "economics": {"metrics": [], "warnings": []},
        "supplier_questions": {"questions": []},
        "quotes_comparison": {"highlights": []},
    }

    model = build_procurement_report_model(metadata, outputs)

    assert model["decision_core"]["decision"]["status"] == "NEEDS_REVIEW"
    assert model["customer_decision"]["recommendation"] == "Требуется проверка"
    assert model["customer_decision"]["reasons"] == model["decision_core"]["decision"]["rationale"]
    assert model["customer_decision"]["next_action"] == model["decision_core"]["decision"]["next_action"]

def _grounded_223fz_model() -> dict:
    model = _grounded_model()
    model["procurement_law"] = "223fz"
    return model


def test_223fz_go_capable_candidate_fails_closed_without_regime_rules() -> None:
    result = build_decision_core(_grounded_223fz_model(), supplier_profile=_profile())

    assert result["procurement_regime"] == "223fz"
    assert result["decision"]["status"] == "NEEDS_REVIEW"
    assert not result["blockers"]
    assert result["facts"]["procurement_title"]["status"] == "KNOWN"
    assert result["facts"]["application_deadline"]["status"] == "KNOWN"
    assert result["facts"]["nmck"]["status"] == "KNOWN"
    assert any(item["code"] == "223FZ_APPLICATION_WINDOW_SEMANTICS" for item in result["unknowns"])


def test_223fz_expired_deadline_does_not_inherit_44fz_hard_blocker() -> None:
    model = _grounded_223fz_model()
    model["deadline_status"] = "expired"

    result = build_decision_core(model, supplier_profile=_profile())

    assert result["decision"]["status"] == "NEEDS_REVIEW"
    assert not result["blockers"]
    assert all(item["code"] != "APPLICATION_DEADLINE_EXPIRED" for item in result["blockers"])


def test_223fz_missing_source_binding_keeps_shared_fact_unknown() -> None:
    model = _grounded_223fz_model()
    model["field_evidence"].pop("application_deadline")
    model["field_evidence"].pop("nmck")

    result = build_decision_core(model, supplier_profile=_profile())

    assert result["decision"]["status"] == "NEEDS_REVIEW"
    assert result["facts"]["application_deadline"]["status"] == "UNKNOWN"
    assert result["facts"]["nmck"]["status"] == "UNKNOWN"


def test_223fz_contradiction_remains_regime_neutral_review() -> None:
    model = _grounded_223fz_model()
    model["contradictions"] = [{"field": "quantity", "values": [10, 20]}]

    result = build_decision_core(model, supplier_profile=_profile())

    consistency = next(item for item in result["readiness"] if item["code"] == "SOURCE_CONSISTENCY")
    assert result["decision"]["status"] == "NEEDS_REVIEW"
    assert consistency["status"] == "REVIEW"


def test_223fz_risk_classification_never_inherits_44fz_hard_blocker() -> None:
    model = _grounded_223fz_model()
    model["risks"] = [
        {
            "risk": "Режимно неподтверждённый риск",
            "classification": "hard_blocker",
            "operator_decision_required": False,
        }
    ]
    model["evidence_map"] = [
        {
            "evidence_id": "risk:1:locator:1",
            "document": "Документ закупки",
            "row": "раздел 7",
            "short_excerpt": "Риск",
        }
    ]

    result = build_decision_core(model, supplier_profile=_profile())

    assert result["decision"]["status"] == "NEEDS_REVIEW"
    assert not result["blockers"]
    assert any(item["code"] == "223FZ_RISK_1_SEMANTICS" for item in result["unknowns"])


def test_customer_projection_exposes_normalized_procurement_regime() -> None:
    model = _grounded_223fz_model()
    model["decision_core"] = build_decision_core(model, supplier_profile=_profile())
    model["customer_decision"] = {}
    model["customer_documents"] = []
    model["line_items"] = []
    model["okpd2_codes"] = []
    model["customer_questions"] = []
    model["corpus_limitations"] = []
    model["delivery_place"] = "Москва"

    projection = build_customer_report_projection(model)

    assert projection["procurement_regime"] == "223fz"
    assert projection["decision_core"]["procurement_regime"] == "223fz"


def test_canonical_report_builder_propagates_223fz_metadata_law() -> None:
    metadata = {
        "run_id": "decision-core-223fz-test",
        "procurement_id": "2230000000000000000",
        "procurement_title": "Тестовая закупка 223-ФЗ",
        "procurement_law": "223-FZ",
        "files": [],
        "_field_evidence": {
            "procurement_title": "notice:procurement_subject",
            "application_deadline": "notice:application_deadline",
            "nmck": "notice:initial_price",
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
                "procurement_subject": "Тестовая закупка 223-ФЗ",
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

    assert model["procurement_law"] == "223-FZ"
    assert model["decision_core"]["procurement_regime"] == "223fz"


def test_canonical_report_never_says_participate_when_decision_core_needs_review() -> None:
    metadata = {
        "run_id": "decision-core-report-consistency",
        "procurement_id": "0333300006126000121",
        "procurement_title": "Поставка электротехнической продукции",
        "files": [
            {
                "display_name": "Описание объекта закупки.docx",
                "role_hint": "technical_spec",
            },
            {
                "display_name": "Проект контракта.docx",
                "role_hint": "contract_draft",
            },
        ],
        "document_set_summary": {
            "status": "complete",
            "physical_file_count": 2,
            "logical_document_count": 2,
            "logical_documents": [
                {"name": "Описание объекта закупки.docx", "type": "технический документ"},
                {"name": "Проект контракта.docx", "type": "проект контракта"},
            ],
            "missing_required_document_kinds": [],
        },
        "_field_evidence": {
            "procurement_title": "eis_notice:procurement_subject",
            "application_deadline": "eis_notice:application_deadline",
            "nmck": "eis_notice:initial_price",
        },
        "deadline": "30.09.2026 12:00:00 +03:00",
        "analysis_completed_at": "27.09.2026T12:00:00+00:00",
        "procurement": {"initial_price": 133_766.60},
    }
    outputs = {
        "requirements": {
            "preliminary_analysis": {
                "supply_items": [],
                "item_coverage": {},
                "next_actions": [],
            },
            "analysis_context": {
                "procurement_subject": "Поставка электротехнической продукции",
                "nmck": 133_766.60,
                "currency": "RUB",
                "document_coverage": "complete",
                "missing_documents": [],
                "contract_draft_status": "present",
                "contract_draft_documents": ["Проект контракта.docx"],
                "contract_draft_evidence_ids": ["contract:FILE-02"],
            },
        },
        "final_recommendation": {
            "recommendation": "manual_review_required",
            "rationale": ["Требуется ручная проверка перед решением об участии."],
            "manual_checks": ["Проверить коммерческие условия."],
        },
        "contract_risks": {"risks": []},
        "economics": {"metrics": [], "warnings": []},
        "supplier_questions": {"questions": []},
        "quotes_comparison": {"highlights": []},
    }

    model = build_procurement_report_model(metadata, outputs)

    assert model["decision_core"]["decision"]["status"] == "NEEDS_REVIEW"
    assert model["bid_decision"]["status"] == "needs_review"
    assert model["customer_decision"]["recommendation"] == "Требуется проверка"
    assert model["customer_decision"]["recommendation"] != "Участвовать"
    assert model["decision"] == "Требуется ручная проверка перед коммерческим расчётом"
    assert model["customer_decision"]["next_action"] == model["decision_core"]["decision"]["next_action"]


def test_decision_core_accepts_source_bound_localized_nmck_display() -> None:
    model = _grounded_model()
    model["nmck"] = "1 361 068,80"

    decision = build_decision_core(model, supplier_profile=_profile(price_max=2_000_000))

    assert decision["facts"]["nmck"]["status"] == "KNOWN"
    assert decision["facts"]["nmck"]["value"] == "1 361 068,80"
    assert decision["facts"]["nmck"]["evidence"]


def test_customer_confirmed_claims_do_not_invent_unextracted_positions() -> None:
    metadata = {
        "run_id": "decision-core-report-no-items",
        "procurement_id": "0333300006126000121",
        "procurement_title": "Поставка электротехнической продукции",
        "tender_title": "Поставка электротехнической продукции",
        "tender_category": "44-ФЗ",
        "customer_name": "Тестовый заказчик",
        "files": [
            {"display_name": "Проект контракта.docx", "role_hint": "contract_draft"},
        ],
        "document_set_summary": {
            "status": "complete",
            "physical_file_count": 1,
            "logical_document_count": 1,
            "logical_documents": [{"name": "Проект контракта.docx", "type": "проект контракта"}],
            "missing_required_document_kinds": [],
        },
        "_field_evidence": {
            "procurement_title": "card:procurement_subject",
            "application_deadline": "card:submission_deadline",
            "nmck": "card:nmck",
            "customer_name": "card:customer_name",
        },
        "deadline": "2026-09-30T12:00:00+03:00",
        "analysis_completed_at": "2026-09-27T12:00:00+00:00",
        "procurement": {"initial_price": 133_766.60},
    }
    outputs = {
        "requirements": {
            "preliminary_analysis": {
                "supply_items": [],
                "item_coverage": {},
                "next_actions": [],
            },
            "analysis_context": {
                "procurement_subject": "Поставка электротехнической продукции",
                "nmck": 133_766.60,
                "currency": "RUB",
                "document_coverage": "complete",
                "missing_documents": [],
                "contract_draft_status": "present",
                "contract_draft_documents": ["Проект контракта.docx"],
                "contract_draft_evidence_ids": ["contract:FILE-01"],
            },
        },
        "final_recommendation": {
            "recommendation": "manual_review_required",
            "rationale": ["Требуется ручная проверка."],
            "manual_checks": ["Проверить позиции."],
        },
        "contract_risks": {"risks": []},
        "economics": {"metrics": [], "warnings": []},
        "supplier_questions": {"questions": []},
        "quotes_comparison": {"highlights": []},
    }

    model = build_procurement_report_model(metadata, outputs)

    confirmed = model["customer_decision"]["confirmed"]
    reasons = " ".join(model["customer_decision"]["reasons"])
    assert "извлечённые позиции закупки" not in confirmed
    assert "количество и единица измерения по всем извлечённым позициям" not in confirmed
    assert "позиция и количество" not in reasons
    assert "позиции и количество не извлечены в source-bound виде" in model["customer_decision"]["not_evaluated"]


def test_customer_confirmed_claims_do_not_invent_missing_quantity() -> None:
    metadata = {
        "run_id": "decision-core-report-missing-quantity",
        "procurement_id": "0301200067526000236",
        "procurement_title": "Поставка кабельной продукции",
        "tender_title": "Поставка кабельной продукции",
        "tender_category": "44-ФЗ",
        "customer_name": "Тестовый заказчик",
        "files": [{"display_name": "Описание объекта закупки.docx", "role_hint": "technical_spec"}],
        "_field_evidence": {
            "procurement_title": "card:procurement_subject",
            "application_deadline": "card:submission_deadline",
            "nmck": "card:nmck",
            "customer_name": "card:customer_name",
        },
        "deadline": "2026-09-30T12:00:00+03:00",
        "analysis_completed_at": "2026-09-27T12:00:00+00:00",
        "procurement": {"initial_price": 1_361_068.80},
    }
    outputs = {
        "requirements": {
            "preliminary_analysis": {
                "canonical_procurement_model": {
                    "canonical_items": [
                        {
                            "canonical_item_id": "direct-1",
                            "official_name": "Кабель силовой",
                            "display_name": "Кабель силовой",
                            "quantity": None,
                            "unit": None,
                            "evidence_ids": ["ev-1"],
                            "field_provenance": {"name": "ev-1"},
                            "source_document": "Описание объекта закупки.docx",
                            "source_row_number": "позиция 1",
                            "name_source_type": "validated_primary",
                            "quality_gate_status": "valid",
                            "warnings": ["QUANTITY_SOURCE_UNRESOLVED"],
                            "conflicts": [],
                            "field_issues": [],
                        }
                    ],
                    "run_status": "needs_review",
                    "unresolved_candidates": [],
                    "production_model_hash": "a" * 64,
                    "source_graph": {
                        "graph_version": "procurement-source-graph-v2",
                        "production_model_hash": "a" * 64,
                        "structured_fragments": [],
                        "canonical_item_edges": [],
                        "parent_child_edges": [],
                        "cross_source_matches": [],
                        "cardinality_decisions": [],
                    },
                },
                "supply_items": [],
                "item_coverage": {},
                "next_actions": [],
            },
            "analysis_context": {
                "procurement_subject": "Поставка кабельной продукции",
                "nmck": 1_361_068.80,
                "currency": "RUB",
                "document_coverage": "complete",
                "missing_documents": [],
                "contract_draft_status": "absent",
                "contract_draft_documents": [],
                "contract_draft_evidence_ids": [],
            },
        },
        "final_recommendation": {
            "recommendation": "manual_review_required",
            "rationale": ["Требуется ручная проверка."],
            "manual_checks": ["Проверить количество."],
        },
        "contract_risks": {"risks": []},
        "economics": {"metrics": [], "warnings": []},
        "supplier_questions": {"questions": []},
        "quotes_comparison": {"highlights": []},
    }

    model = build_procurement_report_model(metadata, outputs)

    confirmed = model["customer_decision"]["confirmed"]
    assert "извлечённые позиции закупки" in confirmed
    assert "количество и единица измерения по всем извлечённым позициям" not in confirmed
    assert (
        "количество и/или единица измерения не подтверждены для всех извлечённых позиций"
        in model["customer_decision"]["not_evaluated"]
    )


def test_present_but_unparsed_contract_is_review_not_missing() -> None:
    model = _grounded_model()
    model["contract_draft_status"] = "parse_failed"
    model["contract_draft_documents"] = ["Проект контракта.docx"]
    model["contract_draft_evidence_ids"] = ["document_set:contract_draft:1"]

    result = build_decision_core(model, supplier_profile=_profile())

    contract = next(item for item in result["readiness"] if item["code"] == "CONTRACT_DRAFT")
    assert result["decision"]["status"] == "NEEDS_REVIEW"
    assert result["facts"]["contract_draft"]["status"] == "KNOWN"
    assert result["facts"]["contract_draft"]["value"] == "present_unparsed"
    assert contract["status"] == "REVIEW"
    assert contract["blocking"] is True
    assert "присутствует" in contract["summary"].lower()
    assert "отсутствует" not in contract["summary"].lower()
    assert any(item["code"] == "CONTRACT_DRAFT_PARSE" for item in result["unknowns"])


def test_report_reconciles_complete_docset_contract_presence_when_text_parse_failed() -> None:
    metadata = {
        "run_id": "decision-core-contract-parse-failed",
        "procurement_id": "0301200067526000236",
        "procurement_title": "Поставка кабельной продукции",
        "tender_title": "Поставка кабельной продукции",
        "tender_category": "44-ФЗ",
        "customer_name": "Тестовый заказчик",
        "files": [
            {"display_name": "Описание объекта закупки.docx", "role_hint": "technical_spec"},
            {"display_name": "Проект контракта.docx.zip", "role_hint": "contract_draft"},
        ],
        "document_set_summary": {
            "status": "complete",
            "physical_file_count": 2,
            "logical_document_count": 2,
            "logical_documents": [
                {
                    "name": "Описание объекта закупки.docx",
                    "type": "техническая документация",
                    "kind": "technical_specification",
                    "files": ["Описание объекта закупки.docx"],
                },
                {
                    "name": "Проект контракта.docx",
                    "type": "проект контракта",
                    "kind": "contract_draft",
                    "files": ["Проект контракта.docx.zip"],
                },
            ],
            "missing_required_document_kinds": [],
        },
        "_field_evidence": {
            "procurement_title": "card:procurement_subject",
            "application_deadline": "card:submission_deadline",
            "nmck": "card:nmck",
            "customer_name": "card:customer_name",
        },
        "deadline": "2026-09-30T12:00:00+03:00",
        "analysis_completed_at": "2026-09-27T12:00:00+00:00",
        "procurement": {"initial_price": 1_361_068.80},
    }
    outputs = {
        "requirements": {
            "preliminary_analysis": {
                "supply_items": [],
                "item_coverage": {},
                "next_actions": [],
            },
            "analysis_context": {
                "procurement_subject": "Поставка кабельной продукции",
                "nmck": 1_361_068.80,
                "currency": "RUB",
                "document_coverage": "complete",
                "missing_documents": [],
                "contract_draft_status": "absent",
                "contract_draft_documents": [],
                "contract_draft_evidence_ids": [],
            },
        },
        "final_recommendation": {
            "recommendation": "manual_review_required",
            "rationale": ["Требуется ручная проверка."],
            "manual_checks": ["Проверить проект контракта."],
        },
        "contract_risks": {"risks": []},
        "economics": {"metrics": [], "warnings": []},
        "supplier_questions": {"questions": []},
        "quotes_comparison": {"highlights": []},
    }

    model = build_procurement_report_model(metadata, outputs)

    contract = next(
        item
        for item in model["decision_core"]["readiness"]
        if item["code"] == "CONTRACT_DRAFT"
    )
    assert model["contract_draft_status"] == "parse_failed"
    assert model["contract_draft_documents"] == ["Проект контракта.docx"]
    assert model["contract_draft_evidence_ids"]
    assert contract["status"] == "REVIEW"
    assert model["decision_core"]["decision"]["status"] == "NEEDS_REVIEW"
    assert model["customer_decision"]["reasons"] == model["decision_core"]["decision"]["rationale"]
    assert any(
        "проект контракта присутствует, но его текст не извлечён полностью" in item
        for item in model["customer_decision"]["not_evaluated"]
    )
    assert all(
        "проект контракта не найден" not in item.lower()
        for item in model["customer_decision"]["not_evaluated"]
    )
