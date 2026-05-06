"""add_task_execution_timeline

Revision ID: b1c2d3e4f5a6
Revises: a7c3d5e9f0b1
Create Date: 2026-04-23 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "a7c3d5e9f0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("maintenance_tasks") as batch_op:
        batch_op.add_column(sa.Column("execution_timeline", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("maintenance_tasks") as batch_op:
        batch_op.drop_column("execution_timeline")

