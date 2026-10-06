from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import quote

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.deal_registry.models import Deal
from src.modules.event_log.models import DecisionRecord
from src.shared.config.settings import Settings, get_settings
from src.shared.db.base import utcnow

from .models import MobileDeviceRegistration, MobilePushDelivery

MobilePushEvent = Literal[
    "REPORT_READY",
    "DEFERRED_DUE",
    "PROCUREMENT_CHANGED",
    "DEADLINE_RISK",
    "OUTCOME_AVAILABLE",
]

_APNS_TOKEN_RE = re.compile(r"^[0-9a-fA-F]{32,256}$")
_APNS_SANDBOX = "https://api.sandbox.push.apple.com"
_APNS_PRODUCTION = "https://api.push.apple.com"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class APNsSendResult:
    ok: bool
    status_code: int
    apns_id: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class PushDispatchSummary:
    event_type: str
    deal_id: str | None
    attempted: int
    sent: int
    duplicate: int
    pending_configuration: int
    failed: int


def normalize_apns_token(value: str) -> str:
    token = "".join(value.split()).lower()
    if not _APNS_TOKEN_RE.fullmatch(token):
        raise ValueError("Invalid APNs device token.")
    return token


def procurement_deep_link(deal_id: str) -> str:
    return f"tenderagent://procurement/{quote(deal_id, safe='')}"


def digest_deep_link() -> str:
    return "tenderagent://digest"


def build_mobile_push_payload(
    *,
    event_type: MobilePushEvent,
    title: str,
    body: str,
    deal_id: str | None = None,
) -> dict:
    deep_link = procurement_deep_link(deal_id) if deal_id else digest_deep_link()
    safe_title = title.strip()[:160]
    safe_body = body.strip()[:1200]
    payload: dict = {
        "aps": {
            "alert": {"title": safe_title, "body": safe_body},
            "sound": "default",
            "thread-id": "tender-agent",
        },
        "event_type": event_type,
        "deep_link": deep_link,
    }
    if deal_id:
        payload["deal_id"] = deal_id
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > 4096:
        raise ValueError("APNs payload exceeds the 4096-byte alert payload limit.")
    return payload


def apns_is_configured(settings: Settings) -> bool:
    return bool(
        settings.mobile_apns_enabled
        and settings.mobile_apns_team_id
        and settings.mobile_apns_key_id
        and settings.mobile_apns_private_key_path
        and settings.mobile_apns_bundle_id
    )


def _provider_jwt(settings: Settings) -> str:
    if not apns_is_configured(settings):
        raise RuntimeError("APNs provider credentials are not configured.")
    key_path = Path(str(settings.mobile_apns_private_key_path)).expanduser()
    private_key = key_path.read_text(encoding="utf-8")
    return jwt.encode(
        {"iss": settings.mobile_apns_team_id, "iat": int(time.time())},
        private_key,
        algorithm="ES256",
        headers={"kid": settings.mobile_apns_key_id},
    )


def send_apns_notification(
    *,
    token: str,
    environment: str,
    payload: dict,
    settings: Settings | None = None,
    transport: httpx.BaseTransport | None = None,
) -> APNsSendResult:
    settings = settings or get_settings()
    token = normalize_apns_token(token)
    if environment not in {"sandbox", "production"}:
        raise ValueError("APNs environment must be sandbox or production.")
    provider_token = _provider_jwt(settings)
    base_url = _APNS_SANDBOX if environment == "sandbox" else _APNS_PRODUCTION
    headers = {
        "authorization": f"bearer {provider_token}",
        "apns-topic": settings.mobile_apns_bundle_id,
        "apns-push-type": "alert",
        "apns-priority": "10",
        "content-type": "application/json",
    }
    with httpx.Client(
        http2=True,
        timeout=settings.mobile_apns_timeout_seconds,
        transport=transport,
    ) as client:
        response = client.post(
            f"{base_url}/3/device/{token}",
            headers=headers,
            json=payload,
        )
    apns_id = response.headers.get("apns-id")
    reason = None
    if response.content:
        try:
            reason = str(response.json().get("reason") or "") or None
        except (ValueError, AttributeError):
            reason = "invalid_apns_response"
    return APNsSendResult(
        ok=200 <= response.status_code < 300,
        status_code=response.status_code,
        apns_id=apns_id,
        reason=reason,
    )


def _delivery_key(
    *,
    device_id: str,
    event_type: str,
    deal_id: str | None,
    source_key: str,
) -> str:
    raw = json.dumps(
        [device_id, event_type, deal_id or "", source_key],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def dispatch_mobile_push_event(
    session: Session,
    *,
    event_type: MobilePushEvent,
    source_key: str,
    title: str,
    body: str,
    deal_id: str | None = None,
    settings: Settings | None = None,
    sender: Callable[[MobileDeviceRegistration, dict], APNsSendResult] | None = None,
) -> PushDispatchSummary:
    settings = settings or get_settings()
    payload = build_mobile_push_payload(
        event_type=event_type,
        title=title,
        body=body,
        deal_id=deal_id,
    )
    registrations = list(
        session.scalars(
            select(MobileDeviceRegistration)
            .where(
                MobileDeviceRegistration.is_enabled.is_(True),
                MobileDeviceRegistration.apns_token != "",
            )
            .order_by(MobileDeviceRegistration.registered_at.asc())
        )
    )
    attempted = sent = duplicate = pending_configuration = failed = 0

    for registration in registrations:
        key = _delivery_key(
            device_id=registration.device_id,
            event_type=event_type,
            deal_id=deal_id,
            source_key=source_key,
        )
        delivery = session.scalar(
            select(MobilePushDelivery).where(MobilePushDelivery.delivery_key == key)
        )
        if delivery is not None and delivery.status == "SENT":
            duplicate += 1
            continue
        if delivery is None:
            delivery = MobilePushDelivery(
                delivery_key=key,
                device_id=registration.device_id,
                event_type=event_type,
                deal_id=deal_id,
                source_key=source_key,
                payload_json=payload,
                status="PENDING",
            )
            session.add(delivery)
            session.flush()
        else:
            delivery.payload_json = payload

        if sender is None and not apns_is_configured(settings):
            delivery.status = "PENDING_CONFIGURATION"
            delivery.updated_at = utcnow()
            session.add(delivery)
            pending_configuration += 1
            continue

        attempted += 1
        delivery.attempts += 1
        delivery.updated_at = utcnow()
        try:
            result = (
                sender(registration, payload)
                if sender is not None
                else send_apns_notification(
                    token=registration.apns_token,
                    environment=registration.apns_environment,
                    payload=payload,
                    settings=settings,
                )
            )
        except Exception as exc:  # noqa: BLE001 - isolated notification transport
            delivery.status = "FAILED"
            delivery.error_code = type(exc).__name__
            failed += 1
        else:
            delivery.apns_id = result.apns_id
            delivery.error_code = result.reason
            if result.ok:
                delivery.status = "SENT"
                delivery.sent_at = datetime.now(UTC)
                sent += 1
            else:
                delivery.status = "FAILED"
                failed += 1
                if result.status_code == 410 or result.reason in {"BadDeviceToken", "Unregistered"}:
                    registration.is_enabled = False
                    registration.apns_token = ""
                    registration.updated_at = utcnow()
                    session.add(registration)
        session.add(delivery)

    session.commit()
    return PushDispatchSummary(
        event_type=event_type,
        deal_id=deal_id,
        attempted=attempted,
        sent=sent,
        duplicate=duplicate,
        pending_configuration=pending_configuration,
        failed=failed,
    )


def dispatch_due_deferred_notifications(
    session: Session,
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
    sender: Callable[[MobileDeviceRegistration, dict], APNsSendResult] | None = None,
) -> list[PushDispatchSummary]:
    now = now or datetime.now(UTC)
    rows = list(
        session.scalars(
            select(DecisionRecord)
            .where(DecisionRecord.decision_code == "PORTFOLIO_BID_DECISION")
            .order_by(DecisionRecord.created_at.asc(), DecisionRecord.id.asc())
        )
    )
    latest_by_deal = {row.deal_id: row for row in rows}
    deals = {
        deal.deal_id: deal
        for deal in session.scalars(
            select(Deal).where(Deal.deal_id.in_(list(latest_by_deal)))
        )
    } if latest_by_deal else {}

    summaries: list[PushDispatchSummary] = []
    for deal_id, record in latest_by_deal.items():
        payload = record.payload_json or {}
        if str(payload.get("mobile_action") or "").upper() != "DEFER":
            continue
        raw_due = payload.get("deferred_until")
        if not isinstance(raw_due, str):
            continue
        try:
            due = datetime.fromisoformat(raw_due)
        except ValueError:
            continue
        if due.tzinfo is None:
            due = due.replace(tzinfo=UTC)
        if due > now:
            continue
        deal = deals.get(deal_id)
        title = "Отложенное решение снова требует внимания"
        body = deal.title if deal is not None else f"Закупка {deal_id}"
        summaries.append(
            dispatch_mobile_push_event(
                session,
                event_type="DEFERRED_DUE",
                source_key=f"defer:{record.id}:{due.isoformat()}",
                title=title,
                body=body,
                deal_id=deal_id,
                settings=settings,
                sender=sender,
            )
        )
    return summaries


def safely_dispatch_mobile_push_event(
    session: Session,
    **kwargs,
) -> PushDispatchSummary | None:
    """Dispatch a push without allowing notification failures to roll back domain state."""
    try:
        return dispatch_mobile_push_event(session, **kwargs)
    except Exception:
        session.rollback()
        logger.exception("Mobile push dispatch failed without mutating canonical domain state")
        return None


def safely_dispatch_procurement_changed(
    session: Session,
    *,
    procurement_number: str,
    source_key: str,
    body: str,
) -> PushDispatchSummary | None:
    """Resolve a canonical deal and emit a change notification without affecting monitoring."""
    try:
        deal = session.scalar(
            select(Deal).where(Deal.procurement_number == procurement_number)
        )
        if deal is None:
            return None
        return dispatch_mobile_push_event(
            session,
            event_type="PROCUREMENT_CHANGED",
            source_key=source_key,
            title="Изменения в закупке",
            body=body or deal.title,
            deal_id=deal.deal_id,
        )
    except Exception:
        session.rollback()
        logger.exception("Procurement change push failed without changing monitoring state")
        return None
