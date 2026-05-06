"""从 JSONL 批量导入知识条目到知识库。

用法（在 backend 目录下执行）:
    python scripts/import_knowledge_jsonl.py "../datasets/knowledge/text/hf_jaya1995_maintenance.jsonl" --replace-existing
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, select

from app.db.models.knowledge import KnowledgeDocument
from app.db.session import get_session_context
from app.modules.knowledge.application.search_service import KnowledgeService
from app.modules.knowledge.schemas.search import KnowledgeDocumentCreate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="将 JSONL 知识条目批量导入知识库")
    parser.add_argument("jsonl_path", help="JSONL 文件路径（每行一条知识文档）")
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="按 source_name 去重替换：导入前先删除同 source_name 的旧文档",
    )
    return parser


def read_jsonl(path: Path) -> list[KnowledgeDocumentCreate]:
    if not path.exists():
        raise FileNotFoundError(f"JSONL 文件不存在: {path}")

    requests: list[KnowledgeDocumentCreate] = []
    with path.open("r", encoding="utf-8") as f:
        for index, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"第 {index} 行不是合法 JSON: {exc}") from exc
            try:
                requests.append(KnowledgeDocumentCreate(**payload))
            except Exception as exc:
                raise ValueError(f"第 {index} 行字段校验失败: {exc}") from exc

    if not requests:
        raise ValueError("JSONL 中没有可导入的有效记录。")
    return requests


async def import_jsonl(args: argparse.Namespace) -> None:
    jsonl_path = Path(args.jsonl_path).resolve()
    requests = read_jsonl(jsonl_path)
    source_names = sorted({item.source_name for item in requests if item.source_name})

    async with get_session_context() as session:
        if args.replace_existing and source_names:
            existing_ids = (
                await session.execute(
                    select(KnowledgeDocument.id).where(KnowledgeDocument.source_name.in_(source_names))
                )
            ).scalars().all()
            if existing_ids:
                await session.execute(delete(KnowledgeDocument).where(KnowledgeDocument.id.in_(existing_ids)))
                await session.commit()

        service = KnowledgeService(session)
        imported = 0
        chunks_total = 0
        for item in requests:
            _, chunk_count = await service.create_document(item)
            imported += 1
            chunks_total += chunk_count

    print("JSONL 知识导入完成。")
    print(f"文件: {jsonl_path}")
    print(f"导入文档数: {imported}")
    print(f"知识分段总数: {chunks_total}")
    print(f"去重替换: {'是' if args.replace_existing else '否'}")


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(import_jsonl(args))


if __name__ == "__main__":
    main()
