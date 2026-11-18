"""Private applicant preview and append-only internal acknowledgement history."""
import sqlalchemy as sa

from alembic import op

revision = '123_application_review'
down_revision = '122_company_cost_norms'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('application_review_previews',
        sa.Column('id',sa.String(),primary_key=True),
        sa.Column('tenant_id',sa.String(64),sa.ForeignKey('saas_tenants.tenant_id'),nullable=False),
        sa.Column('member_id',sa.String(36),sa.ForeignKey('saas_members.id'),nullable=False),
        sa.Column('run_id',sa.String(128),sa.ForeignKey('saas_runs.run_id'),nullable=False),
        sa.Column('procurement_ref',sa.String(64),nullable=False),
        sa.Column('input_json',sa.JSON(),nullable=False),
        sa.Column('archive_bytes',sa.LargeBinary(),nullable=False),
        *[sa.Column(k,sa.String(64),nullable=False) for k in ('archive_sha256','plan_sha256','inputs_sha256','evidence_sha256')],
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_application_preview_scope','application_review_previews',['tenant_id','run_id','created_at'])
    op.create_table('application_review_decisions',
        sa.Column('id',sa.String(),primary_key=True),
        sa.Column('preview_id',sa.String(),sa.ForeignKey('application_review_previews.id'),nullable=False,unique=True),
        sa.Column('tenant_id',sa.String(64),sa.ForeignKey('saas_tenants.tenant_id'),nullable=False),
        sa.Column('member_id',sa.String(36),sa.ForeignKey('saas_members.id'),nullable=False),
        sa.Column('archive_sha256',sa.String(64),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))


def downgrade():
    conn=op.get_bind()
    for table in ('application_review_decisions','application_review_previews'):
        if conn.execute(sa.text('SELECT count(*) FROM '+table)).scalar_one():
            raise RuntimeError('Cannot discard private application review history')
    op.drop_table('application_review_decisions')
    op.drop_index('ix_application_preview_scope',table_name='application_review_previews')
    op.drop_table('application_review_previews')
