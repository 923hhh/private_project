"""检修域依赖注入：当前用户与角色校验。"""
from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.db.models.maintenance import AuthUser
from app.db.session import get_session
from app.modules.maintenance.security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUserCtx:
    """已认证用户上下文。"""

    def __init__(self, user_id: int, username: str, roles: list[str]) -> None:
        self.user_id = user_id
        self.username = username
        self.roles = roles

    def has_any(self, *role_codes: str) -> bool:
        return bool(self.roles and set(role_codes) & set(self.roles))


async def get_current_user_ctx(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUserCtx:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=401,
            detail={"success": False, "business_code": "UNAUTHORIZED", "message": "未提供令牌"},
        )
    try:
        payload = decode_token(
            creds.credentials,
            secret=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401,
            detail={"success": False, "business_code": "UNAUTHORIZED", "message": "令牌无效或已过期"},
        ) from None

    uid = int(payload["sub"])
    result = await session.execute(
        select(AuthUser).options(selectinload(AuthUser.roles)).where(AuthUser.id == uid)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail={"success": False, "business_code": "UNAUTHORIZED", "message": "用户不可用"},
        )
    roles = [r.code for r in user.roles]
    return CurrentUserCtx(user_id=user.id, username=user.username, roles=roles)


def require_roles(*allowed: str):
    """要求当前用户至少具备其一角色。"""

    async def _inner(ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)]) -> CurrentUserCtx:
        if not ctx.has_any(*allowed):
            raise HTTPException(
                status_code=403,
                detail={"success": False, "business_code": "FORBIDDEN", "message": "角色权限不足"},
            )
        return ctx

    return _inner
