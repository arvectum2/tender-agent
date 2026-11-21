"""Preserve the partial qualification review bound to a READY event."""
import sqlalchemy as sa

from alembic import op

revision = '116_company_readiness_evidence'
down_revision = '115_company_case_lifecycle'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('company_readiness_evidence',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('ready_event_id', sa.String(36), sa.ForeignKey('company_case_lifecycle_events.id'), nullable=False, unique=True),
        sa.Column('attempt_id', sa.String(36), sa.ForeignKey('commercial_capture_attempts.id'), nullable=False),
        sa.Column('member_id', sa.String(36), sa.ForeignKey('saas_members.id'), nullable=False),
        sa.Column('projection_sha256', sa.String(64), nullable=False),
        sa.Column('projection_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM company_readiness_evidence')).scalar_one():
        raise RuntimeError('Cannot discard readiness evidence')
    op.drop_table('company_readiness_evidence')
