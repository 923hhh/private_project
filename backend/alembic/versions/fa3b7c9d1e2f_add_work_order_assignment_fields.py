"""add work order assignment fields

Revision ID: fa3b7c9d1e2f
Revises: bb23cc45dd67
Create Date: 2026-05-06 21:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "fa3b7c9d1e2f"
down_revision = "bb23cc45dd67"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("work_orders") as batch_op:
        batch_op.add_column(sa.Column("assigned_worker_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("assigned_expert_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("assigned_safety_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("current_owner_user_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_work_orders_assigned_worker_user_id", ["assigned_worker_user_id"], unique=False)
        batch_op.create_index("ix_work_orders_assigned_expert_user_id", ["assigned_expert_user_id"], unique=False)
        batch_op.create_index("ix_work_orders_assigned_safety_user_id", ["assigned_safety_user_id"], unique=False)
        batch_op.create_index("ix_work_orders_current_owner_user_id", ["current_owner_user_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_work_orders_assigned_worker_user_id_users",
            "users",
            ["assigned_worker_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_work_orders_assigned_expert_user_id_users",
            "users",
            ["assigned_expert_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_work_orders_assigned_safety_user_id_users",
            "users",
            ["assigned_safety_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_work_orders_current_owner_user_id_users",
            "users",
            ["current_owner_user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("work_orders") as batch_op:
        batch_op.drop_constraint("fk_work_orders_current_owner_user_id_users", type_="foreignkey")
        batch_op.drop_constraint("fk_work_orders_assigned_safety_user_id_users", type_="foreignkey")
        batch_op.drop_constraint("fk_work_orders_assigned_expert_user_id_users", type_="foreignkey")
        batch_op.drop_constraint("fk_work_orders_assigned_worker_user_id_users", type_="foreignkey")
        batch_op.drop_index("ix_work_orders_current_owner_user_id")
        batch_op.drop_index("ix_work_orders_assigned_safety_user_id")
        batch_op.drop_index("ix_work_orders_assigned_expert_user_id")
        batch_op.drop_index("ix_work_orders_assigned_worker_user_id")
        batch_op.drop_column("current_owner_user_id")
        batch_op.drop_column("assigned_safety_user_id")
        batch_op.drop_column("assigned_expert_user_id")
        batch_op.drop_column("assigned_worker_user_id")
