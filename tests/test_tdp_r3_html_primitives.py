"""HTML helper extraction: original AST, escape safety and compatibility."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from src.modules.tender_operator_agent_demo import operator_html_primitives as h

ORIGINAL_HASHES = {'list_html': '23307cb0ce564010622a69cd0ff91d48219b0ddd860d5df11bde365e9073207c', 'is_missing': '05e414c475d2282729b7949478b4f1e8fb24b77c700a7a0387b2e590a78e2f6f', 'format_value': '49750e1188a208aa8df71b25b13b19ad390fe65a89a5e9bf30db66a9c53c35c1', 'format_date_ru': '6006807d8e9d0e1d0a42dd9531271e6a37885c81d041ea9503f7713e68da56c6', 'format_price': '240d20c6085f318cbfc748e33fd83293fced72bc205fc46fde4e2d5754bc976b', 'build_archive_button_html': '54ae083a9cf9cb91d6d6cf6a00badc34c118950d284143100db16a0c0636168c', 'build_export_buttons_html': '427bc35b58347659b1bf22a115386553f8c35c6bd26671258d538a8ed4e6c201', 'build_document_list_html': '06e7658a2abe832cda960c1954824ad08e36cc24fe39fb43d93d92c6284acd7a', 'build_document_toggle_html': 'df4cf5d7c87e3b1de6f320cd1a0883cd5463fd250d8a7ea34b1b84c1591567a7', 'format_publication_update': '4f4faaadc702a710c90d66144e41ee5350606ae33a5655f4d0c5e174bbbf13b6', 'render_table': 'd4f31819991c2cf0467a8fb0353363a5b8e7faf83fd7e690f4fe27b52040862f'}
EXTRACTED = (
    Path(__file__).resolve().parents[1]
    / "src/modules/tender_operator_agent_demo/operator_html_primitives.py"
)


def test_all_original_nested_function_bodies_ast_identical():
    tree = ast.parse(EXTRACTED.read_text())
    by_name = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert by_name.keys() == ORIGINAL_HASHES.keys()
    for name, expected in ORIGINAL_HASHES.items():
        actual = hashlib.sha256(
            ast.dump(ast.Module(body=by_name[name].body, type_ignores=[]), include_attributes=False).encode()
        ).hexdigest()
        assert actual == expected, name


@pytest.mark.parametrize("value, expected", [
    (None, "не указано"),
    ("  Да  ", "Да"),
    ("не указан", "не указано"),
])
def test_legacy_missing_value_behavior(value, expected):
    assert h.format_value(value) == expected


def test_russian_date_and_price_projection():
    assert h.format_date_ru("2026-10-08T11:25:00") == "08.10.2026"
    assert h.format_price(1250.5, "RUB") == "1 250,50 RUB"


def test_buttons_escape_untrusted_run_id():
    result = h.build_export_buttons_html('bad"><script>alert(1)</script>')
    assert "<script>" not in result
    assert "&lt;script&gt;" in result
    assert h.build_archive_button_html("run-1", False) == ""


def test_document_toggle_escapes_source_names_and_ids():
    result = h.build_document_toggle_html(
        "run-1", [{"file_id": 'id"><img src=x>', "display_name": "<script>evil</script>"}]
    )
    assert "<script>" not in result
    assert "<img" not in result
    assert "&lt;script&gt;" in result
    assert "document-toggle" in result
    assert "Документы для скачивания" in h.build_document_toggle_html("run-1", [])


def test_table_cell_and_column_escaping():
    result = h.render_table(["<tag>"], [{"<tag>": "<unsafe>"}])
    assert "<tag>" not in result
    assert "<unsafe>" not in result
    assert "&lt;unsafe&gt;" in result
    assert "Нет данных" in h.render_table(["col"], [])
