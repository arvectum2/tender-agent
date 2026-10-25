"""MI005 report download API reusing existing SaaS foundation Bearer + legal gates."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from src.modules.market_intelligence.report_delivery import (
    ReportAccessError,
    ReportBundleStore,
)
from src.modules.saas_foundation.router import Member
from src.modules.saas_foundation.service import legal_required, role_required
from src.shared.api.dependencies import DBSession
from src.shared.config.settings import get_settings

router = APIRouter(prefix="/api/saas/market-intelligence", tags=["market-intelligence"])


def _store() -> ReportBundleStore:
    settings = get_settings()
    if not settings.market_intelligence_report_delivery_enabled:
        raise HTTPException(404, "Market Intelligence delivery disabled")
    return ReportBundleStore(
        Path(settings.arvectum_data_dir) / "market_intelligence_reports"
    )


@router.get("/reports")
def list_my_reports(
    principal: Member,
    session: DBSession,
    store: Annotated[ReportBundleStore, Depends(_store)],
) -> dict:
    role_required(principal, "owner", "admin", "analyst", "viewer")
    legal_required(session, principal)
    return {
        "reports": store.list_reports(principal.tenant_id),
        "tenant_id": principal.tenant_id,
        "national_market_state": "NOT_ESTIMATED",
        "read_only": True,
    }


@router.get("/reports/{report_id}/{fmt}")
def download_my_report(
    report_id: str,
    fmt: Literal["html", "csv", "json"],
    principal: Member,
    session: DBSession,
    store: Annotated[ReportBundleStore, Depends(_store)],
) -> Response:
    role_required(principal, "owner", "admin", "analyst", "viewer")
    legal_required(session, principal)
    try:
        content, mime = store.read(principal.tenant_id, report_id, fmt)
    except ReportAccessError as exc:
        raise HTTPException(404, "Report unavailable") from exc
    return Response(
        content, media_type=mime,
        headers={
            "Cache-Control": "private, no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Content-Disposition": (
                f'attachment; filename="market-intelligence-{report_id}.{fmt}"'
            ),
        },
    )
