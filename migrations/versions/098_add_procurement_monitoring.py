"""add procurement monitoring persistence

Revision ID: 098_add_procurement_monitoring
Revises: 097_add_arv052_expert_review
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "098_add_procurement_monitoring"
down_revision: str | Sequence[str] | None = "097_add_arv052_expert_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("procurement_watches"):
        op.create_table("procurement_watches", sa.Column("id", sa.String(36), primary_key=True), sa.Column("source", sa.String(64), nullable=False), sa.Column("external_id", sa.String(256), nullable=False), sa.Column("source_url", sa.Text()), sa.Column("saved_search", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("source", "external_id", name="uq_procurement_watches_source_external"))
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("procurement_watch_snapshots"):
        op.create_table("procurement_watch_snapshots", sa.Column("id", sa.String(36), primary_key=True), sa.Column("watch_id", sa.String(36), sa.ForeignKey("procurement_watches.id"), nullable=False), sa.Column("fingerprint", sa.String(64), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("watch_id", "fingerprint", name="uq_procurement_watch_snapshot_fingerprint"))
        op.create_index("ix_procurement_watch_snapshots_watch_created", "procurement_watch_snapshots", ["watch_id", "created_at"])
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("procurement_watch_events"):
        op.create_table("procurement_watch_events", sa.Column("id", sa.String(36), primary_key=True), sa.Column("watch_id", sa.String(36), sa.ForeignKey("procurement_watches.id"), nullable=False), sa.Column("event_key", sa.String(64), nullable=False, unique=True), sa.Column("outcome", sa.String(32), nullable=False), sa.Column("source_url", sa.Text()), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
        op.create_index("ix_procurement_watch_events_watch_created", "procurement_watch_events", ["watch_id", "created_at"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in ("procurement_watch_events", "procurement_watch_snapshots", "procurement_watches"):
        if inspector.has_table(table):
            op.drop_table(table)
            inspector = sa.inspect(op.get_bind())
