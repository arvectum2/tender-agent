"""add durable daily tender runs

Revision ID: 100_add_daily_tender_runs
Revises: 099_add_integration_outbox
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "100_add_daily_tender_runs"
down_revision: str | Sequence[str] | None = "099_add_integration_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("daily_tender_runs"):
        op.create_table(
            "daily_tender_runs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("run_id", sa.String(64), nullable=False),
            sa.Column("profile_id", sa.String(128), nullable=False),
            sa.Column("profile_version", sa.String(64), nullable=False),
            sa.Column("profile_snapshot_json", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("current_stage", sa.String(64), nullable=False),
            sa.Column("counts_json", sa.JSON(), nullable=False),
            sa.Column("digest_json", sa.JSON()),
            sa.Column("error_summary", sa.Text()),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("run_id", name="uq_daily_tender_runs_run_id"),
        )
        op.create_index(
            "ix_daily_tender_runs_profile_created",
            "daily_tender_runs",
            ["profile_id", "created_at"],
        )
        op.create_index(
            "ix_daily_tender_runs_status",
            "daily_tender_runs",
            ["status"],
        )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("daily_tender_run_items"):
        op.create_table(
            "daily_tender_run_items",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "run_id",
                sa.String(64),
                sa.ForeignKey("daily_tender_runs.run_id"),
                nullable=False,
            ),
            sa.Column("registry_number", sa.String(32), nullable=False),
            sa.Column("law", sa.String(16), nullable=False),
            sa.Column("source", sa.String(64), nullable=False),
            sa.Column("source_url", sa.Text()),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("customer_name", sa.Text()),
            sa.Column("nmck_amount", sa.Float()),
            sa.Column("deadline_at", sa.DateTime(timezone=True)),
            sa.Column("source_fingerprint", sa.String(64), nullable=False),
            sa.Column("query_hits_json", sa.JSON(), nullable=False),
            sa.Column("stage", sa.String(64), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("screening_status", sa.String(32)),
            sa.Column("screening_score", sa.Float()),
            sa.Column("screening_reasons_json", sa.JSON(), nullable=False),
            sa.Column("changed_since_previous", sa.Boolean(), nullable=False),
            sa.Column("deal_id", sa.String(32), sa.ForeignKey("deals.deal_id")),
            sa.Column("analysis_run_id", sa.String(64)),
            sa.Column("analysis_status", sa.String(64)),
            sa.Column("analysis_report_path", sa.Text()),
            sa.Column("agent_recommendation", sa.String(32)),
            sa.Column("agent_confidence", sa.String(16)),
            sa.Column("agent_rationale", sa.Text()),
            sa.Column("strongest_reasons_json", sa.JSON(), nullable=False),
            sa.Column("blockers_json", sa.JSON(), nullable=False),
            sa.Column("unknowns_json", sa.JSON(), nullable=False),
            sa.Column("synthesis_json", sa.JSON()),
            sa.Column("error", sa.Text()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "run_id",
                "registry_number",
                name="uq_daily_tender_run_item_registry",
            ),
        )
        op.create_index(
            "ix_daily_tender_run_items_run_status",
            "daily_tender_run_items",
            ["run_id", "status"],
        )
        op.create_index(
            "ix_daily_tender_run_items_registry",
            "daily_tender_run_items",
            ["registry_number"],
        )
        op.create_index(
            "ix_daily_tender_run_items_deal",
            "daily_tender_run_items",
            ["deal_id"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("daily_tender_run_items"):
        op.drop_table("daily_tender_run_items")
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("daily_tender_runs"):
        op.drop_table("daily_tender_runs")
