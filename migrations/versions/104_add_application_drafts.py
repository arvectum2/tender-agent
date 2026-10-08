"""add review-only application draft provenance

Revision ID: 104_add_application_drafts
Revises: 103_add_case_collaboration
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "104_add_application_drafts"
down_revision: str | Sequence[str] | None = "103_add_case_collaboration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("application_draft_generations"):
        op.create_table(
            "application_draft_generations",
            sa.Column("deal_id", sa.String(32), nullable=False),
            sa.Column("template_artifact_ref", sa.String(64), nullable=False),
            sa.Column("output_artifact_ref", sa.String(64), nullable=False),
            sa.Column("document_role", sa.String(32), nullable=False),
            sa.Column("output_format", sa.String(16), nullable=False),
            sa.Column("lineage_key", sa.String(192), nullable=False),
            sa.Column("template_version_no", sa.Integer(), nullable=False),
            sa.Column("generation_version_no", sa.Integer(), nullable=False),
            sa.Column("template_sha256", sa.String(64), nullable=False),
            sa.Column("output_sha256", sa.String(64), nullable=False),
            sa.Column("output_file_name", sa.Text(), nullable=False),
            sa.Column("output_storage_uri", sa.Text(), nullable=False),
            sa.Column("review_state", sa.String(32), nullable=False),
            sa.Column("signature_performed", sa.Boolean(), nullable=False),
            sa.Column("submission_performed", sa.Boolean(), nullable=False),
            sa.Column("external_delivery_performed", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("id", sa.String(), nullable=False),
            sa.ForeignKeyConstraint(["deal_id"], ["deals.deal_id"]),
            sa.ForeignKeyConstraint(
                ["output_artifact_ref"], ["document_artifacts.artifact_ref"]
            ),
            sa.ForeignKeyConstraint(
                ["template_artifact_ref"], ["document_artifacts.artifact_ref"]
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "deal_id",
                "lineage_key",
                "generation_version_no",
                name="uq_application_draft_lineage_version",
            ),
        )
        op.create_index(
            "ix_application_draft_deal_role",
            "application_draft_generations",
            ["deal_id", "document_role"],
        )
        op.create_index(
            "ix_application_draft_output_artifact",
            "application_draft_generations",
            ["output_artifact_ref"],
        )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("application_draft_field_provenance"):
        op.create_table(
            "application_draft_field_provenance",
            sa.Column("generation_id", sa.String(36), nullable=False),
            sa.Column("source_type", sa.String(64), nullable=False),
            sa.Column("source_ref", sa.Text(), nullable=False),
            sa.Column("target_locator", sa.Text(), nullable=False),
            sa.Column("original_value_json", sa.JSON(), nullable=True),
            sa.Column("generated_value_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("id", sa.String(), nullable=False),
            sa.ForeignKeyConstraint(
                ["generation_id"], ["application_draft_generations.id"]
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "generation_id",
                "target_locator",
                name="uq_application_draft_generation_target",
            ),
        )
        op.create_index(
            "ix_application_draft_field_generation",
            "application_draft_field_provenance",
            ["generation_id"],
        )
        op.create_index(
            "ix_application_draft_field_source",
            "application_draft_field_provenance",
            ["source_type"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("application_draft_field_provenance"):
        op.drop_table("application_draft_field_provenance")
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("application_draft_generations"):
        op.drop_table("application_draft_generations")
