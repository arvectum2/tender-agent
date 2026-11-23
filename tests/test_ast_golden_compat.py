"""Frozen AST hashes stay stable without masking real syntax changes."""
import ast

from tests.ast_golden_compat import stable_ast_dump


def test_complete_legacy_dump_retains_empty_fields():
    code = ast.parse("value = other")
    frozen = stable_ast_dump(code)
    assert "Name(id='other', ctx=Load())" in frozen
    assert "type_ignores=[]" in frozen


def test_import_default_is_lazy_is_backwards_compatible_and_ast_is_not_mutated():
    tree = ast.parse("from x import y")
    before = ast.dump(tree, include_attributes=False)
    stable = stable_ast_dump(tree)
    assert "ImportFrom(module='x', names=[alias(name='y')], level=0)" in stable
    assert ast.dump(tree, include_attributes=False) == before


def test_nondefault_lazy_import_invalidates_golden_where_supported():
    imported = ast.parse("from x import y").body[0]
    if "is_lazy" not in imported._fields:
        # Legacy interpreters don't represent this syntax flag.
        return
    imported.is_lazy = 1
    text = stable_ast_dump(imported)
    assert "is_lazy=1" in text
