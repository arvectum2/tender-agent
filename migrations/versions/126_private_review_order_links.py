"""Proposed exact same-tenant document/order links. No automatic association."""
import sqlalchemy as sa

from alembic import op

revision = '126_private_review_order_links'
down_revision = '125_private_review_retention'
branch_labels = None
depends_on = None

PARENTS = (
    ('application_review_previews', 'uq_retention_preview_tenant_id'),
    ('original_form_review_candidates', 'uq_retention_candidate_tenant_id'),
    ('private_review_retention_proposals', 'uq_retention_proposal_tenant_id'),
)


def upgrade():
    for table, name in PARENTS:
        op.create_index(name, table, ['tenant_id', 'id'], unique=True)
    op.create_table(
        'private_review_order_links',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('tenant_id', sa.String(64), nullable=False),
        sa.Column('proposal_id', sa.String(), nullable=False),
        sa.Column('preview_id', sa.String(), unique=True),
        sa.Column('candidate_id', sa.String(), unique=True),
        sa.Column('evidence_ref', sa.String(128), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id', 'proposal_id'],
                                ['private_review_retention_proposals.tenant_id', 'private_review_retention_proposals.id']),
        sa.ForeignKeyConstraint(['tenant_id', 'preview_id'],
                                ['application_review_previews.tenant_id', 'application_review_previews.id']),
        sa.ForeignKeyConstraint(['tenant_id', 'candidate_id'],
                                ['original_form_review_candidates.tenant_id', 'original_form_review_candidates.id']),
        sa.CheckConstraint('(preview_id IS NULL) <> (candidate_id IS NULL)', name='ck_retention_order_link_one_document'),
    )
    op.create_index('ix_retention_order_links_scope', 'private_review_order_links', ['tenant_id', 'proposal_id'])


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM private_review_order_links')).scalar_one():
        raise RuntimeError('Cannot discard proposed document-order links')
    op.drop_table('private_review_order_links')
    for table, name in PARENTS:
        op.drop_index(name, table_name=table)
