#!/usr/bin/env python3
"""
为 TC-KB-003 / 演示在「同一数据库」中插入一条可检索的 knowledge_chunks 语料，
使设备类型 pump_test + 型号 M1 的检索能命中（与检修域设备 AST-TC-1 对齐）。

用法（开发库 SQLite 示例）：
  set DATABASE_URL=sqlite+aiosqlite:///./sensor_data.db
  python scripts/seed_kb_chunk_for_maintenance_demo.py

重复执行会跳过（按 source_name 查重）。
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _naive_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def main() -> int:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models.knowledge import KnowledgeChunk, KnowledgeDocument

    raw = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./sensor_data.db")
    sync_url = raw.replace("sqlite+aiosqlite://", "sqlite://").replace("+asyncpg", "")
    engine = create_engine(sync_url, future=True)
    source_name = "演示-检修条目同步"
    equipment_type = "pump_test"
    equipment_model = "M1"

    with Session(engine) as session:
        existing = session.execute(
            select(KnowledgeDocument.id).where(KnowledgeDocument.source_name == source_name)
        ).scalar_one_or_none()
        if existing is not None:
            print(f"已存在文档 id={existing}（source_name={source_name}），跳过。")
            return 0

        now = _naive_utc()
        doc = KnowledgeDocument(
            title="检修域发布后检索演示",
            source_name=source_name,
            source_type="manual",
            equipment_type=equipment_type,
            equipment_model=equipment_model,
            fault_type=None,
            section_reference=None,
            page_reference=None,
            content="本段用于答辩演示：泄漏处理、密封更换与压力恢复检查要点。",
            status="published",
            created_at=now,
            updated_at=now,
        )
        session.add(doc)
        session.flush()
        chunk = KnowledgeChunk(
            document_id=doc.id,
            chunk_index=0,
            heading="演示",
            content="泄漏处理与密封件更换步骤说明，压力恢复后需复核。",
            equipment_type=equipment_type,
            equipment_model=equipment_model,
            fault_type=None,
            section_reference=None,
            section_path=None,
            step_anchor=None,
            page_reference=None,
            image_anchor=None,
            created_at=now,
        )
        session.add(chunk)
        session.commit()
        print(f"已写入 knowledge_documents.id={doc.id}，knowledge_chunks.id={chunk.id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
