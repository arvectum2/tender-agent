from fastapi import APIRouter, HTTPException, Query

from src.shared.api.dependencies import DBSession
from src.tender_research.config import load_config
from src.tender_research.rag.data_platform import (
    DataPlatformRagRetriever,
    build_data_platform_client,
)
from src.tender_research.repository import TenderRepository
from src.tender_research.similar_procurements import (
    SimilarProcurementsResponse,
    find_similar_procurements,
)

router = APIRouter(
    prefix="/api/tender-research/similar",
    tags=["tender-research"],
)


@router.get("/{registry_number}", response_model=SimilarProcurementsResponse)
def get_similar_procurements(
    registry_number: str,
    session: DBSession,
    limit: int = Query(default=10, ge=1, le=50),
) -> SimilarProcurementsResponse:
    repo = TenderRepository(session)
    with build_data_platform_client(load_config()) as platform_client:
        result = find_similar_procurements(
            repo,
            DataPlatformRagRetriever(repo, platform_client),
            registry_number=registry_number,
            limit=limit,
        )
    if result is None:
        raise HTTPException(status_code=404, detail="Tender not found")
    return result
