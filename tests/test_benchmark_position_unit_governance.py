"""Issue #17: one shared typed-position unit policy, enforced before freeze.

No procurement numbers, filenames, or case-specific row values are used.
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from src.modules.benchmark_pipeline import (
    BenchmarkContractError,
    canonical_sha256,
    freeze_blind_labels,
    prepare_evaluator_bundle,
    source_bundle_sha256,
    validate_artifact,
    verify_frozen_labels,
)
from src.modules.benchmark_pipeline.workflow import (
    validate_typed_position_units_for_freeze,
)
from src.modules.tender_operator_agent_demo.goods_source_facts import (
    build_complete_goods_positions,
)
from src.modules.tender_operator_agent_demo.upload_service_legacy import SupplyItem
from src.shared.procurement_units import canonicalize_typed_position_unit

PREPARED = "2026-09-06T12:00:00+00:00"
EVALUATED = "2026-09-06T12:01:00+00:00"
FROZEN = "2026-09-06T12:02:00+00:00"

DOCUMENTS = [
    {
        "path": "source/notice.txt",
        "sha256": "a" * 64,
        "source_url": "https://example.test/procurement/TEST-001",
    }
]


def _manifest() -> dict:
    return {
        "schema_version": "1.1.0",
        "case_id": "calibration-units-1",
        "procurement": {"notice_number": "TEST-001", "title": "Calibration procurement"},
        "source_urls": ["https://example.test/procurement/TEST-001"],
        "acquired_at": "2026-09-06T11:59:00+00:00",
        "documents": deepcopy(DOCUMENTS),
        "source_scope": "public notice and attached procurement documents",
        "source_bundle_sha256": source_bundle_sha256(DOCUMENTS),
        "source_conflict": False,
        "provenance_sufficient": True,
    }


def _bundle() -> dict:
    return prepare_evaluator_bundle(_manifest(), prepared_at=PREPARED)


def _discovery() -> dict:
    return {
        "schema_version": "1.1.0",
        "case_id": "calibration-units-1",
        "source_bundle_sha256": source_bundle_sha256(DOCUMENTS),
        "label": "RELEVANT",
        "reason": "Independent source-grounded calibration decision.",
        "confidence": 0.95,
        "evidence": [{"source_ref": "source/notice.txt", "locator": "title"}],
        "evaluator": "independent-evaluator",
        "evaluated_at": EVALUATED,
    }


def _positions_fact(units: list[str]) -> dict:
    return {
        "field": "positions",
        "value": [
            {
                "position": index + 1,
                "name": f"Изделие {index + 1}",
                "quantity": (index + 1) * 10,
                "unit": unit,
                "classification_code": None,
            }
            for index, unit in enumerate(units)
        ],
        "evidence": [{"source_ref": "source/notice.txt", "locator": "table"}],
        "confidence": 0.98,
        "abstention": "ASSERTED",
        "materiality": "MATERIAL",
    }


def _truth(facts: list[dict]) -> dict:
    return {
        "schema_version": "1.1.0",
        "case_id": "calibration-units-1",
        "source_bundle_sha256": source_bundle_sha256(DOCUMENTS),
        "facts": facts,
        "confidence": 0.95,
        "evaluator": "independent-evaluator",
        "evaluated_at": EVALUATED,
    }


def test_shared_helper_canonicalizes_known_aliases():
    assert canonicalize_typed_position_unit("шт") == "шт"
    assert canonicalize_typed_position_unit("шт.") == "шт"
    assert canonicalize_typed_position_unit("штука") == "шт"
    assert canonicalize_typed_position_unit("штук") == "шт"
    assert canonicalize_typed_position_unit("упак") == "упак"
    assert canonicalize_typed_position_unit("упак.") == "упак"
    assert canonicalize_typed_position_unit("упаковка") == "упак"
    assert canonicalize_typed_position_unit("рул") == "рул."
    assert canonicalize_typed_position_unit("рул.") == "рул."


def test_shared_helper_preserves_unknown_and_fails_safe():
    assert canonicalize_typed_position_unit("компл") == "компл"
    assert canonicalize_typed_position_unit("  шт  ") == "шт"
    assert canonicalize_typed_position_unit("") is None
    assert canonicalize_typed_position_unit(None) is None


def _supply_row(item_no: str, unit: str) -> SupplyItem:
    return SupplyItem(
        item_no, "Изделие", "10", unit, [], [], None,
        "nmck-synthetic.xlsx", "nmck_xlsx", "high", "row",
        source_row_number=int(item_no), evidence_id=f"ev-{item_no}",
    )


def test_product_contract_uses_shared_unit_policy():
    rows = [_supply_row("1", "шт."), _supply_row("2", "упак."), _supply_row("3", "рул")]

    positions = build_complete_goods_positions(rows)

    assert [row["unit"] for row in positions] == ["шт", "упак", "рул."]


def test_future_freeze_accepts_canonical_positions_truth():
    truth = _truth([_positions_fact(["шт", "упак", "рул."])])

    receipt = freeze_blind_labels(_bundle(), _discovery(), truth, frozen_at=FROZEN)

    assert receipt["case_id"] == "calibration-units-1"


@pytest.mark.parametrize(
    ("unit", "canonical"),
    [("шт.", "шт"), ("упак.", "упак"), ("рул", "рул.")],
)
def test_future_freeze_rejects_noncanonical_unit(unit: str, canonical: str):
    truth = _truth([_positions_fact([unit])])

    with pytest.raises(BenchmarkContractError, match=rf"positions\[0\]\.unit is not canonical.*{canonical}"):
        freeze_blind_labels(_bundle(), _discovery(), truth, frozen_at=FROZEN)


def test_future_freeze_does_not_rewrite_truth():
    truth = _truth([_positions_fact(["шт."])])
    before = deepcopy(truth)

    with pytest.raises(BenchmarkContractError):
        freeze_blind_labels(_bundle(), _discovery(), truth, frozen_at=FROZEN)

    assert truth == before


def test_non_positions_facts_are_unaffected():
    truth = _truth([
        {
            "field": "customer_name",
            "value": "Calibration Customer",
            "evidence": [{"source_ref": "source/notice.txt", "locator": "c"}],
            "confidence": 0.98,
            "abstention": "ASSERTED",
            "materiality": "MATERIAL",
        }
    ])

    receipt = freeze_blind_labels(_bundle(), _discovery(), truth, frozen_at=FROZEN)

    assert receipt["case_id"] == "calibration-units-1"


def test_positions_abstention_is_unaffected():
    truth = _truth([
        {
            "field": "positions",
            "value": None,
            "evidence": [{"source_ref": "source/notice.txt", "locator": "t"}],
            "confidence": 0.9,
            "abstention": "INSUFFICIENT_EVIDENCE",
            "materiality": "MATERIAL",
        }
    ])

    receipt = freeze_blind_labels(_bundle(), _discovery(), truth, frozen_at=FROZEN)

    assert receipt["case_id"] == "calibration-units-1"


def test_historical_noncanonical_freeze_still_verifies():
    bundle = _bundle()
    discovery = _discovery()
    truth = _truth([_positions_fact(["шт.", "упак.", "рул"])])
    label_hashes = {
        "discovery_label_sha256": canonical_sha256(discovery),
        "document_truth_sha256": canonical_sha256(truth),
    }
    receipt = {
        "schema_version": "1.1.0",
        "case_id": bundle["case_id"],
        "frozen_at": FROZEN,
        "source_bundle_sha256": bundle["source_bundle_sha256"],
        "evaluator_bundle_sha256": canonical_sha256(bundle),
        "case_manifest_sha256": bundle["case_manifest_sha256"],
        **label_hashes,
        "label_set_sha256": canonical_sha256(label_hashes),
    }

    verify_frozen_labels(receipt, bundle, discovery, truth)


def test_truth_schema_validation_remains_spelling_agnostic():
    truth = _truth([_positions_fact(["шт."])])

    validate_artifact("blind_document_truth", truth)
    validate_typed_position_units_for_freeze(_truth([_positions_fact(["шт"])]))
