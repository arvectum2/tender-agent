"""Immutable user copy for one saved itemized scenario line."""
import sqlalchemy as sa

from alembic import op

revision = '119_company_cost_evidence'
down_revision = '118_company_price_scenarios'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('company_cost_evidence',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('scenario_id', sa.String(36), sa.ForeignKey('company_price_scenarios.id'), nullable=False),
        sa.Column('line_ordinal', sa.Integer(), nullable=False),
        sa.Column('line_sha256', sa.String(64), nullable=False),
        sa.Column('member_id', sa.String(36), sa.ForeignKey('saas_members.id'), nullable=False),
        sa.Column('document_kind', sa.String(24), nullable=False),
        sa.Column('format_hint', sa.String(8), nullable=False),
        sa.Column('raw_bytes', sa.LargeBinary(), nullable=False),
        sa.Column('inspection_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('scenario_id','line_ordinal',name='uq_company_cost_evidence_line'),
        sa.CheckConstraint('line_ordinal BETWEEN 1 AND 60',name='ck_cost_evidence_ordinal'),
        sa.CheckConstraint("document_kind IN ('QUOTE','INVOICE','CONTRACT','TIMESHEET','OTHER')",name='ck_cost_evidence_kind'),
        sa.CheckConstraint("format_hint IN ('pdf','docx','xlsx')",name='ck_cost_evidence_format'))


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM company_cost_evidence')).scalar_one():
        raise RuntimeError('Cannot discard cost evidence')
    op.drop_table('company_cost_evidence')
