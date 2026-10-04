from datetime import datetime

from pydantic import Field

from src.shared.enums import KnowledgeAssetStatus, KnowledgeAssetType
from src.shared.types.common import APIModel


class BuildKnowledgeAssetRequest(APIModel):
    deal_id: str


class KnowledgeAssetLinkResponse(APIModel):
    source_ref: str
    created_at: datetime


class KnowledgeAssetRecordResponse(APIModel):
    knowledge_asset_id: str
    asset_title: str
    asset_type: KnowledgeAssetType
    summary_text: str
    asset_payload_json: dict
    created_at: datetime
    updated_at: datetime
    links: list[KnowledgeAssetLinkResponse]


class KnowledgeAssetSetResponse(APIModel):
    knowledge_asset_set_id: str
    deal_id: str
    postmortem_set_id: str
    archive_export_set_id: str | None
    dashboard_snapshot_set_id: str | None
    knowledge_status: KnowledgeAssetStatus
    created_at: datetime
    updated_at: datetime
    records: list[KnowledgeAssetRecordResponse]


class IndexKnowledgeAssetsRequest(APIModel):
    deal_id: str = Field(min_length=1)


class KnowledgeAssetIndexResponse(APIModel):
    collection_id: str
    records_seen: int
    records_indexed: int
    chunks_created: int
    embeddings_created: int


class SearchKnowledgeAssetsRequest(APIModel):
    deal_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)


class KnowledgeAssetSearchHitResponse(APIModel):
    knowledge_asset_id: str
    asset_title: str
    asset_type: str
    summary_text: str
    score: float
    source_refs: list[str]


class KnowledgeAssetSearchResponse(APIModel):
    collection_id: str
    hits: list[KnowledgeAssetSearchHitResponse]
