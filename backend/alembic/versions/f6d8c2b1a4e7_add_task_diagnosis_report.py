"""add task diagnosis report

Revision ID: f6d8c2b1a4e7
Revises: b1c2d3e4f5a6, e8f1a2b3c4d5
Create Date: 2026-05-03 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6d8c2b1a4e7"
down_revision: Union[str, Sequence[str], None] = ("b1c2d3e4f5a6", "e8f1a2b3c4d5")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("maintenance_tasks", sa.Column("diagnosis_report", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("maintenance_tasks", "diagnosis_report")
