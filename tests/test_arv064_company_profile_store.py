from __future__ import annotations

from sqlalchemy import select

from src.modules.company_profile_store.models import (
    CompanyDocumentVersion,
    CompanyProfileFactVersion,
)
from src.modules.customer_pilot.models import PilotAuditEvent


def _customer(client, name: str) -> str:
    response = client.post(
        "/customers",
        json={
            "legal_name": f"{name} LLC",
            "inn": None,
            "kpp": None,
            "customer_status": "PROSPECT",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["customer_id"]


def _artifact(
    client, *, deal_id=None, name="company.pdf", uri="synthetic://company.pdf"
) -> dict:
    response = client.post(
        "/artifacts",
        json={
            "deal_id": deal_id,
            "artifact_type": "OTHER",
            "file_name": name,
            "mime_type": "application/pdf",
            "storage_uri": uri,
            "checksum_sha256": "a" * 64,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _deal(client, suffix: str) -> str:
    response = client.post(
        "/deals",
        json={
            "title": f"ARV-064 {suffix}",
            "initial_source_type": "manual_entry",
            "direction_type": "SUPPLY",
            "domain_type": "goods",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["deal_id"]


def test_arv064_profile_facts_are_versioned_tenant_scoped_and_autofill_is_explicit(
    client, session
):
    customer_a = _customer(client, "A")
    customer_b = _customer(client, "B")
    base = f"/api/company-profile/customers/{customer_a}"

    first = client.post(
        f"{base}/facts/legal_name/versions",
        json={
            "fact_group": "IDENTITY",
            "value": 'ООО "Синтетика"',
            "source_type": "CUSTOMER_PROVIDED",
            "source_ref": "synthetic-onboarding-v1",
            "expires_at": None,
        },
    )
    assert first.status_code == 201, first.text
    one = first.json()
    assert one["version_no"] == 1
    assert one["state"] == "ACTIVE"

    second = client.post(
        f"{base}/facts/legal_name/versions",
        json={
            "fact_group": "IDENTITY",
            "value": 'ООО "Синтетика 2"',
            "source_type": "MANUAL_REVIEW",
            "source_ref": "operator-confirmed-v2",
            "expires_at": None,
        },
    )
    assert second.status_code == 201, second.text
    assert second.json()["version_no"] == 2

    expired = client.post(
        f"{base}/facts/license_number/versions",
        json={
            "fact_group": "LICENSE",
            "value": "LIC-SYNTH-001",
            "source_type": "CUSTOMER_PROVIDED",
            "source_ref": "synthetic-license",
            "expires_at": "2000-01-01T00:00:00Z",
        },
    )
    assert expired.status_code == 201, expired.text
    assert expired.json()["state"] == "EXPIRED"

    history = client.get(f"{base}/facts/legal_name")
    assert history.status_code == 200
    items = history.json()
    assert [item["version_no"] for item in items] == [1, 2]
    assert [item["state"] for item in items] == ["SUPERSEDED", "ACTIVE"]
    assert items[0]["value"] == 'ООО "Синтетика"'
    assert items[1]["value"] == 'ООО "Синтетика 2"'

    autofill = client.post(
        f"{base}/autofill",
        json={
            "targets": [
                {
                    "fact_key": "legal_name",
                    "target_locator": "docx:token:{{LEGAL_NAME}}",
                },
                {"fact_key": "license_number", "target_locator": "xlsx:cell:Лист1!B2"},
                {
                    "fact_key": "unknown_fact",
                    "target_locator": "docx:token:{{UNKNOWN}}",
                },
            ]
        },
    )
    assert autofill.status_code == 200, autofill.text
    payload = autofill.json()
    assert payload["inference_performed"] is False
    assert payload["private_document_import_performed"] is False
    assert payload["resolved"] == [
        {
            "fact_key": "legal_name",
            "target_locator": "docx:token:{{LEGAL_NAME}}",
            "value": 'ООО "Синтетика 2"',
            "source_type": "COMPANY_PROFILE_FACT",
            "source_ref": second.json()["id"],
            "fact_version_no": 2,
        }
    ]
    assert {(item["fact_key"], item["reason"]) for item in payload["unresolved"]} == {
        ("license_number", "EXPIRED"),
        ("unknown_fact", "MISSING"),
    }

    # Tenant B cannot see A's fact history or resolve A's explicit values.
    assert (
        client.get(
            f"/api/company-profile/customers/{customer_b}/facts/legal_name"
        ).status_code
        == 404
    )
    b_autofill = client.post(
        f"/api/company-profile/customers/{customer_b}/autofill",
        json={
            "targets": [
                {
                    "fact_key": "legal_name",
                    "target_locator": "docx:token:{{LEGAL_NAME}}",
                }
            ]
        },
    )
    assert b_autofill.status_code == 200
    assert b_autofill.json()["resolved"] == []
    assert b_autofill.json()["unresolved"][0]["reason"] == "MISSING"

    audit = session.scalar(
        select(PilotAuditEvent)
        .where(
            PilotAuditEvent.customer_id == customer_a,
            PilotAuditEvent.event_type == "company_profile_fact_version_added",
        )
        .order_by(PilotAuditEvent.created_at.desc())
    )
    assert audit is not None
    assert "value" not in audit.payload
    assert audit.payload["inference_performed"] is False


def test_arv064_company_documents_bind_exact_artifact_versions_and_preserve_expiry(
    client, session
):
    customer = _customer(client, "Documents")
    artifact = _artifact(client, name="license.pdf", uri="synthetic://license/v1.pdf")
    base = f"/api/company-profile/customers/{customer}"

    created = client.post(
        f"{base}/documents",
        json={
            "document_key": "license_main",
            "document_type": "LICENSE",
            "display_name": "Synthetic License",
            "artifact_ref": artifact["artifact_ref"],
            "artifact_version_no": 1,
            "document_number": "SYN-001",
            "issued_at": "2026-01-01T00:00:00Z",
            "expires_at": "2099-01-01T00:00:00Z",
            "source_type": "CUSTOMER_PROVIDED",
            "source_ref": "synthetic-upload-v1",
        },
    )
    assert created.status_code == 201, created.text
    one = created.json()
    assert one["current_version_no"] == 1
    assert one["current_state"] == "ACTIVE"
    assert one["versions"][0]["artifact_version_no"] == 1
    assert one["versions"][0]["artifact_storage_uri"] == "synthetic://license/v1.pdf"

    added_artifact = client.post(
        f"/artifacts/{artifact['artifact_ref']}/versions",
        json={
            "storage_uri": "synthetic://license/v2.pdf",
            "checksum_sha256": "b" * 64,
        },
    )
    assert added_artifact.status_code == 201, added_artifact.text
    assert added_artifact.json()["version_no"] == 2

    second = client.post(
        f"{base}/documents/license_main/versions",
        json={
            "artifact_version_no": 2,
            "document_number": "SYN-002",
            "issued_at": "2027-01-01T00:00:00Z",
            "expires_at": "2000-01-01T00:00:00Z",
            "source_type": "CUSTOMER_PROVIDED",
            "source_ref": "synthetic-upload-v2",
        },
    )
    # Expiry before issued_at is invalid, so lineage remains unchanged.
    assert second.status_code == 422
    unchanged = client.get(f"{base}/documents/license_main").json()
    assert unchanged["current_version_no"] == 1

    valid_second = client.post(
        f"{base}/documents/license_main/versions",
        json={
            "artifact_version_no": 2,
            "document_number": "SYN-002",
            "issued_at": "1999-01-01T00:00:00Z",
            "expires_at": "2000-01-01T00:00:00Z",
            "source_type": "CUSTOMER_PROVIDED",
            "source_ref": "synthetic-upload-v2",
        },
    )
    assert valid_second.status_code == 201, valid_second.text
    two = valid_second.json()
    assert two["current_version_no"] == 2
    assert two["current_state"] == "EXPIRED"
    assert [item["state"] for item in two["versions"]] == ["SUPERSEDED", "EXPIRED"]
    assert two["versions"][0]["artifact_storage_uri"] == "synthetic://license/v1.pdf"
    assert two["versions"][1]["artifact_storage_uri"] == "synthetic://license/v2.pdf"
    assert two["versions"][1]["artifact_checksum_sha256"] == "b" * 64

    stored = session.scalar(
        select(CompanyDocumentVersion).where(
            CompanyDocumentVersion.id == two["versions"][0]["id"]
        )
    )
    stored.document_number = "MUTATED"
    try:
        session.flush()
        raise AssertionError("immutable company document version unexpectedly mutated")
    except ValueError as exc:
        assert "immutable" in str(exc)
    finally:
        session.rollback()


def test_arv064_reusable_document_artifacts_fail_closed_across_tenants_and_deals(
    client,
):
    customer_a = _customer(client, "Artifact A")
    customer_b = _customer(client, "Artifact B")
    artifact = _artifact(client, name="certificate.pdf", uri="synthetic://cert.pdf")

    payload = {
        "document_key": "certificate_main",
        "document_type": "CERTIFICATE",
        "display_name": "Synthetic Certificate",
        "artifact_ref": artifact["artifact_ref"],
        "artifact_version_no": 1,
        "document_number": "CERT-1",
        "issued_at": "2026-01-01T00:00:00Z",
        "expires_at": "2099-01-01T00:00:00Z",
        "source_type": "CUSTOMER_PROVIDED",
        "source_ref": "synthetic-cert",
    }
    a = client.post(
        f"/api/company-profile/customers/{customer_a}/documents",
        json=payload,
    )
    assert a.status_code == 201, a.text

    # The same exact artifact lineage cannot be silently reused as another document
    # even inside one tenant.
    same_tenant_duplicate = client.post(
        f"/api/company-profile/customers/{customer_a}/documents",
        json={**payload, "document_key": "certificate_alias"},
    )
    assert same_tenant_duplicate.status_code == 422
    assert "another company document" in same_tenant_duplicate.text

    # Same artifact cannot be rebound to another tenant.
    b = client.post(
        f"/api/company-profile/customers/{customer_b}/documents",
        json=payload,
    )
    assert b.status_code == 422
    assert "another customer" in b.text

    # Tenant B cannot read A's document by key.
    assert (
        client.get(
            f"/api/company-profile/customers/{customer_b}/documents/certificate_main"
        ).status_code
        == 404
    )

    # A deal-bound artifact is not eligible for the reusable company store.
    deal = _deal(client, "deal-bound")
    deal_artifact = _artifact(
        client,
        deal_id=deal,
        name="deal-only.pdf",
        uri="synthetic://deal-only.pdf",
    )
    deal_payload = {
        **payload,
        "document_key": "deal_bound_doc",
        "artifact_ref": deal_artifact["artifact_ref"],
    }
    rejected = client.post(
        f"/api/company-profile/customers/{customer_a}/documents",
        json=deal_payload,
    )
    assert rejected.status_code == 422
    assert "deal-bound" in rejected.text


def test_arv064_documents_do_not_become_autofill_facts_without_explicit_fact_storage(
    client,
):
    customer = _customer(client, "No Import")
    artifact = _artifact(
        client, name="requisites.pdf", uri="synthetic://private-requisites.pdf"
    )
    base = f"/api/company-profile/customers/{customer}"
    created = client.post(
        f"{base}/documents",
        json={
            "document_key": "requisites_source",
            "document_type": "REQUISITES",
            "display_name": "Synthetic Requisites",
            "artifact_ref": artifact["artifact_ref"],
            "artifact_version_no": 1,
            "document_number": None,
            "issued_at": None,
            "expires_at": None,
            "source_type": "CUSTOMER_PROVIDED",
            "source_ref": "synthetic-private-fixture",
        },
    )
    assert created.status_code == 201, created.text

    autofill = client.post(
        f"{base}/autofill",
        json={
            "targets": [
                {
                    "fact_key": "bank_account",
                    "target_locator": "docx:token:{{BANK_ACCOUNT}}",
                }
            ]
        },
    )
    assert autofill.status_code == 200
    payload = autofill.json()
    assert payload["resolved"] == []
    assert payload["unresolved"] == [
        {
            "fact_key": "bank_account",
            "target_locator": "docx:token:{{BANK_ACCOUNT}}",
            "reason": "MISSING",
        }
    ]
    assert payload["inference_performed"] is False
    assert payload["private_document_import_performed"] is False


def test_arv064_profile_fact_history_is_immutable(client, session):
    customer = _customer(client, "Immutable")
    response = client.post(
        f"/api/company-profile/customers/{customer}/facts/inn/versions",
        json={
            "fact_group": "REQUISITE",
            "value": "0000000000",
            "source_type": "MANUAL_REVIEW",
            "source_ref": "synthetic-fixture",
        },
    )
    assert response.status_code == 201
    record = session.get(CompanyProfileFactVersion, response.json()["id"])
    record.value_json = "1111111111"
    try:
        session.flush()
        raise AssertionError("immutable profile fact unexpectedly mutated")
    except ValueError as exc:
        assert "immutable" in str(exc)
    finally:
        session.rollback()

    # No mutation/delete API is exposed.
    assert (
        client.patch(
            f"/api/company-profile/customers/{customer}/facts/inn",
            json={"value": "1111111111"},
        ).status_code
        == 405
    )
