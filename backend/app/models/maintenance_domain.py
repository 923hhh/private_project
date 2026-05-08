"""检修域 数据模型（对齐《数据字典与数据库设计文档》V1.1）。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def _utc_naive() -> datetime:
    """列无时区信息时使用 naive UTC（替代已弃用的 datetime.utcnow）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuthUser(Base):
    """用户表 `users`。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_naive, onupdate=_utc_naive, nullable=False
    )

    roles: Mapped[list["Role"]] = relationship(
        secondary="user_roles",
        back_populates="users",
    )


class Role(Base):
    """角色表 `roles`。"""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)

    users: Mapped[list[AuthUser]] = relationship(
        secondary="user_roles",
        back_populates="roles",
    )


class UserRole(Base):
    """用户-角色关联。"""

    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )


class Device(Base):
    """设备台账 `devices`。"""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    asset_code: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    responsibility_expert_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_naive, onupdate=_utc_naive, nullable=False
    )


class FlowTemplate(Base):
    """流程模板 `flow_templates`。"""

    __tablename__ = "flow_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    device_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    maintenance_level: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    steps_json: Mapped[list[Any] | dict[str, Any]] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="published", nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class WorkOrder(Base):
    """工单主表 `work_orders`。"""

    __tablename__ = "work_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(4), default="S1", nullable=False, index=True)
    maintenance_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assigned_worker_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_expert_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_safety_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    current_owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    flow_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("flow_templates.id", ondelete="SET NULL"), nullable=True
    )
    current_step_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    # 与 retrieval_snapshots 逻辑关联；避免与 work_order_id 循环外键，首版不设 DB 级 FK
    last_retrieval_snapshot_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    step_progress_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )  # 工步完成标记等，首版 JSON 即可
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_naive, onupdate=_utc_naive, nullable=False
    )


class WorkOrderEvent(Base):
    """工单事件流水。"""

    __tablename__ = "work_order_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(4), nullable=True)
    to_status: Mapped[str] = mapped_column(String(4), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_naive, nullable=False)


class UserNotification(Base):
    """用户通知中心消息。"""

    __tablename__ = "user_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    link_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_naive, onupdate=_utc_naive, nullable=False
    )


class RetrievalSnapshot(Base):
    """检索快照。"""

    __tablename__ = "retrieval_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    query_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunks: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    knowledge_corpus_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence_top1: Mapped[float | None] = mapped_column(Float, nullable=True)
    empty_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    degraded_response: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    prompt_template_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_context_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_naive, nullable=False)


class WorkOrderMessage(Base):
    """工单对话消息。"""

    __tablename__ = "work_order_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("retrieval_snapshots.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_naive, nullable=False)


class Attachment(Base):
    """附件元数据。"""

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    biz_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_naive, nullable=False)


class Escalation(Base):
    """升级会诊。"""

    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False, index=True)
    assigned_expert_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    escalation_note: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_ids: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    related_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("work_order_messages.id", ondelete="SET NULL"), nullable=True
    )
    conclusion_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_naive, onupdate=_utc_naive, nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ApprovalTask(Base):
    """高危审批任务。"""

    __tablename__ = "approval_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    resolution: Mapped[str | None] = mapped_column(String(32), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    material_attachment_ids: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    approver_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_naive, onupdate=_utc_naive, nullable=False
    )


class WorkOrderFilling(Base):
    """结果回填。"""

    __tablename__ = "work_order_fillings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(16), nullable=False)
    closure_code: Mapped[str] = mapped_column(String(32), nullable=False)
    post_unresolved_action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    unresolved_reason_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    detail_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    submitted_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_naive, nullable=False)


class WorkOrderFillingAttachment(Base):
    """回填与附件多对多。"""

    __tablename__ = "work_order_filling_attachments"

    filling_id: Mapped[int] = mapped_column(
        ForeignKey("work_order_fillings.id", ondelete="CASCADE"), primary_key=True
    )
    attachment_id: Mapped[int] = mapped_column(
        ForeignKey("attachments.id", ondelete="CASCADE"), primary_key=True
    )


class KnowledgeArticle(Base):
    """可发布知识条目（检修域）。"""

    __tablename__ = "knowledge_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source_work_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True
    )
    reviewer_expert_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    publisher_admin_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_naive, onupdate=_utc_naive, nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Annotation(Base):
    """模型输出标注。"""

    __tablename__ = "annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[int] = mapped_column(
        ForeignKey("work_order_messages.id", ondelete="CASCADE"), nullable=False
    )
    annotator_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_kb_patch_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_articles.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_naive, nullable=False)


class AuditLog(Base):
    """审计日志。"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    business_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_naive, nullable=False)


class SystemConfig(Base):
    """系统配置键值。"""

    __tablename__ = "system_configs"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(16), default="string", nullable=False)
    reload_policy: Mapped[str] = mapped_column(String(16), default="restart", nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_naive, nullable=False)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


__all__ = [
    "AuthUser",
    "Role",
    "UserRole",
    "Device",
    "FlowTemplate",
    "WorkOrder",
    "WorkOrderEvent",
    "RetrievalSnapshot",
    "WorkOrderMessage",
    "Attachment",
    "Escalation",
    "ApprovalTask",
    "WorkOrderFilling",
    "WorkOrderFillingAttachment",
    "KnowledgeArticle",
    "Annotation",
    "AuditLog",
    "SystemConfig",
]
