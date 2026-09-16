from fastapi import APIRouter, Query, status
from src.shared.api.dependencies import DBSession
from .schemas import AlertEvent, FeedEventResponse, WatchResponse, WatchTarget
from .service import check_watch, create_watch, list_feed

router = APIRouter(prefix="/procurement-monitoring", tags=["procurement-monitoring"])

@router.post("/watches", response_model=WatchResponse, status_code=status.HTTP_201_CREATED)
def create_watch_route(payload: WatchTarget, session: DBSession) -> WatchResponse:
    return WatchResponse.model_validate(create_watch(session, payload))

@router.post("/watches/{watch_id}/check", response_model=AlertEvent | None)
def check_watch_route(watch_id: str, session: DBSession) -> AlertEvent | None:
    return check_watch(session, watch_id)

@router.get("/feed", response_model=list[FeedEventResponse])
def list_feed_route(session: DBSession, watch_id: str | None = Query(default=None)) -> list[FeedEventResponse]:
    return [FeedEventResponse(id=row.id, created_at=row.created_at, **row.payload) for row in list_feed(session, watch_id)]
