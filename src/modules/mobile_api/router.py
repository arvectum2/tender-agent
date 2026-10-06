from fastapi import APIRouter

from src.shared.api.dependencies import DBSession

from .schemas import (
    MobileDecisionRequest,
    MobileInboxResponse,
    MobilePortfolioResponse,
    MobileProcurementItemResponse,
)
from .service import (
    build_mobile_inbox,
    build_mobile_portfolio,
    get_mobile_procurement,
    record_mobile_decision,
)

router = APIRouter(prefix="/mobile/v1", tags=["mobile"])


@router.get("/inbox", response_model=MobileInboxResponse)
def mobile_inbox(session: DBSession) -> MobileInboxResponse:
    return MobileInboxResponse.model_validate(build_mobile_inbox(session))


@router.get("/portfolio", response_model=MobilePortfolioResponse)
def mobile_portfolio(session: DBSession) -> MobilePortfolioResponse:
    return MobilePortfolioResponse.model_validate(build_mobile_portfolio(session))


@router.get("/procurements/{deal_id}", response_model=MobileProcurementItemResponse)
def mobile_procurement(deal_id: str, session: DBSession) -> MobileProcurementItemResponse:
    return MobileProcurementItemResponse.model_validate(get_mobile_procurement(session, deal_id))


@router.post("/procurements/{deal_id}/decision", response_model=MobileProcurementItemResponse)
def mobile_decision(
    deal_id: str,
    payload: MobileDecisionRequest,
    session: DBSession,
) -> MobileProcurementItemResponse:
    return MobileProcurementItemResponse.model_validate(
        record_mobile_decision(session, deal_id, payload)
    )
