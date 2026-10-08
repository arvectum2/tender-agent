from fastapi import APIRouter, HTTPException, Query

from src.shared.api.dependencies import DBSession
from src.tender_research.config import load_config
from src.tender_research.historical_prices import (
    HistoricalPriceResponse,
    build_historical_price_range,
)
from src.tender_research.rag.data_platform import (
    DataPlatformRagRetriever,
    build_data_platform_client,
)
from src.tender_research.repository import TenderRepository

router = APIRouter(
    prefix="/api/tender-research/historical-prices",
    tags=["tender-research"],
)


@router.get("/{registry_number}", response_model=HistoricalPriceResponse)
def get_historical_price_range(
    registry_number: str,
    session: DBSession,
    limit: int = Query(default=10, ge=2, le=25),
) -> HistoricalPriceResponse:
    repo = TenderRepository(session)
    with build_data_platform_client(load_config()) as platform_client:
        result = build_historical_price_range(
            repo,
            DataPlatformRagRetriever(repo, platform_client),
            registry_number=registry_number,
            observation_limit=limit,
        )
    if result is None:
        raise HTTPException(status_code=404, detail="Tender not found")
    return result
