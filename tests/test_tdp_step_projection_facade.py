"""Historical step API remains stable after isolating view projection."""

from __future__ import annotations

from src.modules.tender_operator_agent_demo import (
    operator_step_projection,
    upload_service_legacy,
)


def test_existing_step_builder_forwards_original_payloads(monkeypatch):
    original = {"requirements": {"requirements": []}}
    metadata = {"run_id": "test-run"}
    called = []

    def delegate(meta, outputs):
        called.append((meta, outputs))
        return []

    monkeypatch.setattr(operator_step_projection, "build_operator_steps", delegate)
    result = upload_service_legacy._build_steps_from_outputs(metadata, original)
    assert result == []
    assert called == [(metadata, original)]
