"""Immutable historical binding backfill extraction contracts."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

EXPECTED_BODY_AST_SHA256 = "d6fe9df602e3726563d4996a4beea851923f2c3fece2cfe1755eddd913b20b30"
EXTRACTED = (
    Path(__file__).resolve().parents[1]
    / "src/modules/customer_pilot/legacy_binding_backfill_orchestrator.py"
)


def test_original_immutable_backfill_body_ast_identical():
    tree = ast.parse(EXTRACTED.read_text())
    fn = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "run_immutable_backfill"
    )
    actual = hashlib.sha256(
        ast.dump(ast.Module(body=fn.body, type_ignores=[]), include_attributes=False).encode()
    ).hexdigest()
    assert actual == EXPECTED_BODY_AST_SHA256
