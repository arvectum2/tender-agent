"""Legacy report item rows projection extraction regression contracts."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.modules.tender_operator_agent_demo import report_model_legacy as legacy

EXPECTED_SOURCE_AST_SHA256 = "8e80aa0b7143fb5f8315e3a132521eef1ba6658270a69248be247a97ff480711"
SRC = Path(__file__).resolve().parents[1] / "src/modules/tender_operator_agent_demo/operator_report_item_rows.py"


def test_original_projection_body_ast_remains_identical():
    tree = ast.parse(SRC.read_text())
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "build_item_rows")
    actual = hashlib.sha256(ast.dump(ast.Module(body=fn.body, type_ignores=[]), include_attributes=False).encode()).hexdigest()
    assert actual == EXPECTED_SOURCE_AST_SHA256


@pytest.mark.parametrize("mode", ["legacy", "shadow"])
def test_legacy_and_shadow_fallback_preserve_quantity_and_source(monkeypatch, mode):
    monkeypatch.setattr(legacy, "get_settings", lambda: SimpleNamespace(source_graph_mode=mode))
    items = [{"name": "Компьютер", "quantity": 2, "unit": "шт", "evidence_id": "real-chunk",
              "name_source_type": "source_fact", "source_row": 5}]
    result = legacy._item_rows({"supply_items": items})
    assert len(result) == 1
    assert result[0]["quantity"] == 2
    assert result[0]["evidence_ids"] == ["real-chunk"]
    assert result[0]["source_row"] == "позиция 5"
    assert result[0]["stable_item_id"] == "real-chunk"


def test_production_forbids_legacy_fallback(monkeypatch):
    monkeypatch.setattr(legacy, "get_settings", lambda: SimpleNamespace(source_graph_mode="production"))
    with pytest.raises(RuntimeError, match="SOURCE_GRAPH_MODEL_REQUIRED"):
        legacy._item_rows({"supply_items": [{"name": "Не подтверждено"}]})


def test_production_only_uses_canonical_source(monkeypatch):
    monkeypatch.setattr(legacy, "get_settings", lambda: SimpleNamespace(source_graph_mode="production"))
    preliminary = {"canonical_procurement_model": {"canonical_items": [
        {"official_name": "Источник", "canonical_item_id": "CAN-1", "unit": "шт"}
    ]}, "supply_items": [{"name": "Нельзя использовать"}]}
    rows = legacy._item_rows(preliminary)
    assert len(rows) == 1
    assert rows[0]["official_name"] == "Источник"
    assert rows[0]["stable_item_id"] == "CAN-1"
    assert rows[0]["quantity"] is None
    assert rows[0]["quantity_status"] == "not_specified"


def test_unresolved_name_not_invented(monkeypatch):
    monkeypatch.setattr(legacy, "get_settings", lambda: SimpleNamespace(source_graph_mode="legacy"))
    assert legacy._item_rows({"supply_items": [{"quantity": 55}]}) == []


def test_invalid_mode_fail_closed(monkeypatch):
    monkeypatch.setattr(legacy, "get_settings", lambda: SimpleNamespace(source_graph_mode="dangerous"))
    with pytest.raises(ValueError, match="SOURCE_GRAPH_MODE"):
        legacy._item_rows({"supply_items": [{"name": "Компьютер"}]})


def test_injected_original_helpers_called_at_runtime(monkeypatch):
    monkeypatch.setattr(legacy, "get_settings", lambda: SimpleNamespace(source_graph_mode="shadow"))
    monkeypatch.setattr(legacy, "_format_source_location", lambda v: "CUSTOM-LOC")
    monkeypatch.setattr(legacy, "_quality_gate_status", lambda *args: "CUSTOM-GATE")
    rows = legacy._item_rows({"supply_items": [{"name": "Наименование", "source_row": 10}]})
    assert rows[0]["source_row"] == "CUSTOM-LOC"
    assert rows[0]["quality_gate_status"] == "CUSTOM-GATE"
