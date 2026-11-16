"""Bounded commercial capture reservations and immutable original snapshots."""
import sqlalchemy as sa

from alembic import op

revision = "112_commercial_card_snapshots"
down_revision = "111_company_discovery_schedule"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "commercial_capture_attempts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("saas_tenants.tenant_id"), nullable=False),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("procurement_cases.id"), nullable=False),
        sa.Column("member_id", sa.String(36), sa.ForeignKey("saas_members.id"), nullable=False),
        sa.Column("capture_day", sa.String(10), nullable=False),
        sa.Column("source_url", sa.String(650), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_id", "capture_day", name="uq_commercial_capture_case_day"),
    )
    op.create_index("ix_commercial_capture_tenant_day", "commercial_capture_attempts", ["tenant_id", "capture_day"])
    op.create_table(
        "commercial_card_snapshots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("attempt_id", sa.String(36), sa.ForeignKey("commercial_capture_attempts.id"), nullable=False, unique=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("original_html", sa.LargeBinary(), nullable=True),
        sa.Column("receipt_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("outcome IN ('CAPTURED', 'SOURCE_UNAVAILABLE', 'UNSUPPORTED_CARD')", name="ck_commercial_snapshot_outcome"),
    )


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM commercial_capture_attempts")).scalar_one():
        raise RuntimeError("Cannot discard commercial capture history")
    op.drop_table("commercial_card_snapshots")
    op.drop_index("ix_commercial_capture_tenant_day", table_name="commercial_capture_attempts")
    op.drop_table("commercial_capture_attempts")
