"""add_work_order_fields_to_task_and_case

Revision ID: f2a6b7c8d9e1
Revises: e4b7c6d4a9f1
Create Date: 2026-03-31 21:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a6b7c8d9e1"
down_revision: Union[str, Sequence[str], None] = "e4b7c6d4a9f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("maintenance_tasks") as batch_op:
        batch_op.add_column(sa.Column("work_order_id", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("asset_code", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("report_source", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column("priority", sa.String(length=30), nullable=False, server_default="medium")
        )
        batch_op.create_index("ix_maintenance_tasks_work_order_id", ["work_order_id"], unique=False)
        batch_op.create_index("ix_maintenance_tasks_asset_code", ["asset_code"], unique=False)
        batch_op.create_index("ix_maintenance_tasks_report_source", ["report_source"], unique=False)
        batch_op.create_index("ix_maintenance_tasks_priority", ["priority"], unique=False)

    with op.batch_alter_table("maintenance_cases") as batch_op:
        batch_op.add_column(sa.Column("work_order_id", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("asset_code", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("report_source", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column("priority", sa.String(length=30), nullable=False, server_default="medium")
        )
        batch_op.create_index("ix_maintenance_cases_work_order_id", ["work_order_id"], unique=False)
        batch_op.create_index("ix_maintenance_cases_asset_code", ["asset_code"], unique=False)
        batch_op.create_index("ix_maintenance_cases_report_source", ["report_source"], unique=False)
        batch_op.create_index("ix_maintenance_cases_priority", ["priority"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("maintenance_cases") as batch_op:
        batch_op.drop_index("ix_maintenance_cases_priority")
        batch_op.drop_index("ix_maintenance_cases_report_source")
        batch_op.drop_index("ix_maintenance_cases_asset_code")
        batch_op.drop_index("ix_maintenance_cases_work_order_id")
        batch_op.drop_column("priority")
        batch_op.drop_column("report_source")
        batch_op.drop_column("asset_code")
        batch_op.drop_column("work_order_id")

    with op.batch_alter_table("maintenance_tasks") as batch_op:
        batch_op.drop_index("ix_maintenance_tasks_priority")
        batch_op.drop_index("ix_maintenance_tasks_report_source")
        batch_op.drop_index("ix_maintenance_tasks_asset_code")
        batch_op.drop_index("ix_maintenance_tasks_work_order_id")
        batch_op.drop_column("priority")
        batch_op.drop_column("report_source")
        batch_op.drop_column("asset_code")
        batch_op.drop_column("work_order_id")
