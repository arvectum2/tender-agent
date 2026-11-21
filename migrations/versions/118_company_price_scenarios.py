"""Owned append-only PRICE-01 scenario revisions."""
import sqlalchemy as sa

from alembic import op

revision = '118_company_price_scenarios'
down_revision = '117_company_lifecycle_artifacts'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('company_price_scenarios',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('case_id', sa.String(36), sa.ForeignKey('procurement_cases.id'), nullable=False),
        sa.Column('tenant_id', sa.String(64), sa.ForeignKey('saas_tenants.tenant_id'), nullable=False),
        sa.Column('member_id', sa.String(36), sa.ForeignKey('saas_members.id'), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('idempotency_key', sa.String(128), nullable=False),
        sa.Column('input_json', sa.JSON(), nullable=False),
        sa.Column('result_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('case_id','revision',name='uq_company_price_revision'),
        sa.UniqueConstraint('case_id','idempotency_key',name='uq_company_price_replay'),
        sa.CheckConstraint('revision BETWEEN 1 AND 30',name='ck_company_price_revision'))
    op.create_index('ix_company_price_tenant_case','company_price_scenarios',['tenant_id','case_id'])


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM company_price_scenarios')).scalar_one():
        raise RuntimeError('Cannot discard company price history')
    op.drop_index('ix_company_price_tenant_case',table_name='company_price_scenarios')
    op.drop_table('company_price_scenarios')
