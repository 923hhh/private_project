"""add motorcycle flow template

Revision ID: aa12bb34cc56
Revises: a1b2c3d4e5f6
Create Date: 2026-05-06 23:25:00
"""

from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "aa12bb34cc56"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    exists = bind.execute(
        sa.text(
            """
            SELECT id
            FROM flow_templates
            WHERE device_type = :device_type
              AND maintenance_level = :maintenance_level
              AND status = 'published'
            LIMIT 1
            """
        ),
        {
            "device_type": "摩托车",
            "maintenance_level": "计划定修",
        },
    ).fetchone()
    if exists:
        return

    steps = [
        {
            "step_no": 1,
            "title": "检查拨叉",
            "description": "检查拨叉凸轮从动件、拨叉卡爪是否有弯曲、损坏或裂纹，如有异常则更换拨叉。",
            "requires_approval": False,
        },
        {
            "step_no": 2,
            "title": "检查拨叉轴",
            "description": "将拨叉轴放在平坦表面滚动检查是否弯曲；如弯曲则更换拨叉轴，不要尝试校直。",
            "requires_approval": False,
        },
        {
            "step_no": 3,
            "title": "检查变速鼓",
            "description": "检查变速鼓是否存在磨损、刮痕或卡滞，异常时更换变速鼓。",
            "requires_approval": False,
        },
        {
            "step_no": 4,
            "title": "检查传动主轴与传动副轴齿轮",
            "description": "检查齿轮、挡圈、垫圈是否磨损、缺齿、弯曲或松动，异常时更换对应部件。",
            "requires_approval": False,
        },
        {
            "step_no": 5,
            "title": "检查轴承与换挡顺畅度",
            "description": "检查轴承卡滞或磨损情况，并复核换挡是否顺畅；如不顺畅则重新安装或更换缺陷部件。",
            "requires_approval": False,
        },
    ]

    bind.execute(
        sa.text(
            """
            INSERT INTO flow_templates (
                id, name, device_type, maintenance_level, steps_json, version, status, published_at
            )
            VALUES (
                (SELECT COALESCE(MAX(id), 0) + 1 FROM flow_templates),
                :name,
                :device_type,
                :maintenance_level,
                CAST(:steps_json AS JSON),
                :version,
                :status,
                :published_at
            )
            """
        ),
        {
            "name": "摩托车标准检修",
            "device_type": "摩托车",
            "maintenance_level": "计划定修",
            "steps_json": json.dumps(steps, ensure_ascii=False),
            "version": 1,
            "status": "published",
            "published_at": None,
        },
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM flow_templates
            WHERE device_type = :device_type
              AND maintenance_level = :maintenance_level
              AND name = :name
            """
        ).bindparams(
            device_type="摩托车",
            maintenance_level="计划定修",
            name="摩托车标准检修",
        )
    )
