from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.company_profile_store.models import (
    CompanyDocument,
    CompanyDocumentVersion,
    CompanyProfileFactVersion,
)
from src.modules.company_profile_store.schemas import (
    AppendCompanyDocumentVersionRequest,
    AppendCompanyProfileFactRequest,
    AutofillResolvedField,
    AutofillUnresolvedField,
    CreateCompanyDocumentRequest,
    ResolveCompanyAutofillRequest,
)
from src.modules.customer_pilot.models import PilotAuditEvent
from src.modules.customer_registry.models import CustomerProfile
from src.modules.document_store.models import (
    ArtifactLink,
    ArtifactVersion,
    DocumentArtifact,
)
from src.shared.db.base import utcnow
from src.shared.errors import NotFoundError, ValidationError
from src.shared.validation import require_non_empty


def _customer(session: Session, customer_id: str) -> CustomerProfile:
    record = session.scalar(
        select(CustomerProfile).where(CustomerProfile.customer_id == customer_id)
    )
    if not record:
        raise NotFoundError(f"Customer '{customer_id}' was not found")
    return record


def _clean_key(value: str, field: str) -> str:
    return require_non_empty(value, field).strip().lower()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _expired(expires_at: datetime | None, *, now: datetime | None = None) -> bool:
    if expires_at is None:
        return False
    current = _as_utc(now or utcnow())
    return _as_utc(expires_at) <= current


def _fact_versions(
    session: Session,
    customer_id: str,
    fact_key: str,
) -> list[CompanyProfileFactVersion]:
    return list(
        session.scalars(
            select(CompanyProfileFactVersion)
            .where(
                CompanyProfileFactVersion.customer_id == customer_id,
                CompanyProfileFactVersion.fact_key == fact_key,
            )
            .order_by(
                CompanyProfileFactVersion.version_no.asc(),
                CompanyProfileFactVersion.id.asc(),
            )
        )
    )


def append_company_profile_fact(
    session: Session,
    *,
    customer_id: str,
    fact_key: str,
    payload: AppendCompanyProfileFactRequest,
) -> CompanyProfileFactVersion:
    _customer(session, customer_id)
    key = _clean_key(fact_key, "fact_key")
    versions = _fact_versions(session, customer_id, key)
    if versions and versions[-1].fact_group != payload.fact_group:
        raise ValidationError("fact_group cannot change inside one fact_key lineage")
    record = CompanyProfileFactVersion(
        customer_id=customer_id,
        fact_key=key,
        fact_group=payload.fact_group,
        version_no=(versions[-1].version_no + 1) if versions else 1,
        value_json=payload.value,
        source_type=require_non_empty(payload.source_type, "source_type").upper(),
        source_ref=require_non_empty(payload.source_ref, "source_ref"),
        expires_at=payload.expires_at,
    )
    session.add(record)
    session.flush()
    session.add(
        PilotAuditEvent(
            customer_id=customer_id,
            event_type="company_profile_fact_version_added",
            payload={
                "fact_version_id": record.id,
                "fact_key": record.fact_key,
                "fact_group": record.fact_group,
                "version_no": record.version_no,
                "source_type": record.source_type,
                "source_ref": record.source_ref,
                "expires_at": record.expires_at.isoformat()
                if record.expires_at
                else None,
                "inference_performed": False,
            },
        )
    )
    session.commit()
    session.refresh(record)
    return record


def get_company_profile_fact_history(
    session: Session,
    *,
    customer_id: str,
    fact_key: str,
) -> list[CompanyProfileFactVersion]:
    _customer(session, customer_id)
    key = _clean_key(fact_key, "fact_key")
    records = _fact_versions(session, customer_id, key)
    if not records:
        raise NotFoundError(f"Company profile fact '{key}' was not found")
    return records


def list_current_company_profile_facts(
    session: Session,
    *,
    customer_id: str,
) -> list[CompanyProfileFactVersion]:
    _customer(session, customer_id)
    records = list(
        session.scalars(
            select(CompanyProfileFactVersion)
            .where(CompanyProfileFactVersion.customer_id == customer_id)
            .order_by(
                CompanyProfileFactVersion.fact_key.asc(),
                CompanyProfileFactVersion.version_no.asc(),
            )
        )
    )
    current: dict[str, CompanyProfileFactVersion] = {}
    for record in records:
        current[record.fact_key] = record
    return [current[key] for key in sorted(current)]


def fact_state(
    record: CompanyProfileFactVersion,
    *,
    latest_version_no: int,
) -> tuple[bool, bool, str]:
    is_current = record.version_no == latest_version_no
    is_expired = _expired(record.expires_at)
    if not is_current:
        return False, is_expired, "SUPERSEDED"
    if is_expired:
        return True, True, "EXPIRED"
    return True, False, "ACTIVE"


def _document(
    session: Session,
    *,
    customer_id: str,
    document_key: str,
) -> CompanyDocument:
    key = _clean_key(document_key, "document_key")
    record = session.scalar(
        select(CompanyDocument).where(
            CompanyDocument.customer_id == customer_id,
            CompanyDocument.document_key == key,
        )
    )
    if not record:
        raise NotFoundError(f"Company document '{key}' was not found")
    return record


def _document_versions(
    session: Session,
    company_document_id: str,
) -> list[CompanyDocumentVersion]:
    return list(
        session.scalars(
            select(CompanyDocumentVersion)
            .where(CompanyDocumentVersion.company_document_id == company_document_id)
            .order_by(
                CompanyDocumentVersion.version_no.asc(),
                CompanyDocumentVersion.id.asc(),
            )
        )
    )


def _artifact(
    session: Session,
    *,
    artifact_ref: str,
) -> DocumentArtifact:
    record = session.scalar(
        select(DocumentArtifact).where(DocumentArtifact.artifact_ref == artifact_ref)
    )
    if not record:
        raise NotFoundError(f"Artifact '{artifact_ref}' was not found")
    return record


def _artifact_version(
    session: Session,
    *,
    artifact_ref: str,
    version_no: int,
) -> ArtifactVersion:
    record = session.scalar(
        select(ArtifactVersion).where(
            ArtifactVersion.artifact_ref == artifact_ref,
            ArtifactVersion.version_no == version_no,
        )
    )
    if not record:
        raise ValidationError(
            f"Artifact version '{artifact_ref}:v{version_no}' was not found"
        )
    return record


def _validate_reusable_artifact(
    session: Session,
    *,
    customer_id: str,
    artifact_ref: str,
    allowed_company_document_id: str | None = None,
) -> DocumentArtifact:
    artifact = _artifact(session, artifact_ref=artifact_ref)
    if artifact.deal_id is not None:
        raise ValidationError(
            "Reusable company documents must use an unbound artifact, not a deal-bound artifact"
        )
    existing = session.scalar(
        select(CompanyDocument).where(CompanyDocument.artifact_ref == artifact_ref)
    )
    if existing and existing.customer_id != customer_id:
        raise ValidationError("Artifact is already bound to another customer")
    if existing and existing.id != allowed_company_document_id:
        raise ValidationError("Artifact is already bound to another company document")
    return artifact


def _validate_document_dates(
    issued_at: datetime | None,
    expires_at: datetime | None,
) -> None:
    if issued_at and expires_at and _as_utc(expires_at) <= _as_utc(issued_at):
        raise ValidationError("expires_at must be later than issued_at")


def create_company_document(
    session: Session,
    *,
    customer_id: str,
    payload: CreateCompanyDocumentRequest,
) -> tuple[CompanyDocument, CompanyDocumentVersion]:
    _customer(session, customer_id)
    key = _clean_key(payload.document_key, "document_key")
    if session.scalar(
        select(CompanyDocument).where(
            CompanyDocument.customer_id == customer_id,
            CompanyDocument.document_key == key,
        )
    ):
        raise ValidationError(f"Company document '{key}' already exists")
    artifact = _validate_reusable_artifact(
        session,
        customer_id=customer_id,
        artifact_ref=payload.artifact_ref,
    )
    _artifact_version(
        session,
        artifact_ref=artifact.artifact_ref,
        version_no=payload.artifact_version_no,
    )
    _validate_document_dates(payload.issued_at, payload.expires_at)

    document = CompanyDocument(
        customer_id=customer_id,
        document_key=key,
        document_type=payload.document_type,
        display_name=require_non_empty(payload.display_name, "display_name"),
        artifact_ref=artifact.artifact_ref,
    )
    session.add(document)
    session.flush()
    version = CompanyDocumentVersion(
        company_document_id=document.id,
        version_no=1,
        artifact_version_no=payload.artifact_version_no,
        document_number=payload.document_number.strip()
        if payload.document_number
        else None,
        issued_at=payload.issued_at,
        expires_at=payload.expires_at,
        source_type=require_non_empty(payload.source_type, "source_type").upper(),
        source_ref=require_non_empty(payload.source_ref, "source_ref"),
    )
    session.add(version)
    session.add(
        ArtifactLink(
            artifact_ref=artifact.artifact_ref,
            linked_object_type="COMPANY_DOCUMENT",
            linked_object_ref=document.id,
        )
    )
    session.add(
        PilotAuditEvent(
            customer_id=customer_id,
            event_type="company_document_created",
            payload={
                "company_document_id": document.id,
                "document_key": document.document_key,
                "document_type": document.document_type,
                "artifact_ref": document.artifact_ref,
                "artifact_version_no": version.artifact_version_no,
                "expires_at": version.expires_at.isoformat()
                if version.expires_at
                else None,
                "private_document_import_performed": False,
            },
        )
    )
    session.commit()
    session.refresh(document)
    session.refresh(version)
    return document, version


def append_company_document_version(
    session: Session,
    *,
    customer_id: str,
    document_key: str,
    payload: AppendCompanyDocumentVersionRequest,
) -> tuple[CompanyDocument, CompanyDocumentVersion]:
    _customer(session, customer_id)
    document = _document(session, customer_id=customer_id, document_key=document_key)
    artifact = _validate_reusable_artifact(
        session,
        customer_id=customer_id,
        artifact_ref=document.artifact_ref,
        allowed_company_document_id=document.id,
    )
    _artifact_version(
        session,
        artifact_ref=artifact.artifact_ref,
        version_no=payload.artifact_version_no,
    )
    _validate_document_dates(payload.issued_at, payload.expires_at)
    versions = _document_versions(session, document.id)
    latest = versions[-1]
    if payload.artifact_version_no <= latest.artifact_version_no:
        raise ValidationError(
            "New company document version must reference a newer ArtifactVersion"
        )
    version = CompanyDocumentVersion(
        company_document_id=document.id,
        version_no=latest.version_no + 1,
        artifact_version_no=payload.artifact_version_no,
        document_number=payload.document_number.strip()
        if payload.document_number
        else None,
        issued_at=payload.issued_at,
        expires_at=payload.expires_at,
        source_type=require_non_empty(payload.source_type, "source_type").upper(),
        source_ref=require_non_empty(payload.source_ref, "source_ref"),
    )
    session.add(version)
    session.flush()
    session.add(
        PilotAuditEvent(
            customer_id=customer_id,
            event_type="company_document_version_added",
            payload={
                "company_document_id": document.id,
                "document_key": document.document_key,
                "version_no": version.version_no,
                "artifact_ref": document.artifact_ref,
                "artifact_version_no": version.artifact_version_no,
                "expires_at": version.expires_at.isoformat()
                if version.expires_at
                else None,
                "private_document_import_performed": False,
            },
        )
    )
    session.commit()
    session.refresh(version)
    return document, version


def get_company_document(
    session: Session,
    *,
    customer_id: str,
    document_key: str,
) -> tuple[CompanyDocument, list[CompanyDocumentVersion]]:
    _customer(session, customer_id)
    document = _document(session, customer_id=customer_id, document_key=document_key)
    return document, _document_versions(session, document.id)


def list_company_documents(
    session: Session,
    *,
    customer_id: str,
    document_type: str | None = None,
) -> list[tuple[CompanyDocument, list[CompanyDocumentVersion]]]:
    _customer(session, customer_id)
    query = (
        select(CompanyDocument)
        .where(CompanyDocument.customer_id == customer_id)
        .order_by(CompanyDocument.document_key.asc(), CompanyDocument.id.asc())
    )
    if document_type:
        query = query.where(CompanyDocument.document_type == document_type)
    documents = list(session.scalars(query))
    return [
        (document, _document_versions(session, document.id)) for document in documents
    ]


def document_version_state(
    version: CompanyDocumentVersion,
    *,
    latest_version_no: int,
) -> tuple[bool, bool, str]:
    is_current = version.version_no == latest_version_no
    is_expired = _expired(version.expires_at)
    if not is_current:
        return False, is_expired, "SUPERSEDED"
    if is_expired:
        return True, True, "EXPIRED"
    return True, False, "ACTIVE"


def artifact_version_evidence(
    session: Session,
    *,
    artifact_ref: str,
    artifact_version_no: int,
) -> ArtifactVersion:
    return _artifact_version(
        session,
        artifact_ref=artifact_ref,
        version_no=artifact_version_no,
    )


def resolve_company_autofill(
    session: Session,
    *,
    customer_id: str,
    payload: ResolveCompanyAutofillRequest,
) -> tuple[list[AutofillResolvedField], list[AutofillUnresolvedField]]:
    _customer(session, customer_id)
    requested_keys = {_clean_key(item.fact_key, "fact_key") for item in payload.targets}
    all_versions = list(
        session.scalars(
            select(CompanyProfileFactVersion)
            .where(
                CompanyProfileFactVersion.customer_id == customer_id,
                CompanyProfileFactVersion.fact_key.in_(requested_keys),
            )
            .order_by(
                CompanyProfileFactVersion.fact_key.asc(),
                CompanyProfileFactVersion.version_no.asc(),
            )
        )
    )
    current: dict[str, CompanyProfileFactVersion] = {}
    for record in all_versions:
        current[record.fact_key] = record

    resolved: list[AutofillResolvedField] = []
    unresolved: list[AutofillUnresolvedField] = []
    for target in payload.targets:
        key = _clean_key(target.fact_key, "fact_key")
        record = current.get(key)
        if record is None:
            unresolved.append(
                AutofillUnresolvedField(
                    fact_key=key,
                    target_locator=target.target_locator,
                    reason="MISSING",
                )
            )
            continue
        if _expired(record.expires_at):
            unresolved.append(
                AutofillUnresolvedField(
                    fact_key=key,
                    target_locator=target.target_locator,
                    reason="EXPIRED",
                )
            )
            continue
        resolved.append(
            AutofillResolvedField(
                fact_key=key,
                target_locator=target.target_locator,
                value=record.value_json,
                source_type="COMPANY_PROFILE_FACT",
                source_ref=record.id,
                fact_version_no=record.version_no,
            )
        )
    return resolved, unresolved
