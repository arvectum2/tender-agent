"""Verify output construction is isolated without changing legacy runtime contracts."""

import ast
import inspect
from pathlib import Path

from src.modules.tender_operator_agent_demo.operator_output_orchestrator import (
    project_build_output_payloads,
)


def test_output_projection_has_explicit_call_time_injected_dependencies():
    parameters = inspect.signature(project_build_output_payloads).parameters
    for name in (
        "_build_preliminary_procurement_analysis",
        "_build_goods_rfq_payload",
        "_build_document_grounded_requirements",
        "_collect_unmerged_source_items",
        "extract_goods_source_facts",
        "build_operator_risk_payload",
    ):
        assert name in parameters
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY


def test_old_output_facade_forwards_original_signature():
    legacy_module = ast.parse(
        Path(
            "src/modules/tender_operator_agent_demo/upload_service_legacy.py"
        ).read_text()
    )
    facade = next(
        node
        for node in legacy_module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_build_output_payloads"
    )
    original = {param.arg for param in facade.args.kwonlyargs}
    projected = inspect.signature(project_build_output_payloads)
    assert all(name in projected.parameters for name in original)
    for name in original:
        assert projected.parameters[name].kind == inspect.Parameter.KEYWORD_ONLY


def test_source_graph_imports_remain_local_to_projected_function():
    source = Path(
        "src/modules/tender_operator_agent_demo/operator_output_orchestrator.py"
    ).read_text()
    definition = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef)
        and node.name == "project_build_output_payloads"
    )
    imported = {
        alias.asname or alias.name
        for node in ast.walk(definition)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert {
        "StructuredFragmentCollector",
        "direct_fragments_to_canonical_model",
        "provenance_records",
        "serialize_graph",
    } <= imported
