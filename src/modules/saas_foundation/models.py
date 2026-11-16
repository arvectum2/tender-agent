"""APR-05 durable tenant/auth/entitlement foundations.

Opaque secrets are never stored; only SHA-256 digests of 256-bit random tokens.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.db.base import Base, UUIDPrimaryKeyMixin, utcnow


class SaasTenant(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "saas_tenants"
    tenant_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    customer_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("customer_profiles.customer_id"), unique=True, nullable=False
    )
    plan_code: Mapped[str] = mapped_column(String(32), nullable=False, default="pilot")
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    billing_state: Mapped[str] = mapped_column(String(32), nullable=False, default="trial")
    trial_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class SaasMember(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "saas_members"
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("saas_tenants.tenant_id"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (Index("ix_saas_member_tenant", "tenant_id"),)


class SaasInvitation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "saas_invitations"
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("saas_tenants.tenant_id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    token_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    issued_by_member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("saas_members.id"), nullable=True
    )
    acquisition_channel: Mapped[str] = mapped_column(String(40), nullable=False, default="operator")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (Index("ix_saas_invitation_tenant", "tenant_id"),)


class SaasAccessToken(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "saas_access_tokens"
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("saas_tenants.tenant_id"), nullable=False
    )
    member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saas_members.id"), nullable=False
    )
    token_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (Index("ix_saas_token_member", "tenant_id", "member_id"),)


class SaasLegalAcceptance(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "saas_legal_acceptances"
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("saas_tenants.tenant_id"), nullable=False
    )
    member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saas_members.id"), nullable=False
    )
    terms_version: Mapped[str] = mapped_column(String(64), nullable=False)
    privacy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (Index("ix_saas_legal_member", "tenant_id", "member_id"),)


class SaasUsageCounter(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "saas_usage_counters"
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("saas_tenants.tenant_id"), nullable=False
    )
    period_utc: Mapped[str] = mapped_column(String(7), nullable=False)
    metric: Mapped[str] = mapped_column(String(32), nullable=False)
    used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    __table_args__ = (UniqueConstraint("tenant_id", "period_utc", "metric", name="uq_saas_usage_counter"),)


class SaasRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "saas_runs"
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("saas_tenants.tenant_id"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    created_by_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saas_members.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (Index("ix_saas_run_tenant", "tenant_id"),)


class SaasPaymentEvidence(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "saas_payment_evidence"
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("saas_tenants.tenant_id"), nullable=False
    )
    external_reference: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    operator_note: Mapped[str] = mapped_column(String(512), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class SaasAuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "saas_audit_events"
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("saas_tenants.tenant_id"), nullable=False
    )
    member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("saas_members.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (Index("ix_saas_audit_tenant", "tenant_id", "created_at"),)


class CompanyPortfolioDecision(UUIDPrimaryKeyMixin, Base):
    """Append-only human business decision on an existing company-owned case."""
    __tablename__ = "company_portfolio_decisions"

    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("procurement_cases.id"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("saas_tenants.tenant_id"), nullable=False)
    member_id: Mapped[str] = mapped_column(String(36), ForeignKey("saas_members.id"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    deferred_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (
        UniqueConstraint("case_id", "revision", name="uq_company_case_decision_revision"),
        UniqueConstraint("case_id", "idempotency_key", name="uq_company_case_decision_idem"),
        CheckConstraint("revision > 0", name="ck_company_decision_revision"),
        CheckConstraint("action IN ('GO', 'NO_GO', 'DEFER')", name="ck_company_decision_action"),
        CheckConstraint("(action = 'DEFER' AND deferred_until IS NOT NULL) OR (action <> 'DEFER' AND deferred_until IS NULL)", name="ck_company_decision_defer"),
        Index("ix_company_decisions_tenant_case", "tenant_id", "case_id"),
    )


def _immutable_company_decision(*_args):
    raise ValueError("Company portfolio decision history is immutable")


event.listen(CompanyPortfolioDecision, "before_update", _immutable_company_decision)
event.listen(CompanyPortfolioDecision, "before_delete", _immutable_company_decision)


class CompanyPortfolioEvidence(UUIDPrimaryKeyMixin, Base):
    """Immutable reference to an owned run and the supplier profile used with it."""
    __tablename__ = "company_portfolio_evidence"

    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("procurement_cases.id"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("saas_tenants.tenant_id"), nullable=False)
    member_id: Mapped[str] = mapped_column(String(36), ForeignKey("saas_members.id"), nullable=False)
    run_id: Mapped[str] = mapped_column(String(128), ForeignKey("saas_runs.run_id"), nullable=False)
    profile_fact_id: Mapped[str] = mapped_column(String(36), ForeignKey("company_profile_fact_versions.id"), nullable=False)
    source_snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (
        UniqueConstraint("case_id", "run_id", "profile_fact_id", name="uq_company_case_run_profile"),
        Index("ix_company_evidence_tenant_case", "tenant_id", "case_id"),
    )


event.listen(CompanyPortfolioEvidence, "before_update", _immutable_company_decision)
event.listen(CompanyPortfolioEvidence, "before_delete", _immutable_company_decision)


class CompanyDiscoveryRun(UUIDPrimaryKeyMixin, Base):
    """Bounded company search with a frozen profile and committed step receipts."""
    __tablename__ = "company_discovery_runs"
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("saas_tenants.tenant_id"), nullable=False)
    member_id: Mapped[str] = mapped_column(String(36), ForeignKey("saas_members.id"), nullable=False)
    profile_fact_id: Mapped[str] = mapped_column(String(36), ForeignKey("company_profile_fact_versions.id"), nullable=False)
    run_day: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    plan_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    results_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    attempts_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_day", name="uq_company_discovery_tenant_day"),
        Index("ix_company_discovery_tenant_day", "tenant_id", "run_day"),
    )


class CompanyDiscoverySchedule(UUIDPrimaryKeyMixin, Base):
    """Explicit revocable company-owner grant for unattended public discovery."""
    __tablename__ = "company_discovery_schedules"
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("saas_tenants.tenant_id"), unique=True, nullable=False)
    member_id: Mapped[str] = mapped_column(String(36), ForeignKey("saas_members.id"), nullable=False)
    profile_fact_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("company_profile_fact_versions.id"))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    hour_moscow: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    sources_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_tick_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (CheckConstraint("hour_moscow >= 0 AND hour_moscow <= 23", name="ck_company_schedule_hour"), Index("ix_company_schedule_due", "enabled", "last_tick_at"))


class CommercialCaptureAttempt(UUIDPrimaryKeyMixin, Base):
    """Durable public source request reservation; no automatic retry."""
    __tablename__ = "commercial_capture_attempts"
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("saas_tenants.tenant_id"), nullable=False)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("procurement_cases.id"), nullable=False)
    member_id: Mapped[str] = mapped_column(String(36), ForeignKey("saas_members.id"), nullable=False)
    capture_day: Mapped[str] = mapped_column(String(10), nullable=False)
    source_url: Mapped[str] = mapped_column(String(650), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (UniqueConstraint("case_id", "capture_day", name="uq_commercial_capture_case_day"), Index("ix_commercial_capture_tenant_day", "tenant_id", "capture_day"))


class CommercialCardSnapshot(UUIDPrimaryKeyMixin, Base):
    """Append-only outcome: original HTML only for a verified public observation."""
    __tablename__ = "commercial_card_snapshots"
    attempt_id: Mapped[str] = mapped_column(String(36), ForeignKey("commercial_capture_attempts.id"), nullable=False, unique=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    original_html: Mapped[bytes | None] = mapped_column(LargeBinary)
    receipt_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (CheckConstraint("outcome IN ('CAPTURED', 'SOURCE_UNAVAILABLE', 'UNSUPPORTED_CARD')", name="ck_commercial_snapshot_outcome"),)


for _commercial_immutable in (CommercialCaptureAttempt, CommercialCardSnapshot):
    event.listen(_commercial_immutable, "before_update", _immutable_company_decision)
    event.listen(_commercial_immutable, "before_delete", _immutable_company_decision)


class CommercialAttachmentEvidence(UUIDPrimaryKeyMixin, Base):
    """Company-supplied bytes bound to an observed candidate link, not original proof."""
    __tablename__ = "commercial_attachment_evidence"
    attempt_id: Mapped[str] = mapped_column(String(36), ForeignKey("commercial_capture_attempts.id"), nullable=False)
    member_id: Mapped[str] = mapped_column(String(36), ForeignKey("saas_members.id"), nullable=False)
    candidate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(String(650), nullable=False)
    raw_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    inspection_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (UniqueConstraint("attempt_id", "candidate_id", name="uq_commercial_attachment_candidate"),)


event.listen(CommercialAttachmentEvidence, "before_update", _immutable_company_decision)
event.listen(CommercialAttachmentEvidence, "before_delete", _immutable_company_decision)


class CommercialRequirementReview(UUIDPrimaryKeyMixin, Base):
    """Append-only human judgement on a literal fragment, not a qualification verdict."""
    __tablename__ = "commercial_requirement_reviews"
    attachment_id: Mapped[str] = mapped_column(String(36), ForeignKey("commercial_attachment_evidence.id"), nullable=False)
    member_id: Mapped[str] = mapped_column(String(36), ForeignKey("saas_members.id"), nullable=False)
    fragment_key: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    profile_fact_id: Mapped[str] = mapped_column(String(36), ForeignKey("company_profile_fact_versions.id"), nullable=False)
    reference_fact_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("company_profile_fact_versions.id"))
    document_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("company_document_versions.id"))
    review_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (
        UniqueConstraint("attachment_id", "fragment_key", "revision", name="uq_commercial_review_revision"),
        UniqueConstraint("attachment_id", "idempotency_key", name="uq_commercial_review_replay"),
        CheckConstraint("revision > 0", name="ck_commercial_review_revision"),
    )


event.listen(CommercialRequirementReview, "before_update", _immutable_company_decision)
event.listen(CommercialRequirementReview, "before_delete", _immutable_company_decision)


class CompanyCaseLifecycleEvent(UUIDPrimaryKeyMixin, Base):
    """Human-attested progress on the canonical owned case, never an ETP action."""
    __tablename__ = "company_case_lifecycle_events"
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("procurement_cases.id"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("saas_tenants.tenant_id"), nullable=False)
    member_id: Mapped[str] = mapped_column(String(36), ForeignKey("saas_members.id"), nullable=False)
    go_decision_id: Mapped[str] = mapped_column(String(36), ForeignKey("company_portfolio_decisions.id"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String(24), nullable=False)
    event_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (
        UniqueConstraint("case_id", "revision", name="uq_company_lifecycle_revision"),
        UniqueConstraint("case_id", "idempotency_key", name="uq_company_lifecycle_replay"),
        CheckConstraint("revision > 0", name="ck_company_lifecycle_revision"),
        CheckConstraint("stage IN ('PREPARING','BLOCKED','READY','SUBMITTED','WON','LOST','REJECTED','WITHDRAWN','CANCELLED')", name="ck_company_lifecycle_stage"),
        Index("ix_company_lifecycle_tenant_case", "tenant_id", "case_id"),
    )


event.listen(CompanyCaseLifecycleEvent, "before_update", _immutable_company_decision)
event.listen(CompanyCaseLifecycleEvent, "before_delete", _immutable_company_decision)


class CompanyReadinessEvidence(UUIDPrimaryKeyMixin, Base):
    """Immutable partial-review binding to one READY event."""
    __tablename__ = "company_readiness_evidence"
    ready_event_id: Mapped[str] = mapped_column(String(36), ForeignKey("company_case_lifecycle_events.id"), nullable=False, unique=True)
    attempt_id: Mapped[str] = mapped_column(String(36), ForeignKey("commercial_capture_attempts.id"), nullable=False)
    member_id: Mapped[str] = mapped_column(String(36), ForeignKey("saas_members.id"), nullable=False)
    projection_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    projection_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


event.listen(CompanyReadinessEvidence, "before_update", _immutable_company_decision)
event.listen(CompanyReadinessEvidence, "before_delete", _immutable_company_decision)


class CompanyLifecycleArtifact(UUIDPrimaryKeyMixin, Base):
    """Immutable user-supplied bytes, never proof of platform origin."""
    __tablename__ = "company_lifecycle_artifacts"
    lifecycle_event_id: Mapped[str] = mapped_column(String(36), ForeignKey("company_case_lifecycle_events.id"), nullable=False, unique=True)
    member_id: Mapped[str] = mapped_column(String(36), ForeignKey("saas_members.id"), nullable=False)
    artifact_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    format_hint: Mapped[str] = mapped_column(String(8), nullable=False)
    raw_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    inspection_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (CheckConstraint("artifact_kind IN ('SUBMISSION_RECEIPT','OUTCOME_PROTOCOL')", name="ck_lifecycle_artifact_kind"), CheckConstraint("format_hint IN ('pdf','docx','xlsx')", name="ck_lifecycle_artifact_format"))


event.listen(CompanyLifecycleArtifact, "before_update", _immutable_company_decision)
event.listen(CompanyLifecycleArtifact, "before_delete", _immutable_company_decision)
