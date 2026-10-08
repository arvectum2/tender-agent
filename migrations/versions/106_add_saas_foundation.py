"""APR-05 tenant roles, invitations, hashed tokens, legal, quotas, runs and audit.

Revision ID: 106_add_saas_foundation
Revises: 105_add_company_profile_store
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "106_add_saas_foundation"
down_revision: str | Sequence[str] | None = "105_add_company_profile_store"
branch_labels = None
depends_on = None


def _id():
    return sa.Column("id", sa.String(36), primary_key=True, nullable=False)


def _tenant():
    return sa.Column("tenant_id", sa.String(64), sa.ForeignKey("saas_tenants.tenant_id"), nullable=False)


def _member(nullable=False):
    return sa.Column("member_id", sa.String(36), sa.ForeignKey("saas_members.id"), nullable=nullable)


def _created():
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    op.create_table(
        "saas_tenants", _id(),
        sa.Column("tenant_id", sa.String(64), unique=True, nullable=False),
        sa.Column("customer_id", sa.String(64), sa.ForeignKey("customer_profiles.customer_id"), unique=True, nullable=False),
        sa.Column("plan_code", sa.String(32), nullable=False),
        sa.Column("lifecycle", sa.String(32), nullable=False),
        sa.Column("billing_state", sa.String(32), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=False),
        _created(),
    )
    op.create_table(
        "saas_members", _id(), _tenant(),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("role", sa.String(24), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        _created(),
    )
    op.create_index("ix_saas_member_tenant", "saas_members", ["tenant_id"])
    op.create_table(
        "saas_invitations", _id(), _tenant(),
        sa.Column("role", sa.String(24), nullable=False),
        sa.Column("token_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("issued_by_member_id", sa.String(36), sa.ForeignKey("saas_members.id")),
        sa.Column("acquisition_channel", sa.String(40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        _created(),
    )
    op.create_index("ix_saas_invitation_tenant", "saas_invitations", ["tenant_id"])
    op.create_table(
        "saas_access_tokens", _id(), _tenant(), _member(),
        sa.Column("token_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        _created(),
    )
    op.create_index("ix_saas_token_member", "saas_access_tokens", ["tenant_id", "member_id"])
    op.create_table(
        "saas_legal_acceptances", _id(), _tenant(), _member(),
        sa.Column("terms_version", sa.String(64), nullable=False),
        sa.Column("privacy_version", sa.String(64), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_saas_legal_member", "saas_legal_acceptances", ["tenant_id", "member_id"])
    op.create_table(
        "saas_usage_counters", _id(), _tenant(),
        sa.Column("period_utc", sa.String(7), nullable=False),
        sa.Column("metric", sa.String(32), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False),
        sa.UniqueConstraint("tenant_id", "period_utc", "metric", name="uq_saas_usage_counter"),
    )
    op.create_table(
        "saas_runs", _id(), _tenant(),
        sa.Column("run_id", sa.String(128), nullable=False, unique=True),
        sa.Column("created_by_member_id", sa.String(36), sa.ForeignKey("saas_members.id"), nullable=False),
        _created(),
    )
    op.create_index("ix_saas_run_tenant", "saas_runs", ["tenant_id"])
    op.create_table(
        "saas_payment_evidence", _id(), _tenant(),
        sa.Column("external_reference", sa.String(160), nullable=False, unique=True),
        sa.Column("operator_note", sa.String(512), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "saas_audit_events", _id(), _tenant(), _member(nullable=True),
        sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        _created(),
    )
    op.create_index("ix_saas_audit_tenant", "saas_audit_events", ["tenant_id", "created_at"])


def downgrade() -> None:
    for name, index in (
        ("saas_audit_events", "ix_saas_audit_tenant"),
        ("saas_runs", "ix_saas_run_tenant"),
        ("saas_legal_acceptances", "ix_saas_legal_member"),
        ("saas_access_tokens", "ix_saas_token_member"),
        ("saas_invitations", "ix_saas_invitation_tenant"),
        ("saas_members", "ix_saas_member_tenant"),
    ):
        op.drop_index(index, table_name=name)
    for name in (
        "saas_audit_events", "saas_payment_evidence", "saas_runs",
        "saas_usage_counters", "saas_legal_acceptances",
        "saas_access_tokens", "saas_invitations", "saas_members", "saas_tenants",
    ):
        op.drop_table(name)
