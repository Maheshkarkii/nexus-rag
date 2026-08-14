"""Add extracted_text, statistics, and processing metadata to documents table.

Revision ID: 0003_add_document_extracted_content
Revises: 0002_create_documents_table
Create Date: 2026-08-08 20:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003_add_document_extracted_content"
down_revision: Union[str, None] = "0002_create_documents_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("extracted_text", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("extracted_character_count", sa.BigInteger(), nullable=True))
    op.add_column("documents", sa.Column("extracted_word_count", sa.BigInteger(), nullable=True))
    op.add_column("documents", sa.Column("extracted_metadata", sa.JSON(), nullable=True))
    op.add_column("documents", sa.Column("processing_error", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "processed_at")
    op.drop_column("documents", "processing_error")
    op.drop_column("documents", "extracted_metadata")
    op.drop_column("documents", "extracted_word_count")
    op.drop_column("documents", "extracted_character_count")
    op.drop_column("documents", "extracted_text")
