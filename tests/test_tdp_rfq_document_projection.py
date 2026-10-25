"""Backward compatible delegation and immutable behavior of RFQ projections."""

import ast
import hashlib

import pytest

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy


@pytest.mark.parametrize(
    ("old_name", "new_name", "args"),
    [
        (
            "_build_goods_rfq_payload",
            "build_goods_rfq_payload",
            ({"tender_title": "test"}, []),
        ),
        (
            "_build_document_grounded_requirements",
            "build_document_grounded_requirements",
            ([], "goods"),
        ),
        (
            "_build_document_grounded_questions",
            "build_document_grounded_questions",
            ("goods", []),
        ),
        (
            "_build_document_grounded_risks",
            "project_document_grounded_risks",
            ("goods", [], ""),
        ),
    ],
)
def test_legacy_facade_forwards_arguments(monkeypatch, old_name, new_name, args):
    seen = []
    marker = [] if old_name == "_build_document_grounded_requirements" else object()

    def replacement(*values, **dependencies):
        seen.append((values, dependencies))
        return marker

    monkeypatch.setattr(legacy, new_name, replacement)
    result = getattr(legacy, old_name)(*args)
    if old_name == "_build_document_grounded_requirements":
        assert isinstance(result, list)
    else:
        assert result is marker
    assert len(seen) == 1
    assert seen[0][0] == args
    assert seen[0][1]


def test_extracted_function_bodies_match_prechange():
    from pathlib import Path

    expected_hashes = {
        "_build_goods_rfq_payload": "3fc8e45620179f73a6172f33c2a15053f34babd9ab1f207bba96bd6194127042",
        "_build_document_grounded_requirements": "522d29254f338bce4e9423a897588467cbd3b2b0f5fe4b00e333f4b1b565a4b6",
        "_build_document_grounded_questions": "2b0d695d2537ba52baa64b0b763a0bbf3112c8f6e5fd0468f2fe0201167352c6",
        "_build_document_grounded_risks": "9e52ed891bae172640228f5439331d2fd78c09629b5bc25f3332b0566241201c",
    }
    tree = ast.parse(
        Path(
            "src/modules/tender_operator_agent_demo/operator_rfq_document_projections.py"
        ).read_text()
    )
    for old_name, expected in expected_hashes.items():
        node = next(
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef)
            and n.name
            == (
                "project_document_grounded_risks"
                if old_name == "_build_document_grounded_risks"
                else old_name.lstrip("_")
            )
        )
        payload = ast.dump(
            ast.Module(body=node.body, type_ignores=[]), include_attributes=False
        )
        assert hashlib.sha256(payload.encode()).hexdigest() == expected
