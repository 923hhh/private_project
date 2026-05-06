#!/usr/bin/env python3
"""向检修域表写入本地自定义账号（依赖已执行 Alembic 迁移）。

用法：
    set MAINTENANCE_INIT_USERS_JSON=[{"username":"admin_local","password":"<password>","roles":["admin"]}]
    python scripts/seed_maintenance_domain_users.py
"""
from __future__ import annotations

import asyncio
import json
import os
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
    raw_users = (os.getenv("MAINTENANCE_INIT_USERS_JSON") or "").strip()
    if not raw_users:
        raise SystemExit(
            "缺少 MAINTENANCE_INIT_USERS_JSON。请通过环境变量提供本地初始化账号信息。"
        )
    try:
        user_specs = json.loads(raw_users)
    except json.JSONDecodeError as exc:
        raise SystemExit("MAINTENANCE_INIT_USERS_JSON 必须是合法 JSON。") from exc
    if not isinstance(user_specs, list) or not user_specs:
        raise SystemExit("MAINTENANCE_INIT_USERS_JSON 必须是非空 JSON 数组。")

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

        async def ensure_user(
            username: str,
            display: str,
            password: str,
            codes: list[str],
        ) -> AuthUser:
            row = (await session.execute(select(AuthUser).where(AuthUser.username == username))).scalar_one_or_none()
            if row:
                return row
            u = AuthUser(
                username=username,
                password_hash=hash_password(password),
                display_name=display,
                is_active=True,
            )
            session.add(u)
            await session.flush()
            for c in codes:
                rid = role_by_code[c].id
                session.add(UserRole(user_id=u.id, role_id=rid))
            return u

        created_usernames: list[str] = []
        for item in user_specs:
            if not isinstance(item, dict):
                raise SystemExit("账号配置中的每一项都必须是对象。")
            username = str(item.get("username") or "").strip()
            password = str(item.get("password") or "").strip()
            display_name = str(item.get("display_name") or username).strip()
            role_codes = item.get("roles") or []
            if not username or not password:
                raise SystemExit("每个账号都必须提供 username 和 password。")
            if not isinstance(role_codes, list) or not role_codes:
                raise SystemExit(f"账号 {username} 必须提供非空 roles 数组。")
            unknown_roles = [code for code in role_codes if code not in role_by_code]
            if unknown_roles:
                raise SystemExit(f"账号 {username} 包含未知角色：{', '.join(unknown_roles)}")
            await ensure_user(username, display_name, password, [str(code) for code in role_codes])
            created_usernames.append(username)

        await session.commit()
        print("本地初始化账号已就绪：" + " / ".join(created_usernames))


if __name__ == "__main__":
    asyncio.run(main())
