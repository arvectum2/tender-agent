"""Guard removal of demonstrably unused legacy-only private adapters."""

import ast
from pathlib import Path


def test_retired_private_adapters_not_reintroduced() -> None:
    source = Path(
        "src/modules/tender_operator_agent_demo/upload_service_legacy.py"
    ).read_text()
    definitions = {
        node.name
        for node in ast.parse(source).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert not definitions.intersection(
        {
            "_events_path",
            "_decode_text",
            "_import_runner_module",
            "_extract_goods_spec_table_from_tabular_text",
        }
    )
    # Preserve API compatibility even if existing static callers are absent.
    assert "save_uploaded_demo_steps" in definitions
