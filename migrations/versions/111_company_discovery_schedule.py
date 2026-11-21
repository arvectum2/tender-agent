"""Explicit schedule grants and persisted attempt budget; no automatic opt-in."""
import sqlalchemy as sa

from alembic import op

revision = "111_company_discovery_schedule"
down_revision = "110_company_discovery_runs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("company_discovery_runs", sa.Column("attempts_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.create_table(
        "company_discovery_schedules",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("saas_tenants.tenant_id"), nullable=False, unique=True),
        sa.Column("member_id", sa.String(36), sa.ForeignKey("saas_members.id"), nullable=False),
        sa.Column("profile_fact_id", sa.String(36), sa.ForeignKey("company_profile_fact_versions.id")),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("hour_moscow", sa.Integer(), nullable=False),
        sa.Column("sources_json", sa.JSON(), nullable=False),
        sa.Column("last_tick_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("hour_moscow >= 0 AND hour_moscow <= 23", name="ck_company_schedule_hour"),
    )
    op.create_index("ix_company_schedule_due", "company_discovery_schedules", ["enabled", "last_tick_at"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM company_discovery_schedules")).scalar_one() or op.get_bind().execute(sa.text("SELECT count(*) FROM company_discovery_runs WHERE CAST(attempts_json AS TEXT) <> '[]'")).scalar_one():
        raise RuntimeError("Cannot discard company schedule or attempt history")
    op.drop_index("ix_company_schedule_due", table_name="company_discovery_schedules")
    op.drop_table("company_discovery_schedules")
    with op.batch_alter_table("company_discovery_runs") as batch:
        batch.drop_column("attempts_json")
