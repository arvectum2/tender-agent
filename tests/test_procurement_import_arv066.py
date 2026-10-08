"""ARV-066: fail-closed intake normalization and shared-case provenance."""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.modules.customer_pilot.models import (
    PilotAuditEvent,
    PilotProject,
    ProcurementCase,
)
from src.modules.customer_pilot.procurement_import import (
    import_procurement_case,
    normalize_procurement_input,
)
from src.modules.customer_registry.models import CustomerProfile
from src.shared.db.base import Base

NUMBER = "0173100009626000097"


@pytest.mark.parametrize(
    "raw",
    [
        "https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber="
        + NUMBER,
        "https://www.zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber="
        + NUMBER,
        NUMBER,
    ],
)
def test_normalize_supported(raw):
    assert normalize_procurement_input(raw).procurement_number == NUMBER


@pytest.mark.parametrize(
    "raw",
    [
        "http://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber="
        + NUMBER,
        "https://evil.example/epz/order/notice/ok20/view/common-info.html?regNumber="
        + NUMBER,
        "https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber="
        + NUMBER
        + "&regNumber="
        + NUMBER,
        "https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regnumber="
        + NUMBER,
        "https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html",
        "https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber=abc",
        "javascript:alert(1)",
    ],
)
def test_normalize_rejects_ambiguous_or_unsupported(raw):
    with pytest.raises(ValueError):
        normalize_procurement_input(raw)


def test_case_is_idempotent_with_audit_and_project_boundary():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    # Only relevant metadata tables; customer FK references are resolved from Base.
    Base.metadata.create_all(
        engine,
        tables=[
            CustomerProfile.__table__,
            PilotProject.__table__,
            ProcurementCase.__table__,
            PilotAuditEvent.__table__,
        ],
    )
    with Session(engine) as session:
        session.add_all(
            [
                CustomerProfile(customer_id="a", legal_name="A", customer_status="active"),
                CustomerProfile(customer_id="b", legal_name="B", customer_status="active"),
            ]
        )
        session.flush()
        project = PilotProject(customer_id="a", name="P", internal_slug="p")
        session.add(project)
        session.commit()
        first = import_procurement_case(
            session,
            customer_id="a",
            project_id=project.id,
            raw_input=NUMBER,
            surface="manual",
        )
        second = import_procurement_case(
            session,
            customer_id="a",
            project_id=project.id,
            raw_input="https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber="
            + NUMBER,
            surface="share",
        )
        assert first["created"] is True
        assert second["created"] is False
        assert first["id"] == second["id"]
        assert len(session.scalars(select(ProcurementCase)).all()) == 1
        events = session.scalars(
            select(PilotAuditEvent).where(
                PilotAuditEvent.event_type == "procurement_import_handoff"
            )
        ).all()
        assert len(events) == 2
        assert events[1].payload["handoff_surface"] == "share"
        with pytest.raises(HTTPException) as exc:
            import_procurement_case(
                session,
                customer_id="b",
                project_id=project.id,
                raw_input=NUMBER,
                surface="browser",
            )
        assert exc.value.status_code == 404
