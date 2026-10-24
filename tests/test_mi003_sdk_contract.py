"""Contract smoke with the *real* Data Platform Python SDK, mock HTTP transport."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import yaml
from arvectum_data_client import DataPlatformClient

from src.modules.market_intelligence.portfolio_pipeline import (
    ingest_supplier,
    search_demand,
)


def test_real_sdk_collection_ingest_and_hybrid_query_contract():
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append({
            "method": request.method,
            "path": request.url.path,
            "body": request.content,
        })
        if request.method == "GET" and request.url.path.startswith("/v1/collections/"):
            return httpx.Response(404, json={"detail": "not found"})
        if request.method == "POST" and request.url.path == "/v1/collections":
            payload = json.loads(request.content)
            assert payload["owner"] == "tender-agent:tenant_01"
            return httpx.Response(200, json=payload)
        if request.method == "POST" and request.url.path == "/v1/ingest/document":
            assert b"STATCOM" in request.content
            assert b"mi-intake" in request.content
            return httpx.Response(200, json={
                "resource_id": "supplier-r", "document_id": "supplier-d",
                "extraction_status": "extracted",
            })
        if request.method == "POST" and request.url.path == "/v1/search":
            body = json.loads(request.content)
            assert body["collections"] == ["tenant_01_eis_223"]
            assert body["mode"] == "hybrid"
            assert body["query"]
            return httpx.Response(200, json={"hits": [{
                "chunk_id": "eis-chunk", "document_id": "eis-doc",
                "resource_id": "eis-resource",
                "canonical_uri": "https://zakupki.gov.ru/purchase/123",
                "title": "Схема модернизации ПС 220 кВ",
                "preview": "Монтаж СТАТКОМ 5 МВАр",
                "text": "Технические требования: монтаж СТАТКОМ 5 МВАр",
                "scores": {"fusion": 0.2, "lexical": 0.4, "vector": 0.3},
                "metadata": {"source_sha256": "c" * 64},
                "evidence": [],
            }]})
        raise AssertionError(f"unexpected request {request.method} {request.url}")

    transport = httpx.MockTransport(handle)
    http = httpx.Client(base_url="https://dp.internal", transport=transport)
    sdk = DataPlatformClient(base_url="https://dp.internal", client=http)
    intake = ingest_supplier(
        sdk, tenant_id="tenant_01", run_id="run_01",
        company_name="Вендор", text="Поставляем STATCOM и фильтры гармоник"
    )
    assert intake["portfolio_collection"].startswith("mi-portfolio-")
    ontology = yaml.safe_load(
        Path("data/market_intelligence/power_quality/ontology.v1.yaml").read_text(
            encoding="utf-8"
        )
    )
    search = search_demand(
        sdk, tenant_id="tenant_01",
        source_collections=["tenant_01_eis_223"],
        authorized_collection_ids={"tenant_01_eis_223"},
        families=["statcom"], ontology=ontology,
        reviewed_source_hashes={"https://zakupki.gov.ru/purchase/123": "c" * 64},
    )
    assert len(search["candidate_hits"]) == 1
    assert search["candidate_hits"][0]["source_grade"] == "reviewed_source_manifest"
    assert search["candidate_hits"][0]["award_verified"] is False
    assert [r["path"] for r in calls] == [
        f"/v1/collections/{intake['portfolio_collection']}",
        "/v1/collections", "/v1/ingest/document", "/v1/search",
    ]
    sdk.close()
    http.close()
