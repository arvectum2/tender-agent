from typing import Annotated

from fastapi import APIRouter, Query, status
from fastapi.responses import HTMLResponse

from src.modules.commercial_operator_console.schemas import (
    CommercialOperatorActionRequest,
    CommercialOperatorActionResponse,
    KanbanStatusTransitionRequest,
)
from src.modules.commercial_operator_console.service import (
    apply_kanban_status_transition,
    record_operator_action,
    render_dashboard_html,
    render_decision_html,
    render_kanban_html,
    render_report_html,
    render_requirements_html,
    render_risks_html,
    render_runtime_traces_html,
    render_tender_card_html,
)
from src.modules.status_engine.schemas import StatusHistoryEntry
from src.shared.api.dependencies import DBSession
from src.shared.enums import DealStatus

router = APIRouter(tags=["commercial-operator-console"])


@router.get("/commercial-console", response_class=HTMLResponse)
def commercial_console_dashboard(session: DBSession) -> str:
    return render_dashboard_html(session)


@router.get("/commercial-console/kanban", response_class=HTMLResponse)
def commercial_console_kanban(
    session: DBSession,
    status_filter: Annotated[DealStatus | None, Query(alias="status")] = None,
    priority_bucket: str | None = None,
    customer_name: str | None = None,
    procurement_number: str | None = None,
    q: str | None = None,
) -> str:
    return render_kanban_html(
        session,
        status_filter=status_filter,
        priority_bucket=priority_bucket,
        customer_name=customer_name,
        procurement_number=procurement_number,
        search=q,
    )


@router.post(
    "/commercial-console/kanban/deals/{deal_id}/status",
    response_model=StatusHistoryEntry,
)
def commercial_console_kanban_status(
    deal_id: str,
    payload: KanbanStatusTransitionRequest,
    session: DBSession,
) -> StatusHistoryEntry:
    history = apply_kanban_status_transition(session, deal_id, payload)
    return StatusHistoryEntry.model_validate(history)


@router.get("/commercial-console/deals/{deal_id}", response_class=HTMLResponse)
def commercial_console_tender_card(deal_id: str, session: DBSession) -> str:
    return render_tender_card_html(session, deal_id)


@router.get("/commercial-console/deals/{deal_id}/report", response_class=HTMLResponse)
def commercial_console_report(deal_id: str, session: DBSession) -> str:
    return render_report_html(session, deal_id)


@router.get("/commercial-console/deals/{deal_id}/requirements", response_class=HTMLResponse)
def commercial_console_requirements(deal_id: str, session: DBSession) -> str:
    return render_requirements_html(session, deal_id)


@router.get("/commercial-console/deals/{deal_id}/risks", response_class=HTMLResponse)
def commercial_console_risks(deal_id: str, session: DBSession) -> str:
    return render_risks_html(session, deal_id)


@router.get("/commercial-console/deals/{deal_id}/runtime-traces", response_class=HTMLResponse)
def commercial_console_runtime_traces(deal_id: str, session: DBSession) -> str:
    return render_runtime_traces_html(session, deal_id)


@router.get("/commercial-console/deals/{deal_id}/decision", response_class=HTMLResponse)
def commercial_console_decision(deal_id: str, session: DBSession) -> str:
    return render_decision_html(session, deal_id)


@router.post(
    "/commercial-console/deals/{deal_id}/actions",
    response_model=CommercialOperatorActionResponse,
    status_code=status.HTTP_201_CREATED,
)
def commercial_console_action(
    deal_id: str,
    payload: CommercialOperatorActionRequest,
    session: DBSession,
) -> CommercialOperatorActionResponse:
    return record_operator_action(session, deal_id, payload)
