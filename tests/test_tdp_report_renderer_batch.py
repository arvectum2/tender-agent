"""Legacy renderer delegation and unchanged extracted implementations."""

import ast
from pathlib import Path

import pytest

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy


@pytest.mark.parametrize(
    "name,args,kwargs",
    [
        ("_render_product_report_html", ({},), {}),
        ("_render_procurement_blocked_report_html", ({},), {}),
        (
            "_build_services_preliminary_analysis",
            (),
            {
                "metadata": {},
                "documents": [],
                "notice_text": "",
                "contract_draft_text": "",
            },
        ),
    ],
)
def test_facade_delegates_without_signature_drift(monkeypatch, name, args, kwargs):
    expected = object()
    seen = []

    def stub(*values, **options):
        seen.append((values, options))
        return expected

    monkeypatch.setattr(legacy, "project" + name, stub)
    assert getattr(legacy, name)(*args, **kwargs) is expected
    assert seen
    assert seen[0][0] == args
    for key, value in kwargs.items():
        assert seen[0][1][key] == value


def test_extracted_functions_have_expected_structural_contract():
    modules = {
        "_render_product_report_html": "operator_report_renderers.py",
        "_render_procurement_blocked_report_html": "operator_report_renderers.py",
        "_build_services_preliminary_analysis": "operator_services_analysis.py",
    }
    for original, module in modules.items():
        source = (Path("src/modules/tender_operator_agent_demo") / module).read_text()
        definitions = [
            node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)
        ]
        matches = [node for node in definitions if node.name == "project" + original]
        assert len(matches) == 1
        assert len(matches[0].body) >= 2


def test_blocked_report_html_escapes_untrusted_metadata():
    report = legacy._render_procurement_blocked_report_html(
        {"notice_number": "<unsafe>"}
    )
    assert "&lt;unsafe&gt;" in report
    assert "<unsafe>" not in report
