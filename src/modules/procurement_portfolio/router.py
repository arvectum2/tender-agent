from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from src.shared.api.dependencies import DBSession

from .schemas import (
    CreatePortfolioProcurementRequest,
    ProcurementPortfolioItemResponse,
    ProcurementPortfolioResponse,
    RecordPortfolioDecisionRequest,
)
from .service import (
    build_procurement_portfolio,
    create_portfolio_procurement,
    record_portfolio_decision,
)
from .ui import render_procurement_portfolio_html

router = APIRouter(tags=["procurement-portfolio"])


@router.post(
    "/procurement-portfolio",
    response_model=ProcurementPortfolioItemResponse,
    status_code=201,
)
def create_procurement_portfolio_item(
    payload: CreatePortfolioProcurementRequest,
    session: DBSession,
) -> ProcurementPortfolioItemResponse:
    return ProcurementPortfolioItemResponse.model_validate(
        create_portfolio_procurement(session, payload)
    )


@router.get("/procurement-portfolio", response_model=ProcurementPortfolioResponse)
def get_procurement_portfolio(
    session: DBSession,
    decision: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    submitted: bool | None = Query(default=None),
    q: str | None = Query(default=None),
) -> ProcurementPortfolioResponse:
    return ProcurementPortfolioResponse.model_validate(
        build_procurement_portfolio(
            session,
            decision=decision,
            outcome=outcome,
            submitted=submitted,
            q=q,
        )
    )


@router.post(
    "/procurement-portfolio/{deal_id}/decision",
    response_model=ProcurementPortfolioItemResponse,
)
def record_procurement_portfolio_decision(
    deal_id: str,
    payload: RecordPortfolioDecisionRequest,
    session: DBSession,
) -> ProcurementPortfolioItemResponse:
    return ProcurementPortfolioItemResponse.model_validate(
        record_portfolio_decision(session, deal_id=deal_id, payload=payload)
    )


@router.get("/procurement-portfolio/ui", response_class=HTMLResponse, include_in_schema=False)
def procurement_portfolio_ui() -> HTMLResponse:
    return HTMLResponse(render_procurement_portfolio_html())
