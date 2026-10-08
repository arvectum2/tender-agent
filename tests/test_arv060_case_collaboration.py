import pytest
from sqlalchemy import select

from src.modules.case_collaboration.models import (
    CaseJournalEntry,
    CaseJournalEvidenceLink,
    CaseJournalMention,
)
from src.modules.customer_pilot.models import PilotAuditEvent
from src.modules.customer_registry.models import CustomerProfile


def _customer(session, customer_id: str) -> None:
    session.add(
        CustomerProfile(
            customer_id=customer_id,
            legal_name=f"{customer_id} legal",
            customer_status="prospect",
        )
    )
    session.commit()


def _case(client, customer_id: str, name: str) -> dict:
    project = client.post(
        f"/api/operator/pilot/customers/{customer_id}/projects",
        json={"name": name},
    )
    assert project.status_code == 201
    project_id = project.json()["id"]
    response = client.post(
        f"/api/operator/pilot/customers/{customer_id}/projects/{project_id}/cases",
        json={"procurement_number": f"{customer_id}-PROC"},
    )
    assert response.status_code == 201
    payload = response.json()
    payload["project_id"] = project_id
    return payload


def _entry_url(customer_id: str, case_id: str) -> str:
    return (
        f"/api/operator/pilot/customers/{customer_id}/cases/{case_id}"
        "/discussion/entries"
    )


def test_arv060_comment_mentions_evidence_and_audit_are_internal_and_attributable(
    client, session
):
    _customer(session, "CUST-ARV060")
    case = _case(client, "CUST-ARV060", "ARV060")

    response = client.post(
        _entry_url("CUST-ARV060", case["id"]),
        json={
            "entry_type": "COMMENT",
            "actor_type": "USER",
            "actor_ref": "operator-17",
            "body": "Проверьте источник @legal.team и @buyer_1",
            "mention_refs": ["@buyer_1", "risk.owner"],
            "evidence_links": [
                {"source_type": "PROCUREMENT_CASE", "source_ref": case["id"]},
                {"source_type": "INTERNAL_NOTE", "source_ref": "risk-note:42"},
            ],
        },
    )
    assert response.status_code == 201
    payload = response.json()

    assert payload["entry_type"] == "COMMENT"
    assert payload["actor_type"] == "USER"
    assert payload["actor_ref"] == "operator-17"
    assert [item["mention_ref"] for item in payload["mentions"]] == [
        "buyer_1",
        "legal.team",
        "risk.owner",
    ]
    assert {item["notification_state"] for item in payload["mentions"]} == {
        "INTERNAL_UNREAD"
    }
    assert {
        (item["source_type"], item["source_ref"]) for item in payload["evidence_links"]
    } == {
        ("PROCUREMENT_CASE", case["id"]),
        ("INTERNAL_NOTE", "risk-note:42"),
    }

    audit = session.scalar(
        select(PilotAuditEvent)
        .where(
            PilotAuditEvent.customer_id == "CUST-ARV060",
            PilotAuditEvent.procurement_case_id == case["id"],
            PilotAuditEvent.event_type == "case_journal_entry_recorded",
        )
        .order_by(PilotAuditEvent.created_at.desc())
    )
    assert audit is not None
    assert audit.payload["entry_id"] == payload["id"]
    assert audit.payload["actor_ref"] == "operator-17"
    assert audit.payload["notification_channel"] == "internal_only"
    assert audit.payload["mention_count"] == 3


def test_arv060_cross_tenant_access_and_cross_case_evidence_fail_closed(
    client, session
):
    _customer(session, "CUST-ARV060-A")
    _customer(session, "CUST-ARV060-B")
    case_a = _case(client, "CUST-ARV060-A", "A")
    case_b = _case(client, "CUST-ARV060-B", "B")

    created = client.post(
        _entry_url("CUST-ARV060-A", case_a["id"]),
        json={
            "entry_type": "COMMENT",
            "actor_type": "AGENT",
            "actor_ref": "AI-ENG-001",
            "body": "Внутренний комментарий",
        },
    )
    assert created.status_code == 201
    entry_id = created.json()["id"]

    assert client.get(_entry_url("CUST-ARV060-B", case_a["id"])).status_code == 404
    assert (
        client.get(
            f"{_entry_url('CUST-ARV060-B', case_a['id'])}/{entry_id}"
        ).status_code
        == 404
    )

    invalid = client.post(
        _entry_url("CUST-ARV060-A", case_a["id"]),
        json={
            "entry_type": "COMMENT",
            "actor_type": "USER",
            "actor_ref": "operator",
            "body": "Ссылка не на тот кейс",
            "evidence_links": [
                {"source_type": "PROCUREMENT_CASE", "source_ref": case_b["id"]}
            ],
        },
    )
    assert invalid.status_code == 422


def test_arv060_decision_supersedes_by_append_and_history_is_immutable(client, session):
    _customer(session, "CUST-ARV060-D")
    case = _case(client, "CUST-ARV060-D", "D")
    url = _entry_url("CUST-ARV060-D", case["id"])

    first = client.post(
        url,
        json={
            "entry_type": "DECISION",
            "actor_type": "USER",
            "actor_ref": "lead-1",
            "body": "Нужна дополнительная проверка",
            "decision_code": "REVIEW_REQUIRED",
        },
    )
    assert first.status_code == 201

    second = client.post(
        url,
        json={
            "entry_type": "DECISION",
            "actor_type": "USER",
            "actor_ref": "lead-2",
            "body": "Проверка выполнена, решение обновлено",
            "decision_code": "REVIEW_COMPLETE",
            "supersedes_entry_id": first.json()["id"],
        },
    )
    assert second.status_code == 201

    history = client.get(url)
    assert history.status_code == 200
    items = history.json()
    assert [item["id"] for item in items] == [first.json()["id"], second.json()["id"]]
    assert items[1]["supersedes_entry_id"] == items[0]["id"]
    assert items[0]["body"] == "Нужна дополнительная проверка"

    assert (
        client.patch(
            f"{url}/{first.json()['id']}", json={"body": "rewrite"}
        ).status_code
        == 405
    )
    assert client.delete(f"{url}/{first.json()['id']}").status_code == 405

    stored = session.get(CaseJournalEntry, first.json()["id"])
    stored.body = "attempted mutation"
    with pytest.raises(ValueError, match="immutable"):
        session.flush()
    session.rollback()

    assert (
        session.scalar(
            select(CaseJournalEntry.body).where(
                CaseJournalEntry.id == first.json()["id"]
            )
        )
        == "Нужна дополнительная проверка"
    )


def test_arv060_mentions_and_evidence_are_immutable_append_only_children(
    client, session
):
    _customer(session, "CUST-ARV060-I")
    case = _case(client, "CUST-ARV060-I", "I")
    response = client.post(
        _entry_url("CUST-ARV060-I", case["id"]),
        json={
            "entry_type": "COMMENT",
            "actor_type": "USER",
            "actor_ref": "operator",
            "body": "ping @reviewer",
            "evidence_links": [
                {"source_type": "PROCUREMENT_CASE", "source_ref": case["id"]}
            ],
        },
    )
    assert response.status_code == 201
    entry_id = response.json()["id"]

    mention = session.scalar(
        select(CaseJournalMention).where(
            CaseJournalMention.journal_entry_id == entry_id
        )
    )
    mention.notification_state = "EXTERNAL_SENT"
    with pytest.raises(ValueError, match="immutable"):
        session.flush()
    session.rollback()

    evidence = session.scalar(
        select(CaseJournalEvidenceLink).where(
            CaseJournalEvidenceLink.journal_entry_id == entry_id
        )
    )
    session.delete(evidence)
    with pytest.raises(ValueError, match="immutable"):
        session.flush()
    session.rollback()
