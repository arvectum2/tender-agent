"""Immutable company case evidence references and frozen profile identity."""
import sqlalchemy as sa

from alembic import op

revision = "109_company_portfolio_evidence"
down_revision = "108_company_portfolio_decisions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "company_portfolio_evidence",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("procurement_cases.id"), nullable=False),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("saas_tenants.tenant_id"), nullable=False),
        sa.Column("member_id", sa.String(36), sa.ForeignKey("saas_members.id"), nullable=False),
        sa.Column("run_id", sa.String(128), sa.ForeignKey("saas_runs.run_id"), nullable=False),
        sa.Column("profile_fact_id", sa.String(36), sa.ForeignKey("company_profile_fact_versions.id"), nullable=False),
        sa.Column("source_snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_id", "run_id", "profile_fact_id", name="uq_company_case_run_profile"),
    )
    op.create_index("ix_company_evidence_tenant_case", "company_portfolio_evidence", ["tenant_id", "case_id"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM company_portfolio_evidence")).scalar_one():
        raise RuntimeError("Cannot remove populated company evidence without reviewed archival plan")
    op.drop_index("ix_company_evidence_tenant_case", table_name="company_portfolio_evidence")
    op.drop_table("company_portfolio_evidence")
