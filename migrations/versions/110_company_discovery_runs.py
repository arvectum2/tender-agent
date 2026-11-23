"""Company-scoped bounded discovery checkpoints; no legacy backfill."""
import sqlalchemy as sa

from alembic import op

revision = "110_company_discovery_runs"
down_revision = "109_company_portfolio_evidence"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "company_discovery_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("saas_tenants.tenant_id"), nullable=False),
        sa.Column("member_id", sa.String(36), sa.ForeignKey("saas_members.id"), nullable=False),
        sa.Column("profile_fact_id", sa.String(36), sa.ForeignKey("company_profile_fact_versions.id"), nullable=False),
        sa.Column("run_day", sa.String(10), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("results_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "run_day", name="uq_company_discovery_tenant_day"),
    )
    op.create_index("ix_company_discovery_tenant_day", "company_discovery_runs", ["tenant_id", "run_day"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM company_discovery_runs")).scalar_one():
        raise RuntimeError("Cannot remove populated company discovery history without reviewed archival plan")
    op.drop_index("ix_company_discovery_tenant_day", table_name="company_discovery_runs")
    op.drop_table("company_discovery_runs")
