"""Attachment storage and download authorization for maintenance."""
from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.maintenance import Attachment, WorkOrder
from app.modules.maintenance.datetime_util import utc_now_naive
from app.modules.maintenance.deps import CurrentUserCtx
from app.modules.maintenance.errors import MaintenanceAPIError

ATTACHMENT_UPLOAD_MAX_BYTES = 10 * 1024 * 1024


def _can_read_wo(ctx: CurrentUserCtx, work_order: WorkOrder) -> bool:
    if ctx.has_any("admin", "expert", "safety"):
        return True
    return work_order.created_by_user_id == ctx.user_id


class MaintenanceAttachmentService:
    """Attachment upload, signing, and download path resolution."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def upload_dir(self) -> Path:
        upload_dir = Path(self.settings.maintenance_upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        return upload_dir

    def sign_attachment_token(self, attachment_id: int, exp: int) -> str:
        msg = f"{attachment_id}:{exp}"
        sig = hmac.new(
            self.settings.attachment_sign_secret.encode(),
            msg.encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"{msg}:{sig}"

    def verify_attachment_token(self, token: str) -> tuple[int, int]:
        parts = token.split(":")
        if len(parts) != 3:
            raise MaintenanceAPIError(403, "FORBIDDEN", "签名无效")
        aid_s, exp_s, sig = parts
        aid, exp = int(aid_s), int(exp_s)
        expect = self.sign_attachment_token(aid, exp)
        if not hmac.compare_digest(token, expect):
            raise MaintenanceAPIError(403, "FORBIDDEN", "签名无效")
        if int(datetime.now(timezone.utc).timestamp()) > exp:
            raise MaintenanceAPIError(403, "FORBIDDEN", "链接已过期")
        return aid, exp

    async def save_attachment(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        mime: str,
        biz_type: str,
        work_order_id: int | None,
        ctx: CurrentUserCtx,
    ) -> dict[str, object]:
        if len(file_bytes) > ATTACHMENT_UPLOAD_MAX_BYTES:
            raise MaintenanceAPIError(413, "PAYLOAD_TOO_LARGE", "单文件超过 10MB 限制", data=None)
        uid = uuid.uuid4().hex
        key = f"{ctx.user_id}/{uid}_{filename}"
        path = self.upload_dir() / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(file_bytes)
        attachment = Attachment(
            work_order_id=work_order_id,
            biz_type=biz_type,
            storage_key=key,
            mime_type=mime,
            size_bytes=len(file_bytes),
            uploaded_by_user_id=ctx.user_id,
            created_at=utc_now_naive(),
        )
        self.session.add(attachment)
        await self.session.commit()
        await self.session.refresh(attachment)
        return {
            "id": attachment.id,
            "work_order_id": attachment.work_order_id,
            "biz_type": attachment.biz_type,
            "mime_type": attachment.mime_type,
            "size_bytes": attachment.size_bytes,
            "created_at": attachment.created_at.isoformat(),
        }

    async def get_attachment_for_download(self, attachment_id: int, ctx: CurrentUserCtx) -> Attachment:
        attachment = await self.session.get(Attachment, attachment_id)
        if attachment is None:
            raise MaintenanceAPIError(404, "NOT_FOUND", "附件不存在")
        if attachment.uploaded_by_user_id != ctx.user_id and not ctx.has_any("admin", "expert", "safety"):
            if attachment.work_order_id:
                work_order = await self.session.get(WorkOrder, attachment.work_order_id)
                if work_order and not _can_read_wo(ctx, work_order):
                    raise MaintenanceAPIError(403, "FORBIDDEN", "无权下载该附件")
        return attachment

    async def attachment_file_path(self, attachment_id: int) -> tuple[Attachment, Path]:
        attachment = await self.session.get(Attachment, attachment_id)
        if attachment is None:
            raise MaintenanceAPIError(404, "NOT_FOUND", "附件不存在")
        path = self.upload_dir() / attachment.storage_key
        if not path.is_file():
            raise MaintenanceAPIError(404, "NOT_FOUND", "文件已丢失")
        return attachment, path
