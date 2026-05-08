"""add_maintenance_performance_indexes

Revision ID: f1e2d3c4b5a6
Revises: fa3b7c9d1e2f
Create Date: 2026-05-07 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f1e2d3c4b5a6"
down_revision: Union[str, Sequence[str], None] = "fa3b7c9d1e2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_flow_templates_device_level_status",
        "flow_templates",
        ["device_type", "maintenance_level", "status"],
        unique=False,
    )
    op.create_index(
        "ix_work_orders_status_id",
        "work_orders",
        ["status", "id"],
        unique=False,
    )
    op.create_index(
        "ix_work_orders_owner_status_id",
        "work_orders",
        ["current_owner_user_id", "status", "id"],
        unique=False,
    )
    op.create_index(
        "ix_work_orders_device_status_id",
        "work_orders",
        ["device_id", "status", "id"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_events_work_order_id_id",
        "work_order_events",
        ["work_order_id", "id"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_messages_work_order_id_id",
        "work_order_messages",
        ["work_order_id", "id"],
        unique=False,
    )
    op.create_index(
        "ix_approval_tasks_work_order_step",
        "approval_tasks",
        ["work_order_id", "step_no"],
        unique=False,
    )
    op.create_index(
        "ix_approval_tasks_work_order_step_status",
        "approval_tasks",
        ["work_order_id", "step_no", "status"],
        unique=False,
    )
    op.create_index(
        "ix_retrieval_snapshots_work_order_created",
        "retrieval_snapshots",
        ["work_order_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_fillings_work_order_submitted",
        "work_order_fillings",
        ["work_order_id", "submitted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_work_order_fillings_work_order_submitted", table_name="work_order_fillings")
    op.drop_index("ix_retrieval_snapshots_work_order_created", table_name="retrieval_snapshots")
    op.drop_index("ix_approval_tasks_work_order_step_status", table_name="approval_tasks")
    op.drop_index("ix_approval_tasks_work_order_step", table_name="approval_tasks")
    op.drop_index("ix_work_order_messages_work_order_id_id", table_name="work_order_messages")
    op.drop_index("ix_work_order_events_work_order_id_id", table_name="work_order_events")
    op.drop_index("ix_work_orders_device_status_id", table_name="work_orders")
    op.drop_index("ix_work_orders_owner_status_id", table_name="work_orders")
    op.drop_index("ix_work_orders_status_id", table_name="work_orders")
    op.drop_index("ix_flow_templates_device_level_status", table_name="flow_templates")
