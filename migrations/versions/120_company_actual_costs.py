"""Versioned user-reported actual-cost snapshots."""
import sqlalchemy as sa

from alembic import op

revision = '120_company_actual_costs'
down_revision = '119_company_cost_evidence'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('company_actual_cost_snapshots',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('scenario_id', sa.String(36), sa.ForeignKey('company_price_scenarios.id'), nullable=False),
        sa.Column('member_id', sa.String(36), sa.ForeignKey('saas_members.id'), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('idempotency_key', sa.String(128), nullable=False),
        sa.Column('input_json', sa.JSON(), nullable=False),
        sa.Column('result_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('scenario_id','revision',name='uq_actual_cost_revision'),
        sa.UniqueConstraint('scenario_id','idempotency_key',name='uq_actual_cost_replay'),
        sa.CheckConstraint('revision BETWEEN 1 AND 30',name='ck_actual_cost_revision'))


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM company_actual_cost_snapshots')).scalar_one():
        raise RuntimeError('Cannot discard actual cost history')
    op.drop_table('company_actual_cost_snapshots')
