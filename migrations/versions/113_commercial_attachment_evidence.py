"""Immutable user-supplied commercial attachment evidence; no auto-import."""
import sqlalchemy as sa

from alembic import op

revision = '113_commercial_attachment_evidence'
down_revision = '112_commercial_card_snapshots'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('commercial_attachment_evidence',
        sa.Column('id',sa.String(),primary_key=True),
        sa.Column('attempt_id',sa.String(36),sa.ForeignKey('commercial_capture_attempts.id'),nullable=False),
        sa.Column('member_id',sa.String(36),sa.ForeignKey('saas_members.id'),nullable=False),
        sa.Column('candidate_id',sa.String(64),nullable=False),
        sa.Column('source_url',sa.String(650),nullable=False),
        sa.Column('raw_bytes',sa.LargeBinary(),nullable=False),
        sa.Column('inspection_json',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('attempt_id','candidate_id',name='uq_commercial_attachment_candidate'))


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM commercial_attachment_evidence')).scalar_one():
        raise RuntimeError('Cannot discard commercial attachment evidence')
    op.drop_table('commercial_attachment_evidence')
