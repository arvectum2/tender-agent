from fastapi import APIRouter

from src.modules.contract_execution_analytics.schemas import (
    ContractExecutionAnalyticsResponse,
)
from src.modules.contract_execution_analytics.service import (
    build_contract_execution_analytics,
)
from src.shared.api.dependencies import DBSession

router = APIRouter(
    prefix="/contract-execution-analytics",
    tags=["contract-execution-analytics"],
)


@router.get("/deals/{deal_id}", response_model=ContractExecutionAnalyticsResponse)
def get_contract_execution_analytics(
    deal_id: str,
    session: DBSession,
) -> ContractExecutionAnalyticsResponse:
    return build_contract_execution_analytics(session, deal_id)
