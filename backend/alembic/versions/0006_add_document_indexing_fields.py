"""Add document indexing fields.

Revision ID: 0006_add_document_indexing_fields
Revises: 0005_create_chunk_embeddings_table
Create Date: 2026-08-09 21:37:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_add_document_indexing_fields"
down_revision: str | None = "0005_create_chunk_embeddings_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("indexing_status", sa.String(length=32), nullable=True, server_default="pending"))
    op.add_column("documents", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("indexing_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "indexing_error")
    op.drop_column("documents", "indexed_at")
    op.drop_column("documents", "indexing_status")
