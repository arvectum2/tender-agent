"""Legacy HTML layout AST preservation regression."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ORIGINAL_AST_SHA256 = "292821b3b79923da6432f8e7ef2d1611307c1197ac4b880cf6f9409c211dc571"
SOURCE = Path(__file__).resolve().parents[1] / "src/modules/tender_operator_agent_demo/operator_html_layout.py"


def test_original_fstring_interpolation_ast_is_preserved():
    tree = ast.parse(SOURCE.read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "render_operator_html_layout")
    result = next(n for n in function.body if isinstance(n, ast.Return))
    assert isinstance(result.value, ast.JoinedStr)
    sha = hashlib.sha256(ast.dump(result.value, include_attributes=False).encode()).hexdigest()
    assert sha == ORIGINAL_AST_SHA256
