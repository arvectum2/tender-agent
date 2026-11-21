"""Company-scoped human decision history on existing cases; no legacy backfill."""
import sqlalchemy as sa

from alembic import op

revision = "108_company_portfolio_decisions"
down_revision = "107_add_procurement_learning_observations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "company_portfolio_decisions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("procurement_cases.id"), nullable=False),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("saas_tenants.tenant_id"), nullable=False),
        sa.Column("member_id", sa.String(36), sa.ForeignKey("saas_members.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("deferred_until", sa.DateTime(timezone=True)),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_id", "revision", name="uq_company_case_decision_revision"),
        sa.UniqueConstraint("case_id", "idempotency_key", name="uq_company_case_decision_idem"),
        sa.CheckConstraint("revision > 0", name="ck_company_decision_revision"),
        sa.CheckConstraint("action IN ('GO', 'NO_GO', 'DEFER')", name="ck_company_decision_action"),
        sa.CheckConstraint("(action = 'DEFER' AND deferred_until IS NOT NULL) OR (action <> 'DEFER' AND deferred_until IS NULL)", name="ck_company_decision_defer"),
    )
    op.create_index("ix_company_decisions_tenant_case", "company_portfolio_decisions", ["tenant_id", "case_id"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM company_portfolio_decisions")).scalar_one():
        raise RuntimeError("Cannot remove populated company decision history without reviewed archival plan")
    op.drop_index("ix_company_decisions_tenant_case", table_name="company_portfolio_decisions")
    op.drop_table("company_portfolio_decisions")
