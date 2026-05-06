"""Alembic 异步迁移环境配置.

支持 SQLite (aiosqlite) 和 PostgreSQL (asyncpg) 的无缝切换.
SQLAlchemy 2.0 AsyncEngine + AsyncSession 架构.
"""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_engine_from_config,
)

# 导入项目模型和数据库配置
from app.core.config import get_settings
from app.models import (  # noqa: F401 - 导入所有模型以注册 metadata
    AgentRun,
    Annotation,
    ApprovalTask,
    AuditLog,
    AuthUser,
    Base,
    Device,
    DeviceModel,
    Escalation,
    FlowTemplate,
    KnowledgeArticle,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeRelation,
    MaintenanceCase,
    MaintenanceCaseCorrection,
    MaintenanceTask,
    MaintenanceTaskStep,
    MaintenanceTaskTemplate,
    MaintenanceTaskTemplateStep,
    Attachment,
    RetrievalSnapshot,
    Role,
    SensorData,
    SystemConfig,
    UserRole,
    WorkOrder,
    WorkOrderEvent,
    WorkOrderFilling,
    WorkOrderFillingAttachment,
    WorkOrderMessage,
)

# Alembic Config 对象
config = context.config

settings = get_settings()
# 统一以应用配置为准，避免 Alembic 与应用连接到不同数据库
config.set_main_option("sqlalchemy.url", settings.database_url)

# 模型元数据 (用于 autogenerate 支持)
target_metadata = Base.metadata

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def get_async_engine() -> AsyncEngine:
    """根据 URL 前缀创建对应的异步引擎."""
    url = config.get_main_option("sqlalchemy.url")
    is_sqlite = url and url.startswith("sqlite")

    if is_sqlite:
        # SQLite: NullPool 避免线程检查问题，check_same_thread=False
        return async_engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
            connect_args={"check_same_thread": False},
        )
    else:
        # PostgreSQL / 其他: 默认连接池
        return async_engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            pool_pre_ping=True,
        )


def run_migrations_offline() -> None:
    """离线模式运行迁移 (不需要数据库连接).

    用于生成 SQL 脚本而非直接修改数据库.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations_online() -> None:
    """在线模式运行迁移 (异步).

    为每个数据库 dialect 创建异步 Engine 和 MigrationContext.
    """
    connectable: AsyncEngine = get_async_engine()

    async with connectable.connect() as connection:
        def do_configure_and_migrate(conn: Connection) -> None:
            context.configure(
                connection=conn,
                target_metadata=target_metadata,
            )
            with context.begin_transaction():
                context.run_migrations()

        await connection.run_sync(do_configure_and_migrate)


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations_online())
