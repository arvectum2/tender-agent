from fastapi import APIRouter, HTTPException, Response, status

from src.shared.api.dependencies import DBSession
from src.shared.config.settings import get_settings

from .auth import (
    MobileAuthSecret,
    MobileDeviceID,
    issue_mobile_token,
    verify_pairing_code,
)
from .schemas import (
    MobileDecisionRequest,
    MobileDeviceRegistrationRequest,
    MobileDeviceRegistrationResponse,
    MobileDigestResponse,
    MobileInboxResponse,
    MobilePairRequest,
    MobilePairResponse,
    MobilePortfolioResponse,
    MobileProcurementItemResponse,
)
from .service import (
    activate_mobile_device_access,
    build_mobile_digest,
    build_mobile_inbox,
    build_mobile_portfolio,
    get_mobile_procurement,
    record_mobile_decision,
    register_mobile_device,
    revoke_mobile_device,
)

router = APIRouter(prefix="/mobile/v1", tags=["mobile"])


@router.post("/pair", response_model=MobilePairResponse)
def mobile_pair(
    payload: MobilePairRequest,
    secret: MobileAuthSecret,
    session: DBSession,
) -> MobilePairResponse:
    settings = get_settings()
    if not verify_pairing_code(
        secret,
        payload.pairing_code,
        window_seconds=settings.mobile_pairing_window_seconds,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired pairing code.",
        )
    activate_mobile_device_access(
        session,
        device_id=payload.device_id,
        device_name=payload.device_name,
    )
    token, expires_at = issue_mobile_token(
        secret,
        device_id=payload.device_id,
        ttl_days=settings.mobile_token_ttl_days,
    )
    return MobilePairResponse(
        access_token=token,
        expires_at=expires_at,
        device_id=payload.device_id,
    )


@router.get("/inbox", response_model=MobileInboxResponse)
def mobile_inbox(
    session: DBSession,
    _device_id: MobileDeviceID,
) -> MobileInboxResponse:
    return MobileInboxResponse.model_validate(build_mobile_inbox(session))


@router.get("/digest/latest", response_model=MobileDigestResponse)
def mobile_digest_latest(
    session: DBSession,
    _device_id: MobileDeviceID,
) -> MobileDigestResponse:
    return MobileDigestResponse.model_validate(build_mobile_digest(session))


@router.get("/portfolio", response_model=MobilePortfolioResponse)
def mobile_portfolio(
    session: DBSession,
    _device_id: MobileDeviceID,
) -> MobilePortfolioResponse:
    return MobilePortfolioResponse.model_validate(build_mobile_portfolio(session))


@router.get("/procurements/{deal_id}", response_model=MobileProcurementItemResponse)
def mobile_procurement(
    deal_id: str,
    session: DBSession,
    _device_id: MobileDeviceID,
) -> MobileProcurementItemResponse:
    return MobileProcurementItemResponse.model_validate(
        get_mobile_procurement(session, deal_id)
    )


@router.post(
    "/procurements/{deal_id}/decision",
    response_model=MobileProcurementItemResponse,
)
def mobile_decision(
    deal_id: str,
    payload: MobileDecisionRequest,
    session: DBSession,
    device_id: MobileDeviceID,
) -> MobileProcurementItemResponse:
    return MobileProcurementItemResponse.model_validate(
        record_mobile_decision(
            session,
            deal_id,
            payload,
            actor_ref=f"ios:{device_id}",
        )
    )


@router.post("/devices", response_model=MobileDeviceRegistrationResponse)
def mobile_register_device(
    payload: MobileDeviceRegistrationRequest,
    session: DBSession,
    device_id: MobileDeviceID,
) -> MobileDeviceRegistrationResponse:
    try:
        result = register_mobile_device(
            session,
            device_id=device_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return MobileDeviceRegistrationResponse.model_validate(result)


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def mobile_revoke_device(
    device_id: str,
    session: DBSession,
    authenticated_device_id: MobileDeviceID,
) -> Response:
    if device_id != authenticated_device_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A mobile device may revoke only its own registration.",
        )
    revoke_mobile_device(session, device_id=device_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
