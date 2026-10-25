"""The large historical HTML renderer stays behind a stable compatibility API."""

from __future__ import annotations

from src.modules.tender_operator_agent_demo import (
    operator_legacy_html_renderer,
    upload_service_legacy,
)


def test_legacy_html_renderer_delegates_exact_inputs_and_presentation_dependencies(monkeypatch):
    observed = {}

    def substitute(metadata, outputs, **kwargs):
        observed.update(metadata=metadata, outputs=outputs, callbacks=kwargs)
        return "<html>delegate</html>"

    monkeypatch.setattr(operator_legacy_html_renderer, "render_legacy_report_html", substitute)
    metadata = {"run_id": "test-run"}
    outputs = {"requirements": {"requirements": []}}
    assert upload_service_legacy._render_report_html(metadata, outputs) == "<html>delegate</html>"
    assert observed["metadata"] is metadata
    assert observed["outputs"] is outputs
    for callback in ("inventory_builder", "supply_section_title", "input_dir_resolver"):
        assert callable(observed["callbacks"][callback])
