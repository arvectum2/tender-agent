"""add append-only ProcurementCase collaboration journal

Revision ID: 103_add_case_collaboration
Revises: 102_add_daily_tender_post_decision
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "103_add_case_collaboration"
down_revision: str | Sequence[str] | None = "102_add_daily_tender_post_decision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("case_journal_entries"):
        op.create_table(
            "case_journal_entries",
            sa.Column("customer_id", sa.String(64), nullable=False),
            sa.Column("project_id", sa.String(36), nullable=False),
            sa.Column("procurement_case_id", sa.String(36), nullable=False),
            sa.Column("entry_type", sa.String(24), nullable=False),
            sa.Column("actor_type", sa.String(32), nullable=False),
            sa.Column("actor_ref", sa.String(256), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("decision_code", sa.String(128), nullable=True),
            sa.Column("supersedes_entry_id", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("id", sa.String(), nullable=False),
            sa.ForeignKeyConstraint(["procurement_case_id"], ["procurement_cases.id"]),
            sa.ForeignKeyConstraint(
                ["supersedes_entry_id"], ["case_journal_entries.id"]
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_case_journal_scope_created",
            "case_journal_entries",
            ["customer_id", "project_id", "procurement_case_id", "created_at"],
        )
        op.create_index(
            "ix_case_journal_case_entry_type",
            "case_journal_entries",
            ["procurement_case_id", "entry_type"],
        )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("case_journal_mentions"):
        op.create_table(
            "case_journal_mentions",
            sa.Column("journal_entry_id", sa.String(36), nullable=False),
            sa.Column("mention_ref", sa.String(256), nullable=False),
            sa.Column("notification_state", sa.String(32), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("id", sa.String(), nullable=False),
            sa.ForeignKeyConstraint(["journal_entry_id"], ["case_journal_entries.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_case_journal_mentions_entry",
            "case_journal_mentions",
            ["journal_entry_id"],
        )
        op.create_index(
            "ix_case_journal_mentions_ref", "case_journal_mentions", ["mention_ref"]
        )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("case_journal_evidence_links"):
        op.create_table(
            "case_journal_evidence_links",
            sa.Column("journal_entry_id", sa.String(36), nullable=False),
            sa.Column("source_type", sa.String(64), nullable=False),
            sa.Column("source_ref", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("id", sa.String(), nullable=False),
            sa.ForeignKeyConstraint(["journal_entry_id"], ["case_journal_entries.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_case_journal_evidence_entry",
            "case_journal_evidence_links",
            ["journal_entry_id"],
        )
        op.create_index(
            "ix_case_journal_evidence_source",
            "case_journal_evidence_links",
            ["source_type", "source_ref"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("case_journal_evidence_links"):
        op.drop_table("case_journal_evidence_links")
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("case_journal_mentions"):
        op.drop_table("case_journal_mentions")
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("case_journal_entries"):
        op.drop_table("case_journal_entries")
