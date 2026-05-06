"""add_maintenance_task_workflow_tables

Revision ID: 7e3c4af6d1b2
Revises: 0c7d2d6f4e8a
Create Date: 2026-03-28 23:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7e3c4af6d1b2"
down_revision: Union[str, Sequence[str], None] = "0c7d2d6f4e8a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "maintenance_task_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("equipment_type", sa.String(length=100), nullable=False),
        sa.Column("maintenance_level", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "equipment_type",
            "maintenance_level",
            name="uq_maintenance_task_templates_type_level",
        ),
    )
    op.create_index(
        "ix_maintenance_task_templates_equipment_type",
        "maintenance_task_templates",
        ["equipment_type"],
        unique=False,
    )
    op.create_index(
        "ix_maintenance_task_templates_maintenance_level",
        "maintenance_task_templates",
        ["maintenance_level"],
        unique=False,
    )
    op.create_index(
        "ix_maintenance_task_templates_status",
        "maintenance_task_templates",
        ["status"],
        unique=False,
    )

    op.create_table(
        "maintenance_task_template_steps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("maintenance_task_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("instruction_template", sa.Text(), nullable=False),
        sa.Column("risk_warning", sa.Text(), nullable=True),
        sa.Column("caution", sa.Text(), nullable=True),
        sa.Column("confirmation_text", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_maintenance_task_template_steps_template_id",
        "maintenance_task_template_steps",
        ["template_id"],
        unique=False,
    )

    op.create_table(
        "maintenance_tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("equipment_type", sa.String(length=100), nullable=False),
        sa.Column("equipment_model", sa.String(length=100), nullable=True),
        sa.Column("maintenance_level", sa.String(length=30), nullable=False),
        sa.Column("fault_type", sa.String(length=100), nullable=True),
        sa.Column("symptom_description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("maintenance_task_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_chunk_ids", sa.JSON(), nullable=True),
        sa.Column("source_snapshot", sa.JSON(), nullable=True),
        sa.Column("advice_card", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_maintenance_tasks_equipment_type", "maintenance_tasks", ["equipment_type"], unique=False)
    op.create_index("ix_maintenance_tasks_equipment_model", "maintenance_tasks", ["equipment_model"], unique=False)
    op.create_index("ix_maintenance_tasks_maintenance_level", "maintenance_tasks", ["maintenance_level"], unique=False)
    op.create_index("ix_maintenance_tasks_fault_type", "maintenance_tasks", ["fault_type"], unique=False)
    op.create_index("ix_maintenance_tasks_status", "maintenance_tasks", ["status"], unique=False)

    op.create_table(
        "maintenance_task_steps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "task_id",
            sa.Integer(),
            sa.ForeignKey("maintenance_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "template_step_id",
            sa.Integer(),
            sa.ForeignKey("maintenance_task_template_steps.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("risk_warning", sa.Text(), nullable=True),
        sa.Column("caution", sa.Text(), nullable=True),
        sa.Column("confirmation_text", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("completion_note", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("knowledge_refs", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_maintenance_task_steps_task_id", "maintenance_task_steps", ["task_id"], unique=False)
    op.create_index("ix_maintenance_task_steps_status", "maintenance_task_steps", ["status"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_maintenance_task_steps_status", table_name="maintenance_task_steps")
    op.drop_index("ix_maintenance_task_steps_task_id", table_name="maintenance_task_steps")
    op.drop_table("maintenance_task_steps")

    op.drop_index("ix_maintenance_tasks_status", table_name="maintenance_tasks")
    op.drop_index("ix_maintenance_tasks_fault_type", table_name="maintenance_tasks")
    op.drop_index("ix_maintenance_tasks_maintenance_level", table_name="maintenance_tasks")
    op.drop_index("ix_maintenance_tasks_equipment_model", table_name="maintenance_tasks")
    op.drop_index("ix_maintenance_tasks_equipment_type", table_name="maintenance_tasks")
    op.drop_table("maintenance_tasks")

    op.drop_index("ix_maintenance_task_template_steps_template_id", table_name="maintenance_task_template_steps")
    op.drop_table("maintenance_task_template_steps")

    op.drop_index("ix_maintenance_task_templates_status", table_name="maintenance_task_templates")
    op.drop_index("ix_maintenance_task_templates_maintenance_level", table_name="maintenance_task_templates")
    op.drop_index("ix_maintenance_task_templates_equipment_type", table_name="maintenance_task_templates")
    op.drop_table("maintenance_task_templates")
