"""Compatibility and deterministic behavior for extracted notice and goods fields."""

import ast
import hashlib

import pytest

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy


@pytest.mark.parametrize(
    ("facade", "delegate", "args"),
    [
        ("_extract_notice_price", "extract_notice_price", ({"initial_price": "1200"},)),
        (
            "_extract_notice_delivery_deadline",
            "extract_notice_delivery_deadline",
            ("Срок поставки: 10 дней",),
        ),
        (
            "_split_trailing_classification",
            "split_trailing_classification",
            ("Принтер КТРУ 26.20",),
        ),
        (
            "_summarize_supply_characteristics",
            "summarize_supply_characteristics",
            (["ГОСТ 1"],),
        ),
    ],
)
def test_legacy_facade_delegation(monkeypatch, facade, delegate, args):
    sentinel = object()
    calls = []

    def adapter(*values, **kwargs):
        calls.append((values, kwargs))
        return sentinel

    monkeypatch.setattr(legacy, delegate, adapter)
    assert getattr(legacy, facade)(*args) is sentinel
    assert len(calls) == 1


def test_characteristic_dedupe_and_filtering():
    assert legacy._summarize_supply_characteristics(
        ["ГОСТ 1", "гост 1", "Поставщик", "ГОСТ 2"]
    ) == ["ГОСТ 1", "ГОСТ 2"]


def test_notice_price_absent_is_none():
    assert legacy._extract_notice_price({}, "") is None


def test_extracted_bodies_equal_original():
    from pathlib import Path

    expected_body_hashes = {
        "_extract_notice_price": "b33eda1b54cec655b5bf23756fc32a96a3600a212560723c057213828e9b8248",
        "_extract_notice_delivery_deadline": "28b99f4422a22578025dd9487ad9967233dce2b5ebabf7417614317dd6070d5b",
        "_split_trailing_classification": "7eb639fec09a079caa881bb290b6fa76c365dc8b7360d597453633d6f2bff79b",
        "_summarize_supply_characteristics": "6be5af3d7b23583239872c7cd0c54c7b8930c119997992d38b773ca71c9f896c",
    }
    base = Path("src/modules/tender_operator_agent_demo")
    modules = {
        "_extract_notice_price": ("operator_notice_fields.py", "extract_notice_price"),
        "_extract_notice_delivery_deadline": (
            "operator_notice_fields.py",
            "extract_notice_delivery_deadline",
        ),
        "_split_trailing_classification": (
            "operator_goods_text_fields.py",
            "split_trailing_classification",
        ),
        "_summarize_supply_characteristics": (
            "operator_goods_text_fields.py",
            "summarize_supply_characteristics",
        ),
    }
    for prior, (file, extracted_name) in modules.items():
        extracted = next(
            node
            for node in ast.parse((base / file).read_text()).body
            if isinstance(node, ast.FunctionDef) and node.name == extracted_name
        )
        digest = hashlib.sha256(
            ast.dump(
                ast.Module(body=extracted.body, type_ignores=[]),
                include_attributes=False,
            ).encode()
        ).hexdigest()
        assert digest == expected_body_hashes[prior]
