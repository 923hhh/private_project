"""add_postgres_search_and_workflow_indexes

Revision ID: c9e4f7a1b2d3
Revises: b4d8e1f2a3c4
Create Date: 2026-04-01 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "c9e4f7a1b2d3"
down_revision: Union[str, Sequence[str], None] = "b4d8e1f2a3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_knowledge_documents_status_updated",
        "knowledge_documents",
        ["status", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_documents_source_type_updated",
        "knowledge_documents",
        ["source_type", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_documents_equipment_filters",
        "knowledge_documents",
        ["equipment_type", "equipment_model", "fault_type", "id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_chunks_document_chunk_order",
        "knowledge_chunks",
        ["document_id", "chunk_index"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_chunks_equipment_filters",
        "knowledge_chunks",
        ["equipment_type", "equipment_model", "fault_type", "id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_import_jobs_status_updated",
        "knowledge_import_jobs",
        ["status", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_maintenance_task_template_steps_template_order",
        "maintenance_task_template_steps",
        ["template_id", "step_order"],
        unique=False,
    )
    op.create_index(
        "ix_maintenance_task_steps_task_order",
        "maintenance_task_steps",
        ["task_id", "step_order"],
        unique=False,
    )
    op.create_index(
        "ix_maintenance_tasks_status_priority_updated",
        "maintenance_tasks",
        ["status", "priority", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_maintenance_cases_status_priority_updated",
        "maintenance_cases",
        ["status", "priority", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_maintenance_cases_status_equipment_updated",
        "maintenance_cases",
        ["status", "equipment_type", "updated_at"],
        unique=False,
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_knowledge_documents_search_tsv
            ON knowledge_documents
            USING gin (
              to_tsvector(
                'simple',
                coalesce(title, '') || ' ' ||
                coalesce(source_name, '') || ' ' ||
                coalesce(equipment_model, '') || ' ' ||
                coalesce(fault_type, '')
              )
            )
            """
        )
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


def downgrade() -> None:
    """Downgrade schema."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_search_tsv")
        op.execute("DROP INDEX IF EXISTS ix_knowledge_documents_search_tsv")

    op.drop_index("ix_maintenance_cases_status_equipment_updated", table_name="maintenance_cases")
    op.drop_index("ix_maintenance_cases_status_priority_updated", table_name="maintenance_cases")
    op.drop_index("ix_maintenance_tasks_status_priority_updated", table_name="maintenance_tasks")
    op.drop_index("ix_maintenance_task_steps_task_order", table_name="maintenance_task_steps")
    op.drop_index(
        "ix_maintenance_task_template_steps_template_order",
        table_name="maintenance_task_template_steps",
    )
    op.drop_index("ix_knowledge_import_jobs_status_updated", table_name="knowledge_import_jobs")
    op.drop_index("ix_knowledge_chunks_equipment_filters", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_document_chunk_order", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_documents_equipment_filters", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_source_type_updated", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_status_updated", table_name="knowledge_documents")
