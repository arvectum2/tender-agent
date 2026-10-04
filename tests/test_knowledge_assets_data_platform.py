from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.modules.knowledge_assets import data_platform
from src.shared.errors import ConflictError


def _record(
    asset_id: str,
    *,
    title: str = "Execution lesson",
    summary: str = "Use staged acceptance before rollout.",
    asset_type: str = "execution_lesson",
):
    return SimpleNamespace(
        knowledge_asset_id=asset_id,
        asset_title=title,
        asset_type=asset_type,
        summary_text=summary,
        asset_payload_json={
            "deal_id": "DEAL-001",
            "recommendation_summary": "Stage the rollout.",
        },
    )


class FakeClient:
    def __init__(self) -> None:
        self.collections: list[dict] = []
        self.ingested: list[dict] = []
        self.search_requests: list[dict] = []
        self.search_hits: list[dict] = []
        self.exists = True
        self.closed = False

    def ensure_collection(self, **kwargs):
        self.collections.append(kwargs)
        return kwargs

    def ingest_document(self, **kwargs):
        self.ingested.append(kwargs)
        return {"chunks": 1, "embeddings": 1}

    def collection_exists(self, collection_id: str) -> bool:
        self.last_collection_id = collection_id
        return self.exists

    def search(self, **kwargs):
        self.search_requests.append(kwargs)
        return list(self.search_hits)

    def close(self) -> None:
        self.closed = True


def test_knowledge_collection_revision_changes_with_asset_content() -> None:
    first = _record("KA-001")
    collection_one = data_platform.build_knowledge_collection_id(
        "DEAL-001",
        [first],
    )

    changed = _record("KA-001", summary="Use a different staged acceptance policy.")
    collection_two = data_platform.build_knowledge_collection_id(
        "DEAL-001",
        [changed],
    )

    assert collection_one.startswith("arvectum-os:knowledge:DEAL-001:")
    assert collection_one != collection_two


def test_index_knowledge_assets_uses_deal_scoped_collection_and_canonical_ids(
    monkeypatch,
) -> None:
    records = [_record("KA-001"), _record("KA-002")]
    client = FakeClient()
    monkeypatch.setattr(data_platform, "_records_for_deal", lambda *_args: records)

    result = data_platform.index_knowledge_assets(
        object(),
        deal_id="DEAL-001",
        client=client,
    )

    assert result.records_seen == 2
    assert result.records_indexed == 2
    assert result.chunks_created == 2
    assert result.embeddings_created == 2
    assert client.collections == [
        {
            "collection_id": result.collection_id,
            "owner": "arvectum-os",
            "name": "Arvectum OS knowledge for DEAL-001",
        }
    ]
    assert [item["canonical_uri"] for item in client.ingested] == [
        "arvectum-os-knowledge://KA-001",
        "arvectum-os-knowledge://KA-002",
    ]
    assert all(item["pre_chunked"] is True for item in client.ingested)


def test_search_knowledge_assets_maps_only_current_deal_records(
    monkeypatch,
) -> None:
    records = [_record("KA-001")]
    client = FakeClient()
    client.search_hits = [
        {
            "canonical_uri": "arvectum-os-knowledge://KA-FOREIGN",
            "scores": {"fusion": 0.9},
        },
        {
            "canonical_uri": "arvectum-os-knowledge://KA-001",
            "scores": {"fusion": 0.42},
        },
    ]
    monkeypatch.setattr(data_platform, "_records_for_deal", lambda *_args: records)
    monkeypatch.setattr(
        data_platform,
        "_links_for_asset",
        lambda *_args: ("PM-001", "ARCHIVE-001"),
    )

    collection_id, hits = data_platform.search_knowledge_assets(
        object(),
        deal_id="DEAL-001",
        query="что улучшить в следующей закупке",
        limit=5,
        client=client,
    )

    assert collection_id.startswith("arvectum-os:knowledge:DEAL-001:")
    assert [hit.knowledge_asset_id for hit in hits] == ["KA-001"]
    assert hits[0].source_refs == ("PM-001", "ARCHIVE-001")
    assert client.search_requests == [
        {
            "query": "что улучшить в следующей закупке",
            "collections": [collection_id],
            "limit": 10,
            "mode": "hybrid",
        }
    ]


def test_search_knowledge_assets_fails_closed_without_current_index(
    monkeypatch,
) -> None:
    client = FakeClient()
    client.exists = False
    monkeypatch.setattr(
        data_platform,
        "_records_for_deal",
        lambda *_args: [_record("KA-001")],
    )

    with pytest.raises(ConflictError, match="not prepared"):
        data_platform.search_knowledge_assets(
            object(),
            deal_id="DEAL-001",
            query="уроки исполнения",
            client=client,
        )
