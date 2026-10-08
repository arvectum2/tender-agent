"""add tenant-isolated reusable company profile store

Revision ID: 105_add_company_profile_store
Revises: 104_add_application_drafts
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "105_add_company_profile_store"
down_revision: str | Sequence[str] | None = "104_add_application_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("company_profile_fact_versions"):
        op.create_table(
            "company_profile_fact_versions",
            sa.Column("customer_id", sa.String(64), nullable=False),
            sa.Column("fact_key", sa.String(128), nullable=False),
            sa.Column("fact_group", sa.String(32), nullable=False),
            sa.Column("version_no", sa.Integer(), nullable=False),
            sa.Column("value_json", sa.JSON(), nullable=True),
            sa.Column("source_type", sa.String(64), nullable=False),
            sa.Column("source_ref", sa.Text(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("id", sa.String(), nullable=False),
            sa.ForeignKeyConstraint(["customer_id"], ["customer_profiles.customer_id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "customer_id",
                "fact_key",
                "version_no",
                name="uq_company_profile_fact_version",
            ),
        )
        op.create_index(
            "ix_company_profile_fact_customer_key",
            "company_profile_fact_versions",
            ["customer_id", "fact_key"],
        )
        op.create_index(
            "ix_company_profile_fact_expiry",
            "company_profile_fact_versions",
            ["customer_id", "expires_at"],
        )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("company_documents"):
        op.create_table(
            "company_documents",
            sa.Column("customer_id", sa.String(64), nullable=False),
            sa.Column("document_key", sa.String(128), nullable=False),
            sa.Column("document_type", sa.String(32), nullable=False),
            sa.Column("display_name", sa.Text(), nullable=False),
            sa.Column("artifact_ref", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("id", sa.String(), nullable=False),
            sa.ForeignKeyConstraint(
                ["artifact_ref"], ["document_artifacts.artifact_ref"]
            ),
            sa.ForeignKeyConstraint(["customer_id"], ["customer_profiles.customer_id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("artifact_ref"),
            sa.UniqueConstraint(
                "customer_id",
                "document_key",
                name="uq_company_document_customer_key",
            ),
        )
        op.create_index(
            "ix_company_document_customer_type",
            "company_documents",
            ["customer_id", "document_type"],
        )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("company_document_versions"):
        op.create_table(
            "company_document_versions",
            sa.Column("company_document_id", sa.String(36), nullable=False),
            sa.Column("version_no", sa.Integer(), nullable=False),
            sa.Column("artifact_version_no", sa.Integer(), nullable=False),
            sa.Column("document_number", sa.Text(), nullable=True),
            sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("source_type", sa.String(64), nullable=False),
            sa.Column("source_ref", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("id", sa.String(), nullable=False),
            sa.ForeignKeyConstraint(["company_document_id"], ["company_documents.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "company_document_id",
                "version_no",
                name="uq_company_document_version",
            ),
            sa.UniqueConstraint(
                "company_document_id",
                "artifact_version_no",
                name="uq_company_document_artifact_version",
            ),
        )
        op.create_index(
            "ix_company_document_version_document",
            "company_document_versions",
            ["company_document_id", "version_no"],
        )
        op.create_index(
            "ix_company_document_version_expiry",
            "company_document_versions",
            ["expires_at"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("company_document_versions"):
        op.drop_table("company_document_versions")
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("company_documents"):
        op.drop_table("company_documents")
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("company_profile_fact_versions"):
        op.drop_table("company_profile_fact_versions")
