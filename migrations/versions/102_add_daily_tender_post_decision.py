"""add Daily Tender Run post-decision state

Revision ID: 102_add_daily_tender_post_decision
Revises: 101_add_mobile_push
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "102_add_daily_tender_post_decision"
down_revision: str | Sequence[str] | None = "101_add_mobile_push"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("daily_tender_run_items"):
        return
    columns = _columns("daily_tender_run_items")
    if "human_decision" not in columns:
        op.add_column(
            "daily_tender_run_items",
            sa.Column("human_decision", sa.String(32), nullable=True),
        )
    if "human_decision_id" not in columns:
        op.add_column(
            "daily_tender_run_items",
            sa.Column("human_decision_id", sa.String(64), nullable=True),
        )
    if "post_decision_json" not in columns:
        op.add_column(
            "daily_tender_run_items",
            sa.Column("post_decision_json", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("daily_tender_run_items"):
        return
    columns = _columns("daily_tender_run_items")
    if "post_decision_json" in columns:
        op.drop_column("daily_tender_run_items", "post_decision_json")
    if "human_decision_id" in columns:
        op.drop_column("daily_tender_run_items", "human_decision_id")
    if "human_decision" in columns:
        op.drop_column("daily_tender_run_items", "human_decision")
