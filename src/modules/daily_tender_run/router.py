from fastapi import APIRouter, Query, status

from src.modules.daily_tender_run.schemas import (
    DailyTenderRunResponse,
    StartDailyTenderRunRequest,
)
from src.modules.daily_tender_run.service import (
    create_daily_tender_run,
    execute_daily_tender_run,
    get_daily_tender_run,
    get_latest_daily_tender_run,
    to_run_response,
)
from src.shared.api.dependencies import DBSession

router = APIRouter(prefix="/api/daily-tender-runs", tags=["daily-tender-runs"])


@router.post("", response_model=DailyTenderRunResponse, status_code=status.HTTP_201_CREATED)
def start_daily_tender_run(
    payload: StartDailyTenderRunRequest,
    session: DBSession,
) -> DailyTenderRunResponse:
    run = create_daily_tender_run(session, payload)
    return to_run_response(session, run)


@router.get("/latest", response_model=DailyTenderRunResponse | None)
def latest_daily_tender_run(
    session: DBSession,
    profile_id: str | None = Query(default=None),
) -> DailyTenderRunResponse | None:
    run = get_latest_daily_tender_run(session, profile_id=profile_id)
    return to_run_response(session, run) if run else None


@router.get("/{run_id}", response_model=DailyTenderRunResponse)
def read_daily_tender_run(run_id: str, session: DBSession) -> DailyTenderRunResponse:
    return to_run_response(session, get_daily_tender_run(session, run_id))


@router.post("/{run_id}/resume", response_model=DailyTenderRunResponse)
def resume_daily_tender_run(
    run_id: str,
    session: DBSession,
    retry_failed: bool = Query(default=False),
) -> DailyTenderRunResponse:
    run = execute_daily_tender_run(session, run_id, retry_failed=retry_failed)
    return to_run_response(session, run)


@router.get("/{run_id}/digest")
def read_daily_tender_digest(run_id: str, session: DBSession) -> dict:
    run = get_daily_tender_run(session, run_id)
    return dict(run.digest_json or {})
