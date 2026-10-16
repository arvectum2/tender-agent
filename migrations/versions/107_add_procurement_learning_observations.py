"""Add append-only candidate observations to the existing Tender Agent PostgreSQL.

Revision ID: 107_add_procurement_learning_observations
Revises: 106_add_saas_foundation
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "107_add_procurement_learning_observations"
down_revision: str | Sequence[str] | None = "106_add_saas_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "procurement_learning_observations",
        sa.Column("observation_id", sa.String(64), primary_key=True),
        sa.Column("event_kind", sa.String(40), nullable=False),
        sa.Column("procurement_ref", sa.String(256), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("provenance_sha256", sa.String(64), nullable=False),
        sa.Column("participation", sa.String(32), nullable=False),
        sa.Column("review_state", sa.String(40), nullable=False),
        sa.Column("training_status", sa.String(40), nullable=False),
        sa.Column("candidate_split", sa.String(64), nullable=False),
        sa.Column("visibility_scope", sa.String(32), nullable=False),
        sa.Column("customer_id", sa.String(64), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "training_status = 'candidate_unreviewed'",
            name="ck_learning_observation_not_gold",
        ),
        sa.CheckConstraint(
            "visibility_scope = 'owner_internal' OR "
            "(visibility_scope = 'tenant' AND customer_id IS NOT NULL)",
            name="ck_learning_observation_scoped",
        ),
    )
    op.create_index("ix_learning_observations_procurement", "procurement_learning_observations", ["procurement_ref"])
    op.create_index("ix_learning_observations_customer", "procurement_learning_observations", ["customer_id", "created_at"])
    op.create_index("ix_learning_observations_kind", "procurement_learning_observations", ["event_kind"])


def downgrade() -> None:
    # Deliberately fail closed: learning/provenance observations are immutable
    # data, not disposable schema. Rollback requires explicit archived migration.
    raise RuntimeError("Cannot drop canonical procurement evidence without a reviewed archival plan.")
