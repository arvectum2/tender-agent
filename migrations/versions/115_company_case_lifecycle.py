"""Human-attested company case progress, append-only."""
import sqlalchemy as sa

from alembic import op

revision = '115_company_case_lifecycle'
down_revision = '114_commercial_requirement_reviews'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('company_case_lifecycle_events',
        sa.Column('id',sa.String(),primary_key=True),
        sa.Column('case_id',sa.String(36),sa.ForeignKey('procurement_cases.id'),nullable=False),
        sa.Column('tenant_id',sa.String(64),sa.ForeignKey('saas_tenants.tenant_id'),nullable=False),
        sa.Column('member_id',sa.String(36),sa.ForeignKey('saas_members.id'),nullable=False),
        sa.Column('go_decision_id',sa.String(36),sa.ForeignKey('company_portfolio_decisions.id'),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('stage',sa.String(24),nullable=False),
        sa.Column('event_json',sa.JSON(),nullable=False),
        sa.Column('idempotency_key',sa.String(128),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('case_id','revision',name='uq_company_lifecycle_revision'),
        sa.UniqueConstraint('case_id','idempotency_key',name='uq_company_lifecycle_replay'),
        sa.CheckConstraint('revision > 0',name='ck_company_lifecycle_revision'),
        sa.CheckConstraint("stage IN ('PREPARING','BLOCKED','READY','SUBMITTED','WON','LOST','REJECTED','WITHDRAWN','CANCELLED')",name='ck_company_lifecycle_stage'))
    op.create_index('ix_company_lifecycle_tenant_case','company_case_lifecycle_events',['tenant_id','case_id'])


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM company_case_lifecycle_events')).scalar_one():
        raise RuntimeError('Cannot discard case lifecycle history')
    op.drop_index('ix_company_lifecycle_tenant_case',table_name='company_case_lifecycle_events')
    op.drop_table('company_case_lifecycle_events')
