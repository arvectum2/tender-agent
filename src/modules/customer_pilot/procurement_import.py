"""Bounded EIS registry-number handoff. URL contents are identifiers, never tender facts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlsplit
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.modules.customer_pilot.models import (
    PilotAuditEvent,
    PilotProject,
    ProcurementCase,
)

_NUMBER = re.compile(r"[0-9]{19,20}\Z")
_ALLOWED_HOSTS = frozenset({"zakupki.gov.ru", "www.zakupki.gov.ru"})
_ALLOWED_PARAMETERS = frozenset({"regNumber"})
_ALLOWED_SURFACES = frozenset({"manual", "browser", "share"})


@dataclass(frozen=True)
class ImportIdentifier:
    procurement_number: str
    input_kind: str
    source_url: str | None
    normalization_method: str


def normalize_procurement_input(raw: str) -> ImportIdentifier:
    value = raw.strip()
    if _NUMBER.fullmatch(value):
        return ImportIdentifier(value, "registry_number", None, "exact_registry_number")
    if len(value) > 2048 or not value.startswith("https://"):
        raise ValueError("Unsupported procurement identifier")
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in _ALLOWED_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or parsed.fragment
            or not parsed.path.startswith("/epz/order/notice/")
            or not parsed.path.endswith("/view/common-info.html")
        ):
            raise ValueError("Unsupported EIS notice URL")
        params = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Unsupported EIS notice URL") from exc
    numbers = [v for k, v in params if k in _ALLOWED_PARAMETERS]
    if len(numbers) != 1 or not _NUMBER.fullmatch(numbers[0]):
        raise ValueError("Missing or ambiguous registry number")
    # Reject other possible registry aliases instead of silently selecting one.
    if any(
        k.lower() in {"regnumber", "registrationnumber", "purchase_number", "number"}
        and k != "regNumber"
        for k, _ in params
    ):
        raise ValueError("Ambiguous registry number")
    return ImportIdentifier(numbers[0], "eis_url", value, "eis_regNumber_query")


def import_procurement_case(
    session: Session, *, customer_id: str, project_id: str, raw_input: str, surface: str
) -> dict:
    if surface not in _ALLOWED_SURFACES:
        raise HTTPException(422, "Unsupported handoff surface")
    try:
        identity = normalize_procurement_input(raw_input)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    project = session.scalar(
        select(PilotProject).where(
            PilotProject.id == project_id, PilotProject.customer_id == customer_id
        )
    )
    if project is None:
        raise HTTPException(404, "Project not found")
    lookup = (
        ProcurementCase.customer_id == customer_id,
        ProcurementCase.project_id == project_id,
        ProcurementCase.procurement_number == identity.procurement_number,
    )
    existing = session.scalar(select(ProcurementCase).where(*lookup))
    created = existing is None
    if existing is None:
        # Nested transaction preserves caller session after a competing UNIQUE insert.
        try:
            with session.begin_nested():
                existing = ProcurementCase(
                    customer_id=customer_id,
                    project_id=project_id,
                    procurement_number=identity.procurement_number,
                    artifact_key=f"c_{uuid4().hex}",
                )
                session.add(existing)
                session.flush()
        except IntegrityError:
            existing = session.scalar(select(ProcurementCase).where(*lookup))
            if existing is None:
                raise
            created = False
    session.add(
        PilotAuditEvent(
            customer_id=customer_id,
            project_id=project_id,
            procurement_case_id=existing.id,
            event_type="procurement_import_handoff",
            payload={
                "input_kind": identity.input_kind,
                "source_url": identity.source_url,
                "normalization_method": identity.normalization_method,
                "handoff_surface": surface,
                "procurement_number": identity.procurement_number,
                "created": created,
            },
        )
    )
    session.commit()
    return {
        "id": existing.id,
        "customer_id": customer_id,
        "project_id": project_id,
        "procurement_number": identity.procurement_number,
        "status": existing.status,
        "created": created,
    }
