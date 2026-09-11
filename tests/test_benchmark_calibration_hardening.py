from __future__ import annotations

from copy import deepcopy

import pytest

from src.modules.benchmark_pipeline.calibration import (
    DISCOVERY_CONTEXT_HASH_REF,
    bind_discovery_context,
    build_discovery_context,
    build_sut_ref,
    discovery_context_sha256,
    infer_runtime_produced_at,
    normalize_runtime_response,
    verify_discovery_context_binding,
)
from src.modules.benchmark_pipeline.comparator import compare_case
from src.modules.benchmark_pipeline.contract import (
    BenchmarkContractError,
    canonical_sha256,
    source_bundle_sha256,
)
from src.modules.benchmark_pipeline.workflow import freeze_blind_labels, prepare_evaluator_bundle


ACQUIRED = "2026-09-06T05:00:00+00:00"
PREPARED = "2026-09-06T05:01:00+00:00"
EVALUATED = "2026-09-06T05:02:00+00:00"
FROZEN = "2026-09-06T05:03:00+00:00"
PRODUCED = "2026-09-06T05:04:00+00:00"
COMPARED = "2026-09-06T05:05:00+00:00"


def _manifest() -> dict:
    documents = [
        {
            "path": "source/notice.html",
            "sha256": "a" * 64,
            "source_url": "https://example.test/notice/TEST-001",
        }
    ]
    return {
        "schema_version": "1.1.0",
        "case_id": "calibration-context-1",
        "procurement": {
            "notice_number": "TEST-001",
            "title": "AI service procurement",
            "source": "public_eis_html_44fz",
            "law": "44-ФЗ",
        },
        "source_urls": ["https://example.test/notice/TEST-001"],
        "acquired_at": ACQUIRED,
        "documents": documents,
        "source_scope": "sanitized public calibration fixture",
        "source_bundle_sha256": source_bundle_sha256(documents),
        "source_conflict": False,
        "provenance_sufficient": True,
    }


def _profile() -> dict:
    return {
        "supplier_id": "fixture-electrical",
        "criteria": {
            "categories": ["electrical equipment"],
            "regions": ["Moscow region"],
            "keywords": ["cable", "switchgear"],
        },
    }


def _context() -> dict:
    return build_discovery_context(
        supplier_profile=_profile(),
        registry_number="TEST-001",
        source="public_eis_html_44fz",
        law="44-ФЗ",
        as_of=ACQUIRED,
        query="cable",
    )


def _labels(bundle: dict) -> tuple[dict, dict]:
    discovery = {
        "schema_version": "1.1.0",
        "case_id": bundle["case_id"],
        "source_bundle_sha256": bundle["source_bundle_sha256"],
        "label": "RELEVANT",
        "reason": "The frozen supplier profile matches the source candidate.",
        "confidence": 0.95,
        "evidence": [{"source_ref": "source/notice.html", "locator": "title"}],
        "evaluator": "independent-evaluator",
        "evaluated_at": EVALUATED,
    }
    truth = {
        "schema_version": "1.1.0",
        "case_id": bundle["case_id"],
        "source_bundle_sha256": bundle["source_bundle_sha256"],
        "facts": [],
        "confidence": 0.95,
        "evaluator": "independent-evaluator",
        "evaluated_at": EVALUATED,
    }
    return discovery, truth


def _normalized(bundle: dict, *, label: str = "IRRELEVANT") -> dict:
    return {
        "schema_version": "1.1.0",
        "case_id": bundle["case_id"],
        "source_bundle_sha256": bundle["source_bundle_sha256"],
        "discovery": {"label": label, "ranking_delta": None},
        "facts": [],
    }


def _sut_ref(output: dict, freeze: dict, *, context_hash: str | None) -> dict:
    refs = {"runtime_response": "sut_runtime_response.json"}
    if context_hash is not None:
        refs[DISCOVERY_CONTEXT_HASH_REF] = context_hash
    return {
        "schema_version": "1.1.0",
        "case_id": output["case_id"],
        "runtime_version": "fixture-runtime@1",
        "artifact_refs": refs,
        "produced_at": PRODUCED,
        "source_bundle_sha256": output["source_bundle_sha256"],
        "label_set_sha256_at_generation": freeze["label_set_sha256"],
        "normalized_output_sha256": canonical_sha256(output),
    }


def test_discovery_context_binds_complete_supplier_snapshot_into_frozen_manifest():
    manifest = _manifest()
    context = _context()
    bound = bind_discovery_context(manifest, context)

    assert "benchmark_discovery_context" not in manifest["procurement"]
    assert bound["procurement"]["benchmark_discovery_context"]["supplier_profile"] == _profile()
    assert discovery_context_sha256(bound) == canonical_sha256(context)

    tampered = deepcopy(context)
    tampered["supplier_profile"]["criteria"]["keywords"].append("unfrozen-change")
    with pytest.raises(BenchmarkContractError, match="digest is inconsistent"):
        bind_discovery_context(manifest, tampered)


def test_context_relative_discovery_is_not_scorable_when_sut_context_is_unbound():
    manifest = bind_discovery_context(_manifest(), _context())
    bundle = prepare_evaluator_bundle(manifest, prepared_at=PREPARED)
    discovery, truth = _labels(bundle)
    freeze = freeze_blind_labels(bundle, discovery, truth, frozen_at=FROZEN)
    output = _normalized(bundle, label="IRRELEVANT")

    result = compare_case(
        discovery_label=discovery,
        document_truth=truth,
        evaluator_bundle=bundle,
        freeze_receipt=freeze,
        sut_ref=_sut_ref(output, freeze, context_hash=None),
        sut_output=output,
        compared_at=COMPARED,
    )

    assert result["discovery"]["expected"] == "RELEVANT"
    assert result["discovery"]["actual"] == "IRRELEVANT"
    assert result["discovery"]["outcome"] == "NOT_SCORABLE"
    assert result["material_disagreement"] is False


def test_context_relative_discovery_scores_only_exact_bound_context():
    manifest = bind_discovery_context(_manifest(), _context())
    bundle = prepare_evaluator_bundle(manifest, prepared_at=PREPARED)
    discovery, truth = _labels(bundle)
    freeze = freeze_blind_labels(bundle, discovery, truth, frozen_at=FROZEN)
    output = _normalized(bundle, label="IRRELEVANT")
    context_hash = discovery_context_sha256(bundle)
    assert context_hash is not None

    ref = _sut_ref(output, freeze, context_hash=context_hash)
    assert verify_discovery_context_binding(bundle, ref) == context_hash
    result = compare_case(
        discovery_label=discovery,
        document_truth=truth,
        evaluator_bundle=bundle,
        freeze_receipt=freeze,
        sut_ref=ref,
        sut_output=output,
        compared_at=COMPARED,
    )
    assert result["discovery"]["outcome"] == "MISMATCH"
    assert result["material_disagreement"] is True

    wrong_ref = _sut_ref(output, freeze, context_hash="f" * 64)
    with pytest.raises(BenchmarkContractError, match="different discovery context"):
        verify_discovery_context_binding(bundle, wrong_ref)


def test_runtime_normalizer_maps_known_facts_and_preserves_material_unclassified_claims():
    runtime = {
        "run_id": "toa-run-fixture",
        "tender_title": "AI assistants for municipal service",
        "customer_name": "Municipal Customer",
        "final_recommendation": {
            "economics": [
                "НМЦК: 3 400 000,00",
                "Закупочная себестоимость: не определена, требуется ТКП",
            ],
            "key_requirements": ["Интеграция с внешним реестром"],
            "risks": ["Зависимость от внешнего доступа"],
            "rationale": ["Документы требуют ручной проверки"],
            "open_questions": ["Есть ли доступ к тестовому контуру?"],
            "manual_checks": ["Проверить исходные документы."],
            "label": "нужна ручная проверка",
            "recommendation": "manual_review_required",
            "trace": "bounded runtime trace",
        },
    }

    output, audit = normalize_runtime_response(
        runtime_response=runtime,
        case_id="calibration-context-1",
        source_bundle_sha256="b" * 64,
    )
    facts = {item["field"]: item for item in output["facts"]}

    assert facts["procurement_subject"]["value"] == "AI assistants for municipal service"
    assert facts["customer_name"]["value"] == "Municipal Customer"
    assert facts["initial_max_price_rub"]["value"] == 3400000.0
    assert facts["runtime_claim.final_recommendation.key_requirements.0"]["materiality"] == "MATERIAL"
    assert facts["runtime_claim.final_recommendation.risks.0"]["materiality"] == "MATERIAL"
    assert audit["counts"] == {
        "mapped": 3,
        "preserved_extra": 4,
        "ignored_non_assertion": 5,
    }
    assert audit["normalized_output_sha256"] == canonical_sha256(output)


def test_runtime_normalizer_fails_closed_on_new_decision_payload_shape():
    runtime = {
        "final_recommendation": {
            "key_requirements": [],
            "new_claim_surface": ["A new factual output that is not covered by the normalizer"],
        }
    }
    with pytest.raises(BenchmarkContractError, match="unclassified final_recommendation fields"):
        normalize_runtime_response(
            runtime_response=runtime,
            case_id="calibration-context-1",
            source_bundle_sha256="b" * 64,
        )


def test_runtime_normalizer_maps_explicit_contract_terms_from_analysis_context():
    runtime = {
        "runtime_analysis": {
            "analysis_context": {
                "payment_terms": {"payment": "100% after acceptance", "deadline": "5 working days"},
                "advance_payment": False,
                "performance_security_percent": 10.0,
                "acceptance_terms": {
                    "executor_submission": "5 working days after completion",
                    "customer_acceptance": "5 working days after receipt",
                },
            }
        },
        "final_recommendation": {},
    }

    output, audit = normalize_runtime_response(
        runtime_response=runtime,
        case_id="calibration-context-1",
        source_bundle_sha256="b" * 64,
    )
    facts = {item["field"]: item for item in output["facts"]}

    assert facts["payment_terms"]["value"] == runtime["runtime_analysis"]["analysis_context"]["payment_terms"]
    assert facts["advance_payment"]["value"] is False
    assert facts["performance_security_percent"]["value"] == 10.0
    assert facts["acceptance_terms"]["value"] == runtime["runtime_analysis"]["analysis_context"]["acceptance_terms"]
    assert {entry["source_path"] for entry in audit["entries"]} >= {
        "runtime_analysis.analysis_context.payment_terms",
        "runtime_analysis.analysis_context.advance_payment",
        "runtime_analysis.analysis_context.performance_security_percent",
        "runtime_analysis.analysis_context.acceptance_terms",
    }


def test_runtime_normalizer_does_not_extract_contract_terms_from_prose():
    runtime = {
        "runtime_analysis": {
            "analysis_context": {},
            "trace": {
                "source_excerpt": (
                    "Выплата аванса не предусмотрена. Размер обеспечения исполнения контракта, % от НМЦК | 10"
                )
            },
        },
        "final_recommendation": {},
    }

    output, _ = normalize_runtime_response(
        runtime_response=runtime,
        case_id="calibration-context-1",
        source_bundle_sha256="b" * 64,
    )

    assert {item["field"] for item in output["facts"]}.isdisjoint(
        {"payment_terms", "advance_payment", "performance_security_percent", "acceptance_terms"}
    )


def test_runtime_normalizer_maps_execution_and_warranty_terms_only_from_typed_context():
    values = {
        "service_start": "0 days after contract signing",
        "service_deadline": "2026-11-30",
        "contract_end_date": "2026-12-23",
        "performance_place": "One address",
        "warranty_term": "12 months after acceptance",
        "warranty_security_required": False,
    }
    output, audit = normalize_runtime_response(
        runtime_response={"runtime_analysis": {"analysis_context": values}, "final_recommendation": {}},
        case_id="calibration-context-1",
        source_bundle_sha256="b" * 64,
    )
    facts = {item["field"]: item["value"] for item in output["facts"]}

    assert {field: facts[field] for field in values} == values
    assert {entry["source_path"] for entry in audit["entries"]} >= {
        f"runtime_analysis.analysis_context.{field}" for field in values
    }


def test_runtime_normalizer_maps_only_explicit_runtime_positions_contract():
    positions = [
        {
            "position": 1,
            "name": "Кабель",
            "quantity": 10,
            "unit": "м",
            "classification_code": None,
            "source_document": "Обоснование НМЦК.docx",
            "source_row_number": 1,
            "evidence_id": "ev-position-1",
        }
    ]
    expected = [
        {
            "position": 1,
            "name": "Кабель",
            "quantity": 10,
            "unit": "м",
            "classification_code": None,
        }
    ]
    output, audit = normalize_runtime_response(
        runtime_response={
            "final_recommendation": {},
            "runtime_analysis": {"analysis_context": {"positions": positions}},
        },
        case_id="calibration-context-1",
        source_bundle_sha256="b" * 64,
    )

    assert output["facts"] == [
        {
            "field": "positions",
            "value": expected,
            "status": "ASSERTED",
            "materiality": "MATERIAL",
        }
    ]
    assert audit["entries"] == [
        {
            "source_path": "runtime_analysis.analysis_context.positions",
            "action": "MAPPED",
            "normalized_field": "positions",
        }
    ]


def test_runtime_normalizer_rejects_incomplete_positions_contract():
    output, audit = normalize_runtime_response(
        runtime_response={
            "final_recommendation": {},
            "runtime_analysis": {"analysis_context": {"positions": [{"position": 1}]}},
        },
        case_id="calibration-context-1",
        source_bundle_sha256="b" * 64,
    )

    assert output["facts"] == []
    assert audit["counts"]["mapped"] == 0


def test_runtime_timestamp_and_sut_ref_use_actual_analysis_completion_and_audit_binding():
    runtime = {
        "events": [
            {"event_type": "analysis_started", "timestamp": "2026-09-06T05:03:10Z"},
            {"event_type": "llm_analysis_completed", "timestamp": "2026-09-06T05:03:20Z"},
            {"event_type": "analysis_completed", "timestamp": "2026-09-06T05:03:21Z"},
        ],
        "final_recommendation": {},
    }
    produced_at = infer_runtime_produced_at(runtime)
    assert produced_at == "2026-09-06T05:03:21Z"

    output, audit = normalize_runtime_response(
        runtime_response=runtime,
        case_id="calibration-context-1",
        source_bundle_sha256="b" * 64,
    )
    freeze = {
        "schema_version": "1.1.0",
        "case_id": "calibration-context-1",
        "frozen_at": FROZEN,
        "source_bundle_sha256": "b" * 64,
        "evaluator_bundle_sha256": "c" * 64,
        "discovery_label_sha256": "d" * 64,
        "document_truth_sha256": "e" * 64,
        "label_set_sha256": "f" * 64,
        "case_manifest_sha256": "1" * 64,
    }
    audit_sha = canonical_sha256(audit)
    ref = build_sut_ref(
        normalized_output=output,
        freeze_receipt=freeze,
        runtime_version="fixture-runtime@1",
        runtime_response_ref="sut_runtime_response.json",
        produced_at=produced_at,
        normalization_audit_ref="normalization_audit.json",
        normalization_audit_sha256=audit_sha,
        discovery_context_sha256_at_generation="2" * 64,
    )

    assert ref["artifact_refs"]["normalization_audit_sha256"] == audit_sha
    assert ref["artifact_refs"][DISCOVERY_CONTEXT_HASH_REF] == "2" * 64
    assert ref["produced_at"] == produced_at
