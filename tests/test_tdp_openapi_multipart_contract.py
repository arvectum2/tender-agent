"""A supported FastAPI/Pydantic version must encode required files as OpenAPI."""

from __future__ import annotations

from src.main import app


def test_operator_multipart_routes_have_serializable_required_file_schemas():
    schema = app.openapi()
    assert schema["openapi"].startswith("3.")
    for path, method, prop in (
        ("/api/demo/tender-agent/runs", "post", "files"),
        ("/api/demo/tender-agent/runs/{run_id}/files", "post", "files"),
        ("/api/demo/tender-agent/runs/{run_id}/commercial-core", "post", "catalog_file"),
    ):
        request_body = schema["paths"][path][method]["requestBody"]
        assert request_body["required"] is True
        body_ref = request_body["content"]["multipart/form-data"]["schema"]["$ref"]
        model = schema["components"]["schemas"][body_ref.rsplit("/", 1)[-1]]
        assert prop in model["required"]
        assert prop in model["properties"]
        assert "default" not in model["properties"][prop]
