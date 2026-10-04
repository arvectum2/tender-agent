from fastapi import APIRouter, HTTPException, Query, status

from src.modules.knowledge_assets.data_platform import (
    index_knowledge_assets,
    search_knowledge_assets,
)
from src.modules.knowledge_assets.schemas import (
    BuildKnowledgeAssetRequest,
    IndexKnowledgeAssetsRequest,
    KnowledgeAssetIndexResponse,
    KnowledgeAssetLinkResponse,
    KnowledgeAssetRecordResponse,
    KnowledgeAssetSearchHitResponse,
    KnowledgeAssetSearchResponse,
    KnowledgeAssetSetResponse,
    SearchKnowledgeAssetsRequest,
)
from src.modules.knowledge_assets.service import (
    build_knowledge_asset,
    get_knowledge_asset_record,
    get_knowledge_asset_set,
    list_knowledge_asset_sets,
)
from src.shared.api.dependencies import DBSession
from src.shared.data_platform import DataPlatformError

router = APIRouter(tags=["knowledge-assets"])


def _to_record_response(result: tuple) -> KnowledgeAssetRecordResponse:
    record, links = result
    return KnowledgeAssetRecordResponse(
        knowledge_asset_id=record.knowledge_asset_id,
        asset_title=record.asset_title,
        asset_type=record.asset_type,
        summary_text=record.summary_text,
        asset_payload_json=record.asset_payload_json,
        created_at=record.created_at,
        updated_at=record.updated_at,
        links=[KnowledgeAssetLinkResponse.model_validate(item) for item in links],
    )


def _to_set_response(result: tuple) -> KnowledgeAssetSetResponse:
    asset_set, records = result
    return KnowledgeAssetSetResponse(
        knowledge_asset_set_id=asset_set.knowledge_asset_set_id,
        deal_id=asset_set.deal_id,
        postmortem_set_id=asset_set.postmortem_set_id,
        archive_export_set_id=asset_set.archive_export_set_id,
        dashboard_snapshot_set_id=asset_set.dashboard_snapshot_set_id,
        knowledge_status=asset_set.knowledge_status,
        created_at=asset_set.created_at,
        updated_at=asset_set.updated_at,
        records=[_to_record_response(item) for item in records],
    )


@router.post("/knowledge-assets/build", response_model=KnowledgeAssetSetResponse, status_code=status.HTTP_201_CREATED)
def build_knowledge_asset_route(
    payload: BuildKnowledgeAssetRequest,
    session: DBSession,
) -> KnowledgeAssetSetResponse:
    asset_set = build_knowledge_asset(session, payload)
    return _to_set_response(get_knowledge_asset_set(session, asset_set.knowledge_asset_set_id))


@router.get("/knowledge-assets/{knowledge_asset_set_id}", response_model=KnowledgeAssetSetResponse)
def get_knowledge_asset_set_route(
    knowledge_asset_set_id: str,
    session: DBSession,
) -> KnowledgeAssetSetResponse:
    return _to_set_response(get_knowledge_asset_set(session, knowledge_asset_set_id))


@router.get("/knowledge-assets", response_model=list[KnowledgeAssetSetResponse])
def list_knowledge_asset_sets_route(
    session: DBSession,
    deal_id: str | None = Query(default=None),
) -> list[KnowledgeAssetSetResponse]:
    return [_to_set_response(item) for item in list_knowledge_asset_sets(session, deal_id=deal_id)]


@router.get("/knowledge-assets/records/{knowledge_asset_id}", response_model=KnowledgeAssetRecordResponse)
def get_knowledge_asset_record_route(
    knowledge_asset_id: str,
    session: DBSession,
) -> KnowledgeAssetRecordResponse:
    return _to_record_response(get_knowledge_asset_record(session, knowledge_asset_id))


@router.post(
    "/knowledge-assets/index",
    response_model=KnowledgeAssetIndexResponse,
)
def index_knowledge_assets_route(
    payload: IndexKnowledgeAssetsRequest,
    session: DBSession,
) -> KnowledgeAssetIndexResponse:
    try:
        result = index_knowledge_assets(session, deal_id=payload.deal_id)
    except DataPlatformError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return KnowledgeAssetIndexResponse(
        collection_id=result.collection_id,
        records_seen=result.records_seen,
        records_indexed=result.records_indexed,
        chunks_created=result.chunks_created,
        embeddings_created=result.embeddings_created,
    )


@router.post(
    "/knowledge-assets/search",
    response_model=KnowledgeAssetSearchResponse,
)
def search_knowledge_assets_route(
    payload: SearchKnowledgeAssetsRequest,
    session: DBSession,
) -> KnowledgeAssetSearchResponse:
    try:
        collection_id, hits = search_knowledge_assets(
            session,
            deal_id=payload.deal_id,
            query=payload.query,
            limit=payload.limit,
        )
    except DataPlatformError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return KnowledgeAssetSearchResponse(
        collection_id=collection_id,
        hits=[
            KnowledgeAssetSearchHitResponse(
                knowledge_asset_id=hit.knowledge_asset_id,
                asset_title=hit.asset_title,
                asset_type=hit.asset_type,
                summary_text=hit.summary_text,
                score=hit.score,
                source_refs=list(hit.source_refs),
            )
            for hit in hits
        ],
    )
