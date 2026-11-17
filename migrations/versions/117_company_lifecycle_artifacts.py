"""Preserve exact user-provided receipt/protocol bytes on a lifecycle event."""
import sqlalchemy as sa

from alembic import op

revision = '117_company_lifecycle_artifacts'
down_revision = '116_company_readiness_evidence'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('company_lifecycle_artifacts',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('lifecycle_event_id', sa.String(36), sa.ForeignKey('company_case_lifecycle_events.id'), nullable=False, unique=True),
        sa.Column('member_id', sa.String(36), sa.ForeignKey('saas_members.id'), nullable=False),
        sa.Column('artifact_kind', sa.String(24), nullable=False),
        sa.Column('format_hint', sa.String(8), nullable=False),
        sa.Column('raw_bytes', sa.LargeBinary(), nullable=False),
        sa.Column('inspection_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("artifact_kind IN ('SUBMISSION_RECEIPT','OUTCOME_PROTOCOL')", name='ck_lifecycle_artifact_kind'),
        sa.CheckConstraint("format_hint IN ('pdf','docx','xlsx')", name='ck_lifecycle_artifact_format'))


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM company_lifecycle_artifacts')).scalar_one():
        raise RuntimeError('Cannot discard lifecycle artifacts')
    op.drop_table('company_lifecycle_artifacts')
