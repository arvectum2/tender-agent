"""Source-preserving report model assembly facade regression."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from src.modules.tender_operator_agent_demo import report_model_legacy as legacy

ORIGINAL_AST_SHA256 = "5edc6a2c293df366bdbeedf20118a56c645b30a5fe8573e170fb3c7a802ca085"
MODULE = Path(__file__).resolve().parents[1] / "src/modules/tender_operator_agent_demo/operator_report_model_builder.py"


def test_source_model_builder_original_body_ast_remains_equal():
    fn = next(node for node in ast.parse(MODULE.read_text()).body if isinstance(node, ast.FunctionDef) and node.name == "build_procurement_report_model")
    digest = hashlib.sha256(ast.dump(ast.Module(body=fn.body, type_ignores=[]), include_attributes=False).encode()).hexdigest()
    assert digest == ORIGINAL_AST_SHA256


def test_legacy_model_builder_calls_runtime_overridden_item_source(monkeypatch):
    calls = []
    def rows(preliminary):
        calls.append(preliminary)
        return []
    monkeypatch.setattr(legacy, "_item_rows", rows)
    inputs = {"requirements": {"preliminary_analysis": {}, "analysis_context": {}}, "final_recommendation": {"rationale": []}, "contract_risks": {"risks": []}, "economics": {"metrics": []}, "supplier_questions": {"questions": []}, "quotes_comparison": {"highlights": []}}
    result = legacy.build_procurement_report_model({"procurement_id": "TEST", "run_id": "RUN", "files": []}, inputs, repository_sha="review-sha")
    assert calls == [{}]
    assert result["metadata"]["repository_sha"] == "review-sha"
    assert result["metadata"]["document_count"] == 0
