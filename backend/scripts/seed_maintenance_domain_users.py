#!/usr/bin/env python3
"""向检修域 表写入演示账号（依赖已执行 Alembic 迁移）。

用法：
    python scripts/seed_maintenance_domain_users.py

默认密码均为 ``ChangeMe123!``，生产环境禁用本脚本或修改密码。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.models.maintenance import AuthUser, Role, UserRole
from app.db.session import get_session_context
from app.modules.maintenance.security import hash_password


async def main() -> None:
    pwd = hash_password("ChangeMe123!")
    async with get_session_context() as session:
        # 全量清库后 roles 可能为空，这里先补齐默认角色，再进行用户绑定
        existing_roles = (await session.execute(select(Role))).scalars().all()
        role_by_code = {r.code: r for r in existing_roles}
        default_roles = {
            "worker": "维修人员",
            "expert": "技术专家",
            "safety": "安全监督",
            "admin": "系统管理员",
        }
        for code, name in default_roles.items():
            if code in role_by_code:
                continue
            r = Role(code=code, name=name)
            session.add(r)
            await session.flush()
            role_by_code[code] = r

        roles = (await session.execute(select(Role))).scalars().all()
        role_by_code = {r.code: r for r in roles}

        async def ensure_user(username: str, display: str, codes: list[str]) -> AuthUser:
            row = (await session.execute(select(AuthUser).where(AuthUser.username == username))).scalar_one_or_none()
            if row:
                return row
            u = AuthUser(
                username=username,
                password_hash=pwd,
                display_name=display,
                is_active=True,
            )
            session.add(u)
            await session.flush()
            for c in codes:
                rid = role_by_code[c].id
                session.add(UserRole(user_id=u.id, role_id=rid))
            return u

        await ensure_user("maintenance_worker", "演示一线", ["worker"])
        await ensure_user("maintenance_expert", "演示专家", ["expert"])
        await ensure_user("maintenance_safety", "演示安全", ["safety"])
        await ensure_user("maintenance_admin", "演示管理员", ["admin"])

        await session.commit()
        print("演示用户已就绪：maintenance_worker / maintenance_expert / maintenance_safety / maintenance_admin，密码 ChangeMe123!")


if __name__ == "__main__":
    asyncio.run(main())
