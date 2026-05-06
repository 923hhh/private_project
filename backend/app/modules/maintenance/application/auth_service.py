"""Authentication and admin-user operations for maintenance."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.db.models.maintenance import AuthUser, Role, UserRole
from app.modules.maintenance.deps import CurrentUserCtx
from app.modules.maintenance.errors import MaintenanceAPIError
from app.modules.maintenance.security import create_access_token, hash_password, verify_password


class MaintenanceAuthService:
    """Auth, user profile, and admin user management."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def login(self, username: str, password: str) -> dict[str, Any]:
        result = await self.session.execute(
            select(AuthUser).options(selectinload(AuthUser.roles)).where(AuthUser.username == username)
        )
        user = result.scalar_one_or_none()
        if user is None or not verify_password(password, user.password_hash):
            raise MaintenanceAPIError(401, "INVALID_CREDENTIALS", "用户名或密码错误")
        if not user.is_active:
            raise MaintenanceAPIError(401, "INVALID_CREDENTIALS", "用户已禁用")
        roles = [r.code for r in user.roles]
        token = create_access_token(
            secret=self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
            user_id=user.id,
            username=user.username,
            roles=roles,
            expires_minutes=self.settings.access_token_expire_minutes,
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": self.settings.access_token_expire_minutes * 60,
            "user": {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "roles": roles,
            },
        }

    async def get_me(self, ctx: CurrentUserCtx) -> dict[str, Any]:
        result = await self.session.execute(
            select(AuthUser).options(selectinload(AuthUser.roles)).where(AuthUser.id == ctx.user_id)
        )
        user = result.scalar_one()
        return {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "roles": [r.code for r in user.roles],
        }

    async def admin_list_users(self, page: int, page_size: int) -> dict[str, Any]:
        stmt = select(AuthUser).options(selectinload(AuthUser.roles))
        total = (await self.session.execute(select(func.count()).select_from(AuthUser))).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await self.session.execute(stmt)).scalars().all()
        items = [
            {
                "id": u.id,
                "username": u.username,
                "display_name": u.display_name,
                "is_active": u.is_active,
                "roles": [r.code for r in u.roles],
            }
            for u in rows
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def admin_create_user(self, body: dict[str, Any]) -> dict[str, Any]:
        user = AuthUser(
            username=body["username"],
            password_hash=hash_password(body["password"]),
            display_name=body.get("display_name") or body["username"],
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.session.add(user)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            raise MaintenanceAPIError(409, "DUPLICATE_USERNAME", "用户名已存在") from None
        for code in body.get("role_codes", []):
            role = (await self.session.execute(select(Role).where(Role.code == code))).scalar_one_or_none()
            if role:
                self.session.add(UserRole(user_id=user.id, role_id=role.id))
        await self.session.commit()
        return {"id": user.id, "username": user.username}

    async def admin_assign_roles(self, user_id: int, body: dict[str, Any]) -> None:
        await self.session.execute(select(AuthUser).where(AuthUser.id == user_id))
        await self.session.execute(
            UserRole.__table__.delete().where(UserRole.user_id == user_id)
        )
        for code in body.get("role_codes", []):
            role = (await self.session.execute(select(Role).where(Role.code == code))).scalar_one_or_none()
            if role:
                self.session.add(UserRole(user_id=user_id, role_id=role.id))
        await self.session.commit()
