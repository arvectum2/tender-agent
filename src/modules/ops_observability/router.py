from fastapi import APIRouter

from src.modules.ops_observability.schemas import OperationalSnapshot
from src.modules.ops_observability.service import build_operational_snapshot
from src.shared.api.dependencies import DBSession

router = APIRouter(prefix="/api/ops", tags=["ops-observability"])


@router.get("/observability", response_model=OperationalSnapshot)
def get_operational_snapshot(session: DBSession) -> OperationalSnapshot:
    return build_operational_snapshot(session)
