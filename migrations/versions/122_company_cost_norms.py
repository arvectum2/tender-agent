"""Versioned internal corporate cost norms."""
import sqlalchemy as sa

from alembic import op

revision = '122_company_cost_norms'
down_revision = '121_company_actual_evidence'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('company_cost_norm_versions',
        sa.Column('id',sa.String(),primary_key=True),
        sa.Column('tenant_id',sa.String(64),sa.ForeignKey('saas_tenants.tenant_id'),nullable=False),
        sa.Column('member_id',sa.String(36),sa.ForeignKey('saas_members.id'),nullable=False),
        sa.Column('norm_key',sa.String(64),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('action',sa.String(12),nullable=False),
        sa.Column('idempotency_key',sa.String(128),nullable=False),
        sa.Column('input_json',sa.JSON(),nullable=False),
        sa.Column('result_json',sa.JSON(),nullable=False),
        sa.Column('record_sha256',sa.String(64),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('tenant_id','norm_key','revision',name='uq_cost_norm_revision'),
        sa.UniqueConstraint('tenant_id','idempotency_key',name='uq_cost_norm_replay'),
        sa.CheckConstraint('revision BETWEEN 1 AND 100',name='ck_cost_norm_revision'),
        sa.CheckConstraint("action IN ('APPROVED','WITHDRAWN')",name='ck_cost_norm_action'))


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM company_cost_norm_versions')).scalar_one():
        raise RuntimeError('Cannot discard corporate norm history')
    op.drop_table('company_cost_norm_versions')
