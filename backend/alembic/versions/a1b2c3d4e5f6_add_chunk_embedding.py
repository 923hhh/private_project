"""add chunk embedding pgvector

Revision ID: a1b2c3d4e5f6
Revises: f6d8c2b1a4e7
Create Date: 2026-05-04 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f9a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite (test env) does not support pgvector — skip silently
        return

    # 启用 pgvector 扩展（幂等，已有时不报错）
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 添加 embedding 列（nullable，存量数据无向量）
    # 用原生 SQL 避免 pgvector SQLAlchemy 类型在 alembic 环境里的依赖问题
    op.execute(
        "ALTER TABLE knowledge_chunks "
        "ADD COLUMN IF NOT EXISTS embedding vector(1024)"
    )

    # 创建 HNSW 索引（余弦距离，适合 bge-m3 归一化向量）
    # m=16 ef_construction=64 是 pgvector 推荐的平衡参数
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding_hnsw "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_hnsw")
    op.execute(
        "ALTER TABLE knowledge_chunks DROP COLUMN IF EXISTS embedding"
    )
