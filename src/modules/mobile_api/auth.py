from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select

from src.shared.api.dependencies import DBSession
from src.shared.config.settings import Settings, get_settings

PAIRING_DIGITS = 6
_MOBILE_SECRET_CONTEXT = "arvectum-mobile-auth-v1"


def resolve_mobile_auth_secret(settings: Settings) -> str | None:
    explicit = (settings.mobile_auth_secret or "").strip()
    if len(explicit) >= 32:
        return explicit

    _, pilot_password = settings.pilot_auth_credentials()
    if not pilot_password or not settings.pilot_auth_password_safe():
        return None

    material = f"{_MOBILE_SECRET_CONTEXT}:{pilot_password}".encode()
    return hashlib.sha256(material).hexdigest()


def get_mobile_auth_secret() -> str:
    secret = resolve_mobile_auth_secret(get_settings())
    if secret is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mobile auth is not configured.",
        )
    return secret


def pairing_code(
    secret: str,
    *,
    at: datetime | None = None,
    window_seconds: int = 300,
) -> str:
    moment = at or datetime.now(UTC)
    step = int(moment.timestamp()) // window_seconds
    digest = hmac.new(
        secret.encode("utf-8"),
        f"pair:{step}".encode(),
        hashlib.sha256,
    ).digest()
    value = int.from_bytes(digest[:8], "big") % (10**PAIRING_DIGITS)
    return f"{value:0{PAIRING_DIGITS}d}"


def verify_pairing_code(
    secret: str,
    candidate: str,
    *,
    at: datetime | None = None,
    window_seconds: int = 300,
) -> bool:
    clean = candidate.strip()
    if len(clean) != PAIRING_DIGITS or not clean.isdigit():
        return False
    moment = at or datetime.now(UTC)
    for offset in (-1, 0, 1):
        probe = moment + timedelta(seconds=offset * window_seconds)
        if hmac.compare_digest(
            pairing_code(secret, at=probe, window_seconds=window_seconds),
            clean,
        ):
            return True
    return False


def issue_mobile_token(
    secret: str,
    *,
    device_id: str,
    ttl_days: int = 180,
    now: datetime | None = None,
) -> tuple[str, datetime]:
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(days=ttl_days)
    payload = {
        "v": 1,
        "device_id": device_id,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    encoded_payload = _b64url(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = _b64url(
        hmac.new(
            secret.encode("utf-8"),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
    )
    return f"{encoded_payload}.{signature}", expires_at


def verify_mobile_token(
    secret: str,
    token: str,
    *,
    now: datetime | None = None,
) -> str | None:
    try:
        encoded_payload, signature = token.split(".", 1)
    except ValueError:
        return None
    expected = _b64url(
        hmac.new(
            secret.encode("utf-8"),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
    )
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(_b64url_decode(encoded_payload))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if payload.get("v") != 1:
        return None
    device_id = payload.get("device_id")
    exp = payload.get("exp")
    if not isinstance(device_id, str) or not device_id.strip() or not isinstance(exp, int):
        return None
    moment = now or datetime.now(UTC)
    if int(moment.timestamp()) >= exp:
        return None
    return device_id.strip()


def require_mobile_bearer(
    request: Request,
    secret: Annotated[str, Depends(get_mobile_auth_secret)],
    session: DBSession,
) -> str:
    auth_header = request.headers.get("Authorization") or ""
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mobile bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    device_id = verify_mobile_token(secret, token)
    if device_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired mobile bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from .models import MobileDeviceAccess

    access = session.scalar(
        select(MobileDeviceAccess).where(MobileDeviceAccess.device_id == device_id)
    )
    if access is not None and access.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mobile device access was revoked.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return device_id


MobileDeviceID = Annotated[str, Depends(require_mobile_bearer)]
MobileAuthSecret = Annotated[str, Depends(get_mobile_auth_secret)]


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding).decode("utf-8")
