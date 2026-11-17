"""Immutable actual cost document copies."""
import sqlalchemy as sa

from alembic import op

revision = '121_company_actual_evidence'
down_revision = '120_company_actual_costs'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('company_actual_cost_evidence',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('snapshot_id', sa.String(36), sa.ForeignKey('company_actual_cost_snapshots.id'), nullable=False),
        sa.Column('row_kind', sa.String(12), nullable=False),
        sa.Column('line_ordinal', sa.Integer(), nullable=False),
        sa.Column('line_sha256', sa.String(64), nullable=False),
        sa.Column('member_id', sa.String(36), sa.ForeignKey('saas_members.id'), nullable=False),
        sa.Column('document_kind', sa.String(24), nullable=False),
        sa.Column('format_hint', sa.String(8), nullable=False),
        sa.Column('raw_bytes', sa.LargeBinary(), nullable=False),
        sa.Column('inspection_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('snapshot_id','row_kind','line_ordinal',name='uq_actual_evidence_line'),
        sa.CheckConstraint("(row_kind = 'PLANNED' AND line_ordinal BETWEEN 1 AND 60) OR (row_kind = 'UNPLANNED' AND line_ordinal BETWEEN 1 AND 30)",name='ck_actual_evidence_line'),
        sa.CheckConstraint("document_kind IN ('INVOICE','CONTRACT','TIMESHEET','ACCEPTANCE_ACT','PAYMENT_RECORD','OTHER')",name='ck_actual_evidence_kind'),
        sa.CheckConstraint("format_hint IN ('pdf','docx','xlsx')",name='ck_actual_evidence_format'))


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM company_actual_cost_evidence')).scalar_one():
        raise RuntimeError('Cannot discard actual cost evidence')
    op.drop_table('company_actual_cost_evidence')
