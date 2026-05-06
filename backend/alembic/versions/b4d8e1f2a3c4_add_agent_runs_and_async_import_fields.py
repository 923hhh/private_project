"""add_agent_runs_and_async_import_fields

Revision ID: b4d8e1f2a3c4
Revises: a7c3d5e9f0b1
Create Date: 2026-03-31 23:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4d8e1f2a3c4"
down_revision: Union[str, Sequence[str], None] = "a7c3d5e9f0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_agent_runs_run_id", "agent_runs", ["run_id"], unique=True)
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"], unique=False)

    with op.batch_alter_table("knowledge_import_jobs") as batch_op:
        batch_op.add_column(sa.Column("content_type", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("file_bytes", sa.LargeBinary(), nullable=True))
        batch_op.add_column(
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("started_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("finished_at", sa.DateTime(), nullable=True))
        batch_op.alter_column(
            "status",
            existing_type=sa.String(length=30),
            server_default="pending",
            existing_nullable=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("knowledge_import_jobs") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.String(length=30),
            server_default="processing",
            existing_nullable=False,
        )
        batch_op.drop_column("finished_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("attempt_count")
        batch_op.drop_column("file_bytes")
        batch_op.drop_column("content_type")

    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_run_id", table_name="agent_runs")
    op.drop_table("agent_runs")
