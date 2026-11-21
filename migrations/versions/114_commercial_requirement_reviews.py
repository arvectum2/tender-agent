"""Append-only source-linked human requirement review."""
import sqlalchemy as sa

from alembic import op

revision = '114_commercial_requirement_reviews'
down_revision = '113_commercial_attachment_evidence'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('commercial_requirement_reviews',
        sa.Column('id',sa.String(),primary_key=True),
        sa.Column('attachment_id',sa.String(36),sa.ForeignKey('commercial_attachment_evidence.id'),nullable=False),
        sa.Column('member_id',sa.String(36),sa.ForeignKey('saas_members.id'),nullable=False),
        sa.Column('fragment_key',sa.String(64),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('idempotency_key',sa.String(128),nullable=False),
        sa.Column('profile_fact_id',sa.String(36),sa.ForeignKey('company_profile_fact_versions.id'),nullable=False),
        sa.Column('reference_fact_id',sa.String(36),sa.ForeignKey('company_profile_fact_versions.id')),
        sa.Column('document_version_id',sa.String(36),sa.ForeignKey('company_document_versions.id')),
        sa.Column('review_json',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('attachment_id','fragment_key','revision',name='uq_commercial_review_revision'),
        sa.UniqueConstraint('attachment_id','idempotency_key',name='uq_commercial_review_replay'),
        sa.CheckConstraint('revision > 0',name='ck_commercial_review_revision'))


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM commercial_requirement_reviews')).scalar_one():
        raise RuntimeError('Cannot discard requirement review history')
    op.drop_table('commercial_requirement_reviews')
