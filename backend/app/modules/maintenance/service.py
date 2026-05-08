"""Standardized maintenance service facade."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.maintenance import (
    ApprovalTask,
    AuditLog,
    Device,
    Escalation,
    Attachment,
    WorkOrder,
    WorkOrderEvent,
)
from app.db.models.tasks import MaintenanceTask
from app.modules.maintenance.application.attachment_service import MaintenanceAttachmentService
from app.modules.maintenance.application.audit_service import MaintenanceAuditService
from app.modules.maintenance.application.annotation_service import MaintenanceAnnotationService
from app.modules.maintenance.application.auth_service import MaintenanceAuthService
from app.modules.maintenance.application.approval_service import MaintenanceApprovalService
from app.modules.maintenance.application.device_service import MaintenanceDeviceService
from app.modules.maintenance.application.escalation_service import MaintenanceEscalationService
from app.modules.maintenance.application.flow_template_service import MaintenanceFlowTemplateService
from app.modules.maintenance.application.knowledge_article_service import (
    MaintenanceKnowledgeArticleService,
)
from app.modules.maintenance.application.notification_service import MaintenanceNotificationService
from app.modules.maintenance.application.system_config_service import MaintenanceSystemConfigService
from app.modules.maintenance.application.work_order_execution_service import (
    MaintenanceWorkOrderExecutionService,
)
from app.modules.maintenance.application.work_order_message_service import (
    MaintenanceWorkOrderMessageService,
)
from app.modules.maintenance.application.work_order_retrieval_service import (
    MaintenanceWorkOrderRetrievalService,
)
from app.modules.maintenance.application.work_order_service import MaintenanceWorkOrderService
from app.modules.maintenance.datetime_util import to_iso_cn, utc_now_naive
from app.modules.maintenance.deps import CurrentUserCtx

ATTACHMENT_UPLOAD_MAX_BYTES = 10 * 1024 * 1024

class MaintenanceService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.auth_service = MaintenanceAuthService(session, settings)
        self.attachment_service = MaintenanceAttachmentService(session, settings)
        self.audit_service = MaintenanceAuditService(session)
        self.work_order_service = MaintenanceWorkOrderService(session, self._audit)
        self.notification_service = MaintenanceNotificationService(session)
        self.annotation_service = MaintenanceAnnotationService(
            session,
            self._audit,
            self.work_order_service,
        )
        self.device_service = MaintenanceDeviceService(session, self._audit)
        self.flow_template_service = MaintenanceFlowTemplateService(session)
        self.system_config_service = MaintenanceSystemConfigService(session)
        self.work_order_message_service = MaintenanceWorkOrderMessageService(
            session,
            self.work_order_service,
        )
        self.work_order_retrieval_service = MaintenanceWorkOrderRetrievalService(
            session,
            self._audit,
            self.work_order_service,
            self.device_service,
        )
        self.approval_service = MaintenanceApprovalService(
            session,
            self._audit,
            self.work_order_service,
        )
        self.escalation_service = MaintenanceEscalationService(
            session,
            self._audit,
            self.work_order_service,
            self.device_service,
        )
        self.knowledge_article_service = MaintenanceKnowledgeArticleService(
            session,
            self._audit,
            self.work_order_service,
        )
        self.work_order_execution_service = MaintenanceWorkOrderExecutionService(
            session,
            self._audit,
            self.work_order_service,
            self.device_service,
        )

    async def _audit(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        actor_user_id: int | None,
        payload: dict | None = None,
        business_code: str | None = None,
    ) -> None:
        self.session.add(
            AuditLog(
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                actor_user_id=actor_user_id,
                payload=payload,
                business_code=business_code,
                created_at=utc_now_naive(),
            )
        )

    async def login(self, username: str, password: str) -> dict[str, Any]:
        return await self.auth_service.login(username, password)

    async def get_me(self, ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.auth_service.get_me(ctx)

    async def list_notifications(self, ctx: CurrentUserCtx, limit: int = 20) -> dict[str, Any]:
        return await self.notification_service.list_notifications(ctx, limit=limit)

    async def mark_notification_read(self, notification_id: int, ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.notification_service.mark_read(notification_id, ctx)

    async def mark_all_notifications_read(self, ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.notification_service.mark_all_read(ctx)

    async def list_devices(
        self,
        *,
        page: int,
        page_size: int,
        device_type: str | None,
        model: str | None,
        q: str | None,
    ) -> dict[str, Any]:
        return await self.device_service.list_devices(
            page=page,
            page_size=page_size,
            device_type=device_type,
            model=model,
            q=q,
        )

    async def get_device(self, device_id: int) -> Device:
        return await self.device_service.get_device(device_id)

    async def patch_device(self, device_id: int, body: dict[str, Any], ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.device_service.patch_device(device_id, body, ctx)

    async def create_device(self, body: dict[str, Any], ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.device_service.create_device(body, ctx)

    def _sign_attachment_token(self, attachment_id: int, exp: int) -> str:
        return self.attachment_service.sign_attachment_token(attachment_id, exp)

    def _verify_attachment_token(self, token: str) -> tuple[int, int]:
        return self.attachment_service.verify_attachment_token(token)

    async def save_attachment(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        mime: str,
        biz_type: str,
        work_order_id: int | None,
        ctx: CurrentUserCtx,
    ) -> dict[str, Any]:
        return await self.attachment_service.save_attachment(
            file_bytes=file_bytes,
            filename=filename,
            mime=mime,
            biz_type=biz_type,
            work_order_id=work_order_id,
            ctx=ctx,
        )

    async def get_attachment_for_download(self, attachment_id: int, ctx: CurrentUserCtx) -> Attachment:
        return await self.attachment_service.get_attachment_for_download(attachment_id, ctx)

    async def attachment_file_path(self, attachment_id: int) -> tuple[Attachment, Path]:
        return await self.attachment_service.attachment_file_path(attachment_id)

    async def _get_wo(self, work_order_id: int) -> WorkOrder:
        return await self.work_order_service.get_work_order(work_order_id)

    async def _assert_wo_readable(self, ctx: CurrentUserCtx, wo: WorkOrder) -> None:
        await self.work_order_service.assert_work_order_readable(ctx, wo)

    async def _transition(
        self,
        wo: WorkOrder,
        to_status: str,
        *,
        event_type: str,
        actor_user_id: int | None,
        payload: dict | None = None,
    ) -> None:
        await self.work_order_service.transition(
            wo,
            to_status,
            event_type=event_type,
            actor_user_id=actor_user_id,
            payload=payload,
        )

    async def create_work_order(self, body: dict[str, Any], ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.work_order_service.create_work_order(body, ctx)

    async def list_work_orders(
        self,
        ctx: CurrentUserCtx,
        *,
        page: int,
        page_size: int,
        status: str | None,
        device_id: int | None,
        mine: bool | None,
        assignment_role: str | None = None,
        assignment_state: str | None = None,
    ) -> dict[str, Any]:
        return await self.work_order_service.list_work_orders(
            ctx,
            page=page,
            page_size=page_size,
            status=status,
            device_id=device_id,
            mine=mine,
            assignment_role=assignment_role,
            assignment_state=assignment_state,
        )

    async def delete_work_order(self, work_order_id: int, ctx: CurrentUserCtx) -> None:
        await self.work_order_service.delete_work_order(work_order_id, ctx)

    async def get_work_order_detail(self, work_order_id: int, ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.work_order_service.get_work_order_detail(work_order_id, ctx)

    async def list_assignment_candidates(self, ctx: CurrentUserCtx, role_code: str | None = None) -> dict[str, Any]:
        return await self.work_order_service.list_assignment_candidates(ctx, role_code=role_code)

    async def update_work_order_assignment(
        self,
        work_order_id: int,
        body: dict[str, Any],
        ctx: CurrentUserCtx,
    ) -> dict[str, Any]:
        return await self.work_order_service.update_assignment(work_order_id, body, ctx)

    async def list_events(self, work_order_id: int, ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.work_order_service.list_events(work_order_id, ctx)

    async def post_retrieval(
        self,
        work_order_id: int,
        body: dict[str, Any],
        ctx: CurrentUserCtx,
    ) -> dict[str, Any]:
        return await self.work_order_retrieval_service.post_retrieval(work_order_id, body, ctx)

    async def retrieval_stream(
        self,
        work_order_id: int,
        query_text: str,
        maintenance_level: str | None,
        ctx: CurrentUserCtx,
        emit: Any,
    ) -> None:
        await self.work_order_retrieval_service.retrieval_stream(
            work_order_id,
            query_text,
            maintenance_level,
            ctx,
            emit,
        )

    async def post_user_message(
        self,
        work_order_id: int,
        body: dict[str, Any],
        ctx: CurrentUserCtx,
    ) -> dict[str, Any]:
        return await self.work_order_message_service.post_user_message(work_order_id, body, ctx)

    async def list_messages(
        self,
        work_order_id: int,
        ctx: CurrentUserCtx,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        return await self.work_order_message_service.list_messages(
            work_order_id,
            ctx,
            page,
            page_size,
        )

    async def action_enter_maintenance(self, work_order_id: int, ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.work_order_execution_service.action_enter_maintenance(work_order_id, ctx)

    async def action_complete_maintenance(self, work_order_id: int, ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.work_order_execution_service.action_complete_maintenance(work_order_id, ctx)

    async def action_accept_fill_review(self, work_order_id: int, ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.work_order_execution_service.action_accept_fill_review(work_order_id, ctx)

    def _validate_filling(self, body: dict[str, Any]) -> None:
        self.work_order_execution_service.validate_filling(body)

    async def post_filling(self, work_order_id: int, body: dict[str, Any], ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.work_order_execution_service.post_filling(work_order_id, body, ctx)

    async def list_approval_tasks(self, ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.approval_service.list_approval_tasks(ctx)

    async def resolve_approval(
        self,
        approval_task_id: int,
        body: dict[str, Any],
        ctx: CurrentUserCtx,
    ) -> dict[str, Any]:
        return await self.approval_service.resolve_approval(approval_task_id, body, ctx)

    async def create_escalation(self, work_order_id: int, body: dict[str, Any], ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.escalation_service.create_escalation(work_order_id, body, ctx)

    async def get_escalation(self, escalation_id: int, ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.escalation_service.get_escalation(escalation_id, ctx)

    async def resolve_escalation(
        self,
        escalation_id: int,
        body: dict[str, Any],
        ctx: CurrentUserCtx,
    ) -> dict[str, Any]:
        return await self.escalation_service.resolve_escalation(escalation_id, body, ctx)

    async def list_flow_templates(self, device_type: str | None, maintenance_level: str | None) -> dict[str, Any]:
        return await self.flow_template_service.list_flow_templates(device_type, maintenance_level)

    async def get_flow_template(self, template_id: int) -> dict[str, Any]:
        return await self.flow_template_service.get_flow_template(template_id)

    async def confirm_step(self, work_order_id: int, body: dict[str, Any], ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.work_order_service.confirm_step(work_order_id, body, ctx)

    async def create_annotation(
        self,
        work_order_id: int,
        message_id: int,
        body: dict[str, Any],
        ctx: CurrentUserCtx,
    ) -> dict[str, Any]:
        return await self.annotation_service.create_annotation(work_order_id, message_id, body, ctx)

    async def spawn_kb_draft(self, annotation_id: int, body: dict[str, Any], ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.knowledge_article_service.spawn_kb_draft(annotation_id, body, ctx)

    async def kb_from_work_order(self, body: dict[str, Any], ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.knowledge_article_service.kb_from_work_order(body, ctx)

    async def list_kb_articles(
        self,
        ctx: CurrentUserCtx,
        status: str | None,
        page: int,
        page_size: int,
        series_id: int | None = None,
    ) -> dict[str, Any]:
        return await self.knowledge_article_service.list_kb_articles(ctx, status, page, page_size, series_id)

    async def get_kb_publish_console(self, ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.knowledge_article_service.get_publish_console(ctx)

    async def get_kb_article_versions(self, article_id: int, ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.knowledge_article_service.get_article_versions(article_id, ctx)

    async def review_kb(self, article_id: int, body: dict[str, Any], ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.knowledge_article_service.review_kb(article_id, body, ctx)

    async def publish_kb(self, article_id: int, body: dict[str, Any] | None, ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.knowledge_article_service.publish_kb(article_id, body, ctx)

    async def withdraw_kb(self, article_id: int, ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.knowledge_article_service.withdraw_kb(article_id, ctx)

    async def list_audit_logs(
        self,
        ctx: CurrentUserCtx,
        *,
        page: int,
        page_size: int,
        resource_type: str | None,
        resource_id: str | None,
    ) -> dict[str, Any]:
        return await self.audit_service.list_audit_logs(
            ctx,
            page=page,
            page_size=page_size,
            resource_type=resource_type,
            resource_id=resource_id,
        )

    async def list_system_configs(self, ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.system_config_service.list_system_configs(ctx)

    async def patch_system_config(self, key: str, body: dict[str, Any], ctx: CurrentUserCtx) -> dict[str, Any]:
        return await self.system_config_service.patch_system_config(key, body, ctx)

    async def admin_list_users(self, page: int, page_size: int) -> dict[str, Any]:
        return await self.auth_service.admin_list_users(page, page_size)

    async def admin_create_user(self, body: dict[str, Any]) -> dict[str, Any]:
        return await self.auth_service.admin_create_user(body)

    async def admin_assign_roles(self, user_id: int, body: dict[str, Any]) -> None:
        await self.auth_service.admin_assign_roles(user_id, body)

    async def health_sub(self) -> dict[str, Any]:
        return await self.system_config_service.health_sub()
