"""add_case_review_and_feedback_tables

Revision ID: c1f4e2ab9d73
Revises: 7e3c4af6d1b2
Create Date: 2026-03-28 20:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1f4e2ab9d73"
down_revision: Union[str, Sequence[str], None] = "7e3c4af6d1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("maintenance_cases") as batch_op:
        batch_op.add_column(sa.Column("task_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("processing_steps", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("attachment_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("attachment_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("knowledge_refs", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("reviewer_name", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("review_note", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("reviewed_at", sa.DateTime(), nullable=True))
        batch_op.create_foreign_key(
            "fk_maintenance_cases_task_id",
            "maintenance_tasks",
            ["task_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_maintenance_cases_task_id", ["task_id"], unique=False)

    op.create_table(
        "maintenance_case_corrections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "case_id",
            sa.Integer(),
            sa.ForeignKey("maintenance_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("correction_target", sa.String(length=30), nullable=False),
        sa.Column("original_content", sa.Text(), nullable=True),
        sa.Column("corrected_content", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_maintenance_case_corrections_case_id",
        "maintenance_case_corrections",
        ["case_id"],
        unique=False,
    )
    op.create_index(
        "ix_maintenance_case_corrections_correction_target",
        "maintenance_case_corrections",
        ["correction_target"],
        unique=False,
    )
    op.create_index(
        "ix_maintenance_case_corrections_status",
        "maintenance_case_corrections",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_maintenance_case_corrections_status",
        table_name="maintenance_case_corrections",
    )
    op.drop_index(
        "ix_maintenance_case_corrections_correction_target",
        table_name="maintenance_case_corrections",
    )
    op.drop_index(
        "ix_maintenance_case_corrections_case_id",
        table_name="maintenance_case_corrections",
    )
    op.drop_table("maintenance_case_corrections")

    with op.batch_alter_table("maintenance_cases") as batch_op:
        batch_op.drop_index("ix_maintenance_cases_task_id")
        batch_op.drop_constraint("fk_maintenance_cases_task_id", type_="foreignkey")
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("review_note")
        batch_op.drop_column("reviewer_name")
        batch_op.drop_column("knowledge_refs")
        batch_op.drop_column("attachment_url")
        batch_op.drop_column("attachment_name")
        batch_op.drop_column("processing_steps")
        batch_op.drop_column("task_id")
