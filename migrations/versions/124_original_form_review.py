"""Private original form candidates and independent review receipts."""
import sqlalchemy as sa

from alembic import op

revision = '124_original_form_review'
down_revision = '123_application_review'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('original_form_review_candidates',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('tenant_id', sa.String(64), sa.ForeignKey('saas_tenants.tenant_id'), nullable=False),
        sa.Column('run_id', sa.String(128), sa.ForeignKey('saas_runs.run_id'), nullable=False),
        sa.Column('creator_id', sa.String(36), sa.ForeignKey('saas_members.id'), nullable=False),
        sa.Column('reviewer_id', sa.String(36), sa.ForeignKey('saas_members.id'), nullable=False),
        sa.Column('input_json', sa.JSON(), nullable=False),
        sa.Column('receipt_json', sa.JSON(), nullable=False),
        sa.Column('document_bytes', sa.LargeBinary(), nullable=False),
        sa.Column('document_sha256', sa.String(64), nullable=False),
        sa.Column('candidate_sha256', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('creator_id <> reviewer_id', name='ck_original_form_distinct_members'))
    op.create_index('ix_original_form_review_scope', 'original_form_review_candidates',
                    ['tenant_id', 'run_id', 'created_at'])
    op.create_table('original_form_review_receipts',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('candidate_id', sa.String(), sa.ForeignKey('original_form_review_candidates.id'), nullable=False, unique=True),
        sa.Column('reviewer_id', sa.String(36), sa.ForeignKey('saas_members.id'), nullable=False),
        sa.Column('candidate_sha256', sa.String(64), nullable=False),
        sa.Column('document_sha256', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    conn = op.get_bind()
    for table in ('original_form_review_receipts', 'original_form_review_candidates'):
        if conn.execute(sa.text('SELECT count(*) FROM '+table)).scalar_one():
            raise RuntimeError('Cannot discard original form review history')
    op.drop_table('original_form_review_receipts')
    op.drop_index('ix_original_form_review_scope', table_name='original_form_review_candidates')
    op.drop_table('original_form_review_candidates')
