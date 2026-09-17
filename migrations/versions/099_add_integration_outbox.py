"""add internal integration outbox
Revision ID: 099_add_integration_outbox
Revises: 098_add_procurement_monitoring
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa
revision: str = "099_add_integration_outbox"
down_revision: str | Sequence[str] | None = "098_add_procurement_monitoring"
branch_labels = None
depends_on = None
def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("integration_outbox_events"):
        op.create_table("integration_outbox_events", sa.Column("id", sa.String(36), primary_key=True), sa.Column("event_key", sa.String(128), nullable=False), sa.Column("event_type", sa.String(64), nullable=False), sa.Column("tenant_id", sa.String(128)), sa.Column("aggregate_type", sa.String(64), nullable=False), sa.Column("aggregate_id", sa.String(256), nullable=False), sa.Column("envelope", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("event_key", name="uq_integration_outbox_event_key"))
        op.create_index("ix_integration_outbox_tenant_created", "integration_outbox_events", ["tenant_id", "created_at"])
        op.create_index("ix_integration_outbox_type_created", "integration_outbox_events", ["event_type", "created_at"])
def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("integration_outbox_events"): op.drop_table("integration_outbox_events")
