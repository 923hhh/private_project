"""maintenance_domain_tables

Revision ID: e8f1a2b3c4d5
Revises: d2f6e4c1b8a9
Create Date: 2026-04-11

检修域 表：对齐《数据字典》V1.1；SQLite/PG 共用 DDL，部分唯一索引在两种方言下均尝试创建。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e8f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "d2f6e4c1b8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_type", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("asset_code", sa.String(length=64), nullable=True),
        sa.Column("location", sa.String(length=256), nullable=True),
        sa.Column("responsibility_expert_user_id", sa.Integer(), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["responsibility_expert_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_code"),
    )
    op.create_index("ix_devices_device_type", "devices", ["device_type"])
    op.create_index("ix_devices_model", "devices", ["model"])
    op.create_index(
        "ix_devices_responsibility_expert_user_id",
        "devices",
        ["responsibility_expert_user_id"],
    )

    op.create_table(
        "flow_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("device_type", sa.String(length=64), nullable=False),
        sa.Column("maintenance_level", sa.String(length=32), nullable=False),
        sa.Column("steps_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_flow_templates_device_type", "flow_templates", ["device_type"])
    op.create_index("ix_flow_templates_maintenance_level", "flow_templates", ["maintenance_level"])

    op.create_table(
        "work_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=4), nullable=False),
        sa.Column("maintenance_level", sa.String(length=32), nullable=True),
        sa.Column("flow_template_id", sa.Integer(), nullable=True),
        sa.Column("current_step_no", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("last_retrieval_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("step_progress_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["flow_template_id"], ["flow_templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_work_orders_device_id", "work_orders", ["device_id"])
    op.create_index("ix_work_orders_status", "work_orders", ["status"])
    op.create_index("ix_work_orders_created_by_user_id", "work_orders", ["created_by_user_id"])
    op.create_index(
        "ix_work_orders_last_retrieval_snapshot_id",
        "work_orders",
        ["last_retrieval_snapshot_id"],
    )

    op.create_table(
        "work_order_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=4), nullable=True),
        sa.Column("to_status", sa.String(length=4), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_work_order_events_work_order_id", "work_order_events", ["work_order_id"])

    op.create_table(
        "retrieval_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=True),
        sa.Column("chunks", sa.JSON(), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("knowledge_corpus_version", sa.String(length=64), nullable=True),
        sa.Column("confidence_top1", sa.Float(), nullable=True),
        sa.Column("empty_hit", sa.Boolean(), nullable=False),
        sa.Column("degraded_response", sa.Boolean(), nullable=False),
        sa.Column("prompt_template_version", sa.String(length=64), nullable=True),
        sa.Column("device_context_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_retrieval_snapshots_work_order_id", "retrieval_snapshots", ["work_order_id"])

    op.create_table(
        "work_order_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("retrieval_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["retrieval_snapshot_id"],
            ["retrieval_snapshots.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_work_order_messages_work_order_id", "work_order_messages", ["work_order_id"])

    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=True),
        sa.Column("biz_type", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attachments_work_order_id", "attachments", ["work_order_id"])
    op.create_index("ix_attachments_biz_type", "attachments", ["biz_type"])

    op.create_table(
        "escalations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assigned_expert_user_id", sa.Integer(), nullable=False),
        sa.Column("escalation_note", sa.Text(), nullable=False),
        sa.Column("attachment_ids", sa.JSON(), nullable=True),
        sa.Column("related_message_id", sa.Integer(), nullable=True),
        sa.Column("conclusion_text", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["assigned_expert_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["related_message_id"],
            ["work_order_messages.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_escalations_work_order_id", "escalations", ["work_order_id"])
    op.create_index("ix_escalations_status", "escalations", ["status"])

    op.create_table(
        "approval_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("step_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("resolution", sa.String(length=32), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("material_attachment_ids", sa.JSON(), nullable=True),
        sa.Column("approver_user_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["approver_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_tasks_work_order_id", "approval_tasks", ["work_order_id"])

    op.create_table(
        "work_order_fillings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("is_latest", sa.Boolean(), nullable=False),
        sa.Column("resolution_status", sa.String(length=16), nullable=False),
        sa.Column("closure_code", sa.String(length=32), nullable=False),
        sa.Column("post_unresolved_action", sa.String(length=32), nullable=True),
        sa.Column("unresolved_reason_code", sa.String(length=32), nullable=True),
        sa.Column("detail_notes", sa.String(length=2000), nullable=True),
        sa.Column("submitted_by_user_id", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_work_order_fillings_work_order_id", "work_order_fillings", ["work_order_id"])

    op.create_table(
        "work_order_filling_attachments",
        sa.Column("filling_id", sa.Integer(), nullable=False),
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["filling_id"], ["work_order_fillings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("filling_id", "attachment_id"),
    )

    op.create_table(
        "knowledge_articles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("series_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_work_order_id", sa.Integer(), nullable=True),
        sa.Column("reviewer_expert_user_id", sa.Integer(), nullable=True),
        sa.Column("publisher_admin_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["publisher_admin_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_expert_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_work_order_id"],
            ["work_orders.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_articles_series_id", "knowledge_articles", ["series_id"])
    op.create_index("ix_knowledge_articles_status", "knowledge_articles", ["status"])

    op.create_table(
        "annotations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("annotator_user_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("candidate_kb_patch_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_kb_patch_id"],
            ["knowledge_articles.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["annotator_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["work_order_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_annotations_work_order_id", "annotations", ["work_order_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("business_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])

    op.create_table(
        "system_configs",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("value_type", sa.String(length=16), nullable=False),
        sa.Column("reload_policy", sa.String(length=16), nullable=False),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("key"),
    )

    # 预置角色
    roles = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
    )
    op.bulk_insert(
        roles,
        [
            {"id": 1, "code": "worker", "name": "一线检修工人"},
            {"id": 2, "code": "expert", "name": "检修专家"},
            {"id": 3, "code": "safety", "name": "安全审批人"},
            {"id": 4, "code": "admin", "name": "系统管理员"},
        ],
    )

    # 默认流程模板（机泵 / 标准检修）
    steps = [
        {
            "step_no": 1,
            "title": "停机与挂牌",
            "requires_approval": False,
        },
        {
            "step_no": 2,
            "title": "高危拆解作业",
            "requires_approval": True,
        },
    ]
    ft = sa.table(
        "flow_templates",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("device_type", sa.String),
        sa.column("maintenance_level", sa.String),
        sa.column("steps_json", sa.JSON),
        sa.column("version", sa.Integer),
        sa.column("status", sa.String),
        sa.column("published_at", sa.DateTime),
    )
    op.bulk_insert(
        ft,
        [
            {
                "id": 1,
                "name": "机泵标准检修",
                "device_type": "pump",
                "maintenance_level": "计划定修",
                "steps_json": steps,
                "version": 1,
                "status": "published",
                "published_at": None,
            },
        ],
    )

    # 部分唯一索引（SQLite 3.31+ / PostgreSQL）
    bind = op.get_bind()
    if bind.dialect.name in ("sqlite", "postgresql"):
        op.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_escalation_active
            ON escalations(work_order_id)
            WHERE status IN ('open','in_progress')
            """
        )
        if bind.dialect.name == "sqlite":
            op.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_filling_latest
                ON work_order_fillings(work_order_id)
                WHERE is_latest = 1
                """
            )
        else:
            op.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_filling_latest
                ON work_order_fillings(work_order_id)
                WHERE is_latest IS TRUE
                """
            )
        op.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_approval_pending
            ON approval_tasks(work_order_id, step_no)
            WHERE status = 'pending'
            """
        )
        op.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_kb_series_published
            ON knowledge_articles(series_id)
            WHERE status = 'published'
            """
        )
        op.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_flow_template_published
            ON flow_templates(device_type, maintenance_level)
            WHERE status = 'published'
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name in ("sqlite", "postgresql"):
        for name in (
            "ux_flow_template_published",
            "ux_kb_series_published",
            "ux_approval_pending",
            "ux_filling_latest",
            "ux_escalation_active",
        ):
            op.execute(f"DROP INDEX IF EXISTS {name}")
    op.drop_table("system_configs")
    op.drop_table("audit_logs")
    op.drop_table("annotations")
    op.drop_table("knowledge_articles")
    op.drop_table("work_order_filling_attachments")
    op.drop_table("work_order_fillings")
    op.drop_table("approval_tasks")
    op.drop_table("escalations")
    op.drop_table("attachments")
    op.drop_table("work_order_messages")
    op.drop_table("retrieval_snapshots")
    op.drop_table("work_order_events")
    op.drop_table("work_orders")
    op.drop_table("flow_templates")
    op.drop_table("devices")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_table("users")
