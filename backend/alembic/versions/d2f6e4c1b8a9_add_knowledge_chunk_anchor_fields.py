"""add_knowledge_chunk_anchor_fields

Revision ID: d2f6e4c1b8a9
Revises: c9e4f7a1b2d3
Create Date: 2026-04-01 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2f6e4c1b8a9"
down_revision: Union[str, Sequence[str], None] = "c9e4f7a1b2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("knowledge_chunks", sa.Column("section_path", sa.String(length=255), nullable=True))
    op.add_column("knowledge_chunks", sa.Column("step_anchor", sa.String(length=255), nullable=True))
    op.add_column("knowledge_chunks", sa.Column("image_anchor", sa.String(length=100), nullable=True))

    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_search_tsv")
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_search_tsv
            ON knowledge_chunks
            USING gin (
              to_tsvector(
                'simple',
                coalesce(heading, '') || ' ' ||
                coalesce(content, '') || ' ' ||
                coalesce(equipment_model, '') || ' ' ||
                coalesce(fault_type, '') || ' ' ||
                coalesce(section_reference, '') || ' ' ||
                coalesce(section_path, '') || ' ' ||
                coalesce(step_anchor, '') || ' ' ||
                coalesce(page_reference, '') || ' ' ||
                coalesce(image_anchor, '')
              )
            )
            """
        )


def downgrade() -> None:
    """Downgrade schema."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_search_tsv")
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_search_tsv
            ON knowledge_chunks
            USING gin (
              to_tsvector(
                'simple',
                coalesce(heading, '') || ' ' ||
                coalesce(content, '') || ' ' ||
                coalesce(equipment_model, '') || ' ' ||
                coalesce(fault_type, '') || ' ' ||
                coalesce(section_reference, '') || ' ' ||
                coalesce(page_reference, '')
              )
            )
            """
        )

    op.drop_column("knowledge_chunks", "image_anchor")
    op.drop_column("knowledge_chunks", "step_anchor")
    op.drop_column("knowledge_chunks", "section_path")
