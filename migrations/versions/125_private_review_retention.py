"""Internal retention proposal history. No deletion or access logic."""
import sqlalchemy as sa

from alembic import op

revision = '125_private_review_retention'
down_revision = '124_original_form_review'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'private_review_retention_proposals',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('tenant_id', sa.String(64), sa.ForeignKey('saas_tenants.tenant_id'), nullable=False),
        sa.Column('order_ref', sa.String(128), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('policy_ref', sa.String(128), nullable=False),
        sa.Column('order_ended_on', sa.Date()),
        sa.Column('end_evidence_ref', sa.String(128)),
        sa.Column('working_days', sa.Integer(), nullable=False),
        sa.Column('backup_days', sa.Integer(), nullable=False),
        sa.Column('hold_state', sa.String(16), nullable=False),
        sa.Column('hold_evidence_ref', sa.String(128)),
        sa.Column('hold_review_on', sa.Date()),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('tenant_id', 'order_ref', 'revision', name='uq_retention_proposal_revision'),
        sa.CheckConstraint('revision > 0', name='ck_retention_proposal_revision'),
        sa.CheckConstraint('working_days >= 0 AND working_days <= 3650 AND backup_days >= working_days AND backup_days <= 3650',
                           name='ck_retention_proposal_days'),
        sa.CheckConstraint('(order_ended_on IS NULL AND end_evidence_ref IS NULL) OR (order_ended_on IS NOT NULL AND end_evidence_ref IS NOT NULL)',
                           name='ck_retention_proposal_end'),
        sa.CheckConstraint("(hold_state = 'UNKNOWN' AND hold_evidence_ref IS NULL AND hold_review_on IS NULL) OR "
                           "(hold_state IN ('ACTIVE','CLEAR') AND hold_evidence_ref IS NOT NULL AND hold_review_on IS NOT NULL)",
                           name='ck_retention_proposal_hold'),
    )


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM private_review_retention_proposals')).scalar_one():
        raise RuntimeError('Cannot discard retention proposal history')
    op.drop_table('private_review_retention_proposals')
