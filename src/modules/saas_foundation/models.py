"""APR-05 durable tenant/auth/entitlement foundations.

Opaque secrets are never stored; only SHA-256 digests of 256-bit random tokens.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
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
