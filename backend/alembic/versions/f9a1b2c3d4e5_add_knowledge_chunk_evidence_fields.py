"""add knowledge chunk evidence fields

Revision ID: f9a1b2c3d4e5
Revises: f6d8c2b1a4e7
Create Date: 2026-05-04 15:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f9a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "f6d8c2b1a4e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_chunks", sa.Column("source_modality", sa.String(length=30), nullable=True))
    op.add_column("knowledge_chunks", sa.Column("ocr_text", sa.Text(), nullable=True))
    op.add_column("knowledge_chunks", sa.Column("image_caption", sa.Text(), nullable=True))
    op.add_column("knowledge_chunks", sa.Column("evidence_summary", sa.Text(), nullable=True))
    op.create_index(
        "ix_knowledge_chunks_source_modality",
        "knowledge_chunks",
        ["source_modality"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_source_modality", table_name="knowledge_chunks")
    op.drop_column("knowledge_chunks", "evidence_summary")
    op.drop_column("knowledge_chunks", "image_caption")
    op.drop_column("knowledge_chunks", "ocr_text")
    op.drop_column("knowledge_chunks", "source_modality")
