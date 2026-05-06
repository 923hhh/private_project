"""add_knowledge_import_jobs_table

Revision ID: e4b7c6d4a9f1
Revises: c1f4e2ab9d73
Create Date: 2026-03-30 21:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4b7c6d4a9f1"
down_revision: Union[str, Sequence[str], None] = "c1f4e2ab9d73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "knowledge_import_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("import_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("equipment_type", sa.String(length=100), nullable=False),
        sa.Column("equipment_model", sa.String(length=100), nullable=True),
        sa.Column("fault_type", sa.String(length=100), nullable=True),
        sa.Column("section_reference", sa.String(length=100), nullable=True),
        sa.Column("replace_existing", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("preview_excerpt", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_knowledge_import_jobs_import_type",
        "knowledge_import_jobs",
        ["import_type"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_import_jobs_source_name",
        "knowledge_import_jobs",
        ["source_name"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_import_jobs_source_type",
        "knowledge_import_jobs",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_import_jobs_equipment_type",
        "knowledge_import_jobs",
        ["equipment_type"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_import_jobs_equipment_model",
        "knowledge_import_jobs",
        ["equipment_model"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_import_jobs_fault_type",
        "knowledge_import_jobs",
        ["fault_type"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_import_jobs_status",
        "knowledge_import_jobs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_import_jobs_document_id",
        "knowledge_import_jobs",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_knowledge_import_jobs_document_id", table_name="knowledge_import_jobs")
    op.drop_index("ix_knowledge_import_jobs_status", table_name="knowledge_import_jobs")
    op.drop_index("ix_knowledge_import_jobs_fault_type", table_name="knowledge_import_jobs")
    op.drop_index("ix_knowledge_import_jobs_equipment_model", table_name="knowledge_import_jobs")
    op.drop_index("ix_knowledge_import_jobs_equipment_type", table_name="knowledge_import_jobs")
    op.drop_index("ix_knowledge_import_jobs_source_type", table_name="knowledge_import_jobs")
    op.drop_index("ix_knowledge_import_jobs_source_name", table_name="knowledge_import_jobs")
    op.drop_index("ix_knowledge_import_jobs_import_type", table_name="knowledge_import_jobs")
    op.drop_table("knowledge_import_jobs")
