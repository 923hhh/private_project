"""add_knowledge_base_tables

Revision ID: 0c7d2d6f4e8a
Revises: 388d25b1856f
Create Date: 2026-03-28 23:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0c7d2d6f4e8a"
down_revision: Union[str, Sequence[str], None] = "388d25b1856f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "device_models",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("equipment_type", sa.String(length=100), nullable=False),
        sa.Column("model_code", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("manufacturer", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("equipment_type", "model_code", name="uq_device_models_type_code"),
    )
    op.create_index("ix_device_models_equipment_type", "device_models", ["equipment_type"], unique=False)
    op.create_index("ix_device_models_model_code", "device_models", ["model_code"], unique=False)

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("equipment_type", sa.String(length=100), nullable=False),
        sa.Column("equipment_model", sa.String(length=100), nullable=True),
        sa.Column("fault_type", sa.String(length=100), nullable=True),
        sa.Column("section_reference", sa.String(length=100), nullable=True),
        sa.Column("page_reference", sa.String(length=50), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_knowledge_documents_source_type", "knowledge_documents", ["source_type"], unique=False)
    op.create_index("ix_knowledge_documents_equipment_type", "knowledge_documents", ["equipment_type"], unique=False)
    op.create_index("ix_knowledge_documents_equipment_model", "knowledge_documents", ["equipment_model"], unique=False)
    op.create_index("ix_knowledge_documents_fault_type", "knowledge_documents", ["fault_type"], unique=False)
    op.create_index("ix_knowledge_documents_status", "knowledge_documents", ["status"], unique=False)

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("equipment_type", sa.String(length=100), nullable=False),
        sa.Column("equipment_model", sa.String(length=100), nullable=True),
        sa.Column("fault_type", sa.String(length=100), nullable=True),
        sa.Column("section_reference", sa.String(length=100), nullable=True),
        sa.Column("page_reference", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"], unique=False)
    op.create_index("ix_knowledge_chunks_equipment_type", "knowledge_chunks", ["equipment_type"], unique=False)
    op.create_index("ix_knowledge_chunks_equipment_model", "knowledge_chunks", ["equipment_model"], unique=False)
    op.create_index("ix_knowledge_chunks_fault_type", "knowledge_chunks", ["fault_type"], unique=False)

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE INDEX ix_knowledge_chunks_search_vector
            ON knowledge_chunks
            USING gin (
              to_tsvector(
                'simple',
                coalesce(content, '') || ' ' ||
                coalesce(equipment_model, '') || ' ' ||
                coalesce(fault_type, '')
              )
            )
            """
        )

    op.create_table(
        "maintenance_cases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("equipment_type", sa.String(length=100), nullable=False),
        sa.Column("equipment_model", sa.String(length=100), nullable=True),
        sa.Column("fault_type", sa.String(length=100), nullable=True),
        sa.Column("symptom_description", sa.Text(), nullable=False),
        sa.Column("resolution_summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "source_document_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_maintenance_cases_equipment_type", "maintenance_cases", ["equipment_type"], unique=False)
    op.create_index("ix_maintenance_cases_equipment_model", "maintenance_cases", ["equipment_model"], unique=False)
    op.create_index("ix_maintenance_cases_fault_type", "maintenance_cases", ["fault_type"], unique=False)
    op.create_index("ix_maintenance_cases_status", "maintenance_cases", ["status"], unique=False)

    op.create_table(
        "knowledge_relations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("source_kind", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("target_kind", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("relation_type", sa.String(length=50), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_knowledge_relations_source_kind", "knowledge_relations", ["source_kind"], unique=False)
    op.create_index("ix_knowledge_relations_source_id", "knowledge_relations", ["source_id"], unique=False)
    op.create_index("ix_knowledge_relations_target_kind", "knowledge_relations", ["target_kind"], unique=False)
    op.create_index("ix_knowledge_relations_target_id", "knowledge_relations", ["target_id"], unique=False)
    op.create_index("ix_knowledge_relations_relation_type", "knowledge_relations", ["relation_type"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_search_vector")

    op.drop_index("ix_knowledge_relations_relation_type", table_name="knowledge_relations")
    op.drop_index("ix_knowledge_relations_target_id", table_name="knowledge_relations")
    op.drop_index("ix_knowledge_relations_target_kind", table_name="knowledge_relations")
    op.drop_index("ix_knowledge_relations_source_id", table_name="knowledge_relations")
    op.drop_index("ix_knowledge_relations_source_kind", table_name="knowledge_relations")
    op.drop_table("knowledge_relations")

    op.drop_index("ix_maintenance_cases_status", table_name="maintenance_cases")
    op.drop_index("ix_maintenance_cases_fault_type", table_name="maintenance_cases")
    op.drop_index("ix_maintenance_cases_equipment_model", table_name="maintenance_cases")
    op.drop_index("ix_maintenance_cases_equipment_type", table_name="maintenance_cases")
    op.drop_table("maintenance_cases")

    op.drop_index("ix_knowledge_chunks_fault_type", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_equipment_model", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_equipment_type", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_document_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")

    op.drop_index("ix_knowledge_documents_status", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_fault_type", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_equipment_model", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_equipment_type", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_source_type", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")

    op.drop_index("ix_device_models_model_code", table_name="device_models")
    op.drop_index("ix_device_models_equipment_type", table_name="device_models")
    op.drop_table("device_models")
