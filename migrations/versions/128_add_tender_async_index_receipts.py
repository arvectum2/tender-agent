"""Store durable provenance-bound background ingest receipts (opt-in, metadata only).

Revision ID: 128_add_tender_async_index_receipts
Revises: 127_private_review_link_corrections
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "128_add_tender_async_index_receipts"
down_revision: str | Sequence[str] | None = "127_private_review_link_corrections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tender_async_index_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tender_id",
            sa.String(36),
            sa.ForeignKey("procurement_tenders.id"),
            nullable=False,
        ),
        sa.Column("collection_id", sa.String(128), nullable=False),
        sa.Column("chunk_id", sa.String(36), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("expected_chunks", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("document_id", sa.String(128), nullable=True),
        sa.Column("indexed_chunks", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "collection_id", "chunk_id", name="uq_tender_async_receipt_source"
        ),
        sa.UniqueConstraint(
            "collection_id", "job_id", name="uq_tender_async_receipt_job"
        ),
    )
    op.create_index(
        "ix_tender_async_receipt_tender_collection",
        "tender_async_index_receipts",
        ["tender_id", "collection_id"],
    )


def downgrade() -> None:
    # No operator may inadvertently lose resumability or provenance metadata.
    rows = (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM tender_async_index_receipts"))
        .scalar_one()
    )
    if rows:
        raise RuntimeError("refusing populated tender async receipt downgrade")
    op.drop_index(
        "ix_tender_async_receipt_tender_collection",
        table_name="tender_async_index_receipts",
    )
    op.drop_table("tender_async_index_receipts")
