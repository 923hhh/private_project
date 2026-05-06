"""add_structured_step_fields

Revision ID: a7c3d5e9f0b1
Revises: f2a6b7c8d9e1
Create Date: 2026-03-31 22:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c3d5e9f0b1"
down_revision: Union[str, Sequence[str], None] = "f2a6b7c8d9e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("maintenance_task_template_steps") as batch_op:
        batch_op.add_column(sa.Column("required_tools", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("required_materials", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("estimated_minutes", sa.Integer(), nullable=True))

    with op.batch_alter_table("maintenance_task_steps") as batch_op:
        batch_op.add_column(sa.Column("required_tools", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("required_materials", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("estimated_minutes", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("maintenance_task_steps") as batch_op:
        batch_op.drop_column("estimated_minutes")
        batch_op.drop_column("required_materials")
        batch_op.drop_column("required_tools")

    with op.batch_alter_table("maintenance_task_template_steps") as batch_op:
        batch_op.drop_column("estimated_minutes")
        batch_op.drop_column("required_materials")
        batch_op.drop_column("required_tools")
