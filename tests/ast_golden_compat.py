"""Stable Python 3.12 AST representation for approved source-body goldens.

Python 3.14 changes ast.dump's empty-field defaults. Python 3.15 also
adds Import/ImportFrom.is_lazy=0, a new syntax flag that Python 3.12 does
not represent. Keep original golden hashes for unchanged source code.
Nondefault lazy imports remain distinguishable and invalidate the golden.
"""
from __future__ import annotations

import ast
import copy
import inspect

_HAS_SHOW_EMPTY = "show_empty" in inspect.signature(ast.dump).parameters


def stable_ast_dump(node: ast.AST, *, include_attributes: bool = False) -> str:
    if not _HAS_SHOW_EMPTY:
        return ast.dump(node, include_attributes=include_attributes)

    # Normalize a DEEP COPY: never modify the AST supplied by a test,
    # and never monkeypatch global AST types or repr behavior.
    normalized = copy.deepcopy(node)
    for child in ast.walk(normalized):
        if (isinstance(child, (ast.Import, ast.ImportFrom))
            and getattr(child, "is_lazy", None) == 0
            and "is_lazy" in child._fields):
            # is_lazy=1 remains and will be caught as a real syntax change.
            child._fields = tuple(
                name for name in child._fields if name != "is_lazy"
            )
    return ast.dump(
        normalized, include_attributes=include_attributes, show_empty=True
    )
