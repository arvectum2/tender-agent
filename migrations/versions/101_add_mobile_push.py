"""add mobile APNs registration and delivery ledger

Revision ID: 101_add_mobile_push
Revises: 100_add_daily_tender_runs
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "101_add_mobile_push"
down_revision: str | Sequence[str] | None = "100_add_daily_tender_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("mobile_device_access"):
        op.create_table(
            "mobile_device_access",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("device_id", sa.String(128), nullable=False),
            sa.Column("device_name", sa.String(128)),
            sa.Column("is_revoked", sa.Boolean(), nullable=False),
            sa.Column("paired_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True)),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("device_id", name="uq_mobile_device_access_device_id"),
        )
        op.create_index(
            "ix_mobile_device_access_revoked",
            "mobile_device_access",
            ["is_revoked", "updated_at"],
        )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("mobile_device_registrations"):
        op.create_table(
            "mobile_device_registrations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("device_id", sa.String(128), nullable=False),
            sa.Column("device_name", sa.String(128)),
            sa.Column("apns_token", sa.String(256), nullable=False),
            sa.Column("apns_environment", sa.String(16), nullable=False),
            sa.Column("app_version", sa.String(64)),
            sa.Column("is_enabled", sa.Boolean(), nullable=False),
            sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("device_id", name="uq_mobile_device_registrations_device_id"),
        )
        op.create_index(
            "ix_mobile_device_registration_enabled",
            "mobile_device_registrations",
            ["is_enabled", "updated_at"],
        )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("mobile_push_deliveries"):
        op.create_table(
            "mobile_push_deliveries",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("delivery_key", sa.String(64), nullable=False),
            sa.Column(
                "device_id",
                sa.String(128),
                sa.ForeignKey("mobile_device_registrations.device_id"),
                nullable=False,
            ),
            sa.Column("event_type", sa.String(32), nullable=False),
            sa.Column("deal_id", sa.String(32)),
            sa.Column("source_key", sa.String(256), nullable=False),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False),
            sa.Column("apns_id", sa.String(128)),
            sa.Column("error_code", sa.Text()),
            sa.Column("sent_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("delivery_key", name="uq_mobile_push_delivery_key"),
        )
        op.create_index(
            "ix_mobile_push_delivery_status",
            "mobile_push_deliveries",
            ["status", "created_at"],
        )
        op.create_index(
            "ix_mobile_push_delivery_device",
            "mobile_push_deliveries",
            ["device_id", "created_at"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("mobile_push_deliveries"):
        op.drop_table("mobile_push_deliveries")
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("mobile_device_registrations"):
        op.drop_table("mobile_device_registrations")
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("mobile_device_access"):
        op.drop_table("mobile_device_access")
