"""Deterministic legacy-facade behavior and extraction body parity."""

import ast
import hashlib
from pathlib import Path

import pytest

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy


@pytest.mark.parametrize(
    "old,args",
    [
        ("_collect_matches", ("Поставка товара", ("Поставка",))),
        ("_extract_notice_service_deadline", ("оказание услуг до 10 декабря",)),
        ("_extract_inline_goods_field", ("Характеристики: ГОСТ", ("Характеристики",))),
        ("_rewrite_compliance_highlight", ("Требуется согласование",)),
        ("_rewrite_delivery_model_item", ("До конца месяца", "goods")),
        ("_is_goods_supply_table_present", ("товары и количество",)),
    ],
)
def test_facade_passes_through_projector(monkeypatch, old, args):
    marker = object()
    seen = []

    def fake(*values, **kwargs):
        seen.append((values, kwargs))
        return marker

    monkeypatch.setattr(legacy, "project" + old, fake)
    assert (
        getattr(legacy, old)(
            *args,
            **({"stop_markers": ()} if old == "_extract_inline_goods_field" else {}),
        )
        is marker
    )
    assert len(seen) == 1
    assert seen[0][0] == args


def test_ast_original_body_hashes_stable():
    expected = {
        "_collect_matches": "b5de45c153f6dd2a13318b4e803259101b3303f8e8a965072b30f0a2d9426916",
        "_extract_notice_service_deadline": "b5eb7f5b317b5fc7853f6c28be0b7fac5d2c0555e07530896d7efd189878e134",
        "_extract_inline_goods_field": "6a9e094d6f426013dd187fcf75de474e8a1b1ad3a9add35e88c05b070a33c99f",
        "_rewrite_compliance_highlight": "1d0c819aa02787edb6f4279e492008b6c521ef82180a39de3afc3e69e72d3c7c",
        "_rewrite_delivery_model_item": "79f81e7a0843d759565bd6e50e622053dcc042e4297fbfe6502e553e0526f5fb",
        "_is_goods_supply_table_present": "84398a70bc9cfe3de33410112e9da49fc1f802ab906e120b2b7a1590499ff050",
    }
    modules = {
        "_collect_matches": "operator_notice_text_helpers.py",
        "_extract_notice_service_deadline": "operator_notice_text_helpers.py",
        "_extract_inline_goods_field": "operator_notice_text_helpers.py",
        "_rewrite_compliance_highlight": "operator_analysis_text_helpers.py",
        "_rewrite_delivery_model_item": "operator_analysis_text_helpers.py",
        "_is_goods_supply_table_present": "operator_analysis_text_helpers.py",
    }
    for old, module in modules.items():
        tree = ast.parse(
            (Path("src/modules/tender_operator_agent_demo") / module).read_text()
        )
        fn = next(
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "project" + old
        )
        signature = ast.dump(
            ast.Module(body=fn.body, type_ignores=[]), include_attributes=False
        )
        assert hashlib.sha256(signature.encode()).hexdigest() == expected[old]
