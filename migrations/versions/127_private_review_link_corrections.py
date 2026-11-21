"""Append-only proposed link corrections."""
import sqlalchemy as sa

from alembic import op

revision = '127_private_review_link_corrections'
down_revision = '126_private_review_order_links'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('uq_retention_link_tenant_id', 'private_review_order_links', ['tenant_id', 'id'], unique=True)
    op.create_table(
        'private_review_link_corrections',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('tenant_id', sa.String(64), nullable=False),
        sa.Column('link_id', sa.String(), nullable=False),
        sa.Column('proposal_id', sa.String(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('evidence_ref', sa.String(128), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id', 'link_id'],
                                ['private_review_order_links.tenant_id', 'private_review_order_links.id']),
        sa.ForeignKeyConstraint(['tenant_id', 'proposal_id'],
                                ['private_review_retention_proposals.tenant_id', 'private_review_retention_proposals.id']),
        sa.UniqueConstraint('tenant_id', 'link_id', 'revision', name='uq_retention_link_correction_revision'),
        sa.CheckConstraint('revision > 0 AND revision <= 200', name='ck_retention_link_correction_revision'),
    )


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM private_review_link_corrections')).scalar_one():
        raise RuntimeError('Cannot discard proposed link correction history')
    op.drop_table('private_review_link_corrections')
    op.drop_index('uq_retention_link_tenant_id', table_name='private_review_order_links')
