from __future__ import annotations

import json
from types import SimpleNamespace

from src.modules.controlled_llm_prebid import service
from src.shared.config.settings import Settings


def test_openai_compatible_provider_includes_strict_output_schema(monkeypatch) -> None:
    captured: dict[str, object] = {}
    schema = {
        "type": "object",
        "properties": {
            "requirements_summary": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["requirements_summary"],
    }

    def fake_json_request(request, *, attempts: int, timeout_seconds: int):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["attempts"] = attempts
        captured["timeout_seconds"] = timeout_seconds
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({"requirements_summary": ["one"]}),
                    }
                }
            ]
        }

    monkeypatch.setattr(service, "_json_request", fake_json_request)
    settings = Settings(
        llm_provider="openai_compatible",
        llm_model="local-model",
        openai_api_key="local-only",
        openai_base_url="http://127.0.0.1:8081/v1",
    )
    provider = service._OpenAICompatibleJSONProvider(
        settings=settings,
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key or "",
    )
    prompt = SimpleNamespace(
        asset_payload_json={
            "template": "Return a structured RFQ draft.",
            "output_schema_json": schema,
        }
    )

    result = provider.generate("rfq_draft", {}, prompt)
    body = captured["body"]
    assert isinstance(body, dict)
    user_payload = json.loads(body["messages"][1]["content"])
    assert user_payload["output_schema"] == schema
    assert "Match the supplied output schema exactly" in body["messages"][0]["content"]
    assert "Do not coerce JSON arrays" in body["messages"][0]["content"]
    assert result == {"requirements_summary": ["one"]}


def test_rfq_prompt_declares_list_typed_fields() -> None:
    template = service.TENDER_OPERATOR_PROMPT_SPECS["rfq_draft"].template
    assert "must each be JSON arrays of strings" in template
    assert "never numbered or newline-formatted strings" in template
