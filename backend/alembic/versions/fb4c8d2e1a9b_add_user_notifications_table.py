"""add user notifications table

Revision ID: fb4c8d2e1a9b
Revises: fa3b7c9d1e2f
Create Date: 2026-05-07 11:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "fb4c8d2e1a9b"
down_revision = "fa3b7c9d1e2f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("source_key", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("link_url", sa.String(length=255), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "source_key", name="uq_user_notifications_user_source_key"),
    )
    op.create_index("ix_user_notifications_user_id", "user_notifications", ["user_id"], unique=False)
    op.create_index("ix_user_notifications_kind", "user_notifications", ["kind"], unique=False)
    op.create_index("ix_user_notifications_is_read", "user_notifications", ["is_read"], unique=False)
    op.create_index("ix_user_notifications_updated_at", "user_notifications", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_notifications_updated_at", table_name="user_notifications")
    op.drop_index("ix_user_notifications_is_read", table_name="user_notifications")
    op.drop_index("ix_user_notifications_kind", table_name="user_notifications")
    op.drop_index("ix_user_notifications_user_id", table_name="user_notifications")
    op.drop_table("user_notifications")
