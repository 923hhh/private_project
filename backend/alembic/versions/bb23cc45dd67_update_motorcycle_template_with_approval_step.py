"""update motorcycle template with approval step

Revision ID: bb23cc45dd67
Revises: aa12bb34cc56
Create Date: 2026-05-06 21:40:00
"""

from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "bb23cc45dd67"
down_revision: Union[str, Sequence[str], None] = "aa12bb34cc56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_STEPS = [
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

NEW_STEPS = [
    {
        "step_no": 1,
        "title": "检查拨叉",
        "description": "检查拨叉凸轮从动件、拨叉卡爪是否有弯曲、损坏或裂纹，如有异常则更换拨叉。",
        "requires_approval": False,
    },
    {
        "step_no": 2,
        "title": "检查拨叉轴并执行定位校正",
        "description": "将拨叉轴放在平坦表面滚动检查是否弯曲；若涉及定位校正或拆装复位，属于高风险变速机构作业，需审批后执行。",
        "requires_approval": True,
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


def _update_steps(steps: list[dict[str, object]]) -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE flow_templates
            SET steps_json = CAST(:steps_json AS JSON)
            WHERE device_type = :device_type
              AND maintenance_level = :maintenance_level
              AND name = :name
            """
        ),
        {
            "steps_json": json.dumps(steps, ensure_ascii=False),
            "device_type": "摩托车",
            "maintenance_level": "计划定修",
            "name": "摩托车标准检修",
        },
    )


def upgrade() -> None:
    _update_steps(NEW_STEPS)


def downgrade() -> None:
    _update_steps(OLD_STEPS)
