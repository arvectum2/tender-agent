from fastapi import APIRouter, Query

from src.shared.api.dependencies import DBSession

from .schemas import AdapterStatus, IntegrationOutboxResponse
from .service import list_outbox

router = APIRouter(prefix="/integration-outbox", tags=["integration-outbox"])
@router.get("/events", response_model=list[IntegrationOutboxResponse])
def events(session: DBSession, tenant_id: str | None = Query(default=None), event_type: str | None = Query(default=None)):
    return list_outbox(session, tenant_id=tenant_id, event_type=event_type)
@router.get("/adapter-status", response_model=AdapterStatus)
def adapter_status() -> AdapterStatus:
    return AdapterStatus()
