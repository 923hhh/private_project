"""Import a PDF manual into the knowledge base with page-aware chunks.

Usage:
    python scripts/import_knowledge_pdf.py "摩托车发动机维修手册.pdf" --equipment-type "摩托车发动机"
"""
from __future__ import annotations

import argparse
import asyncio
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.session import get_session_context
from app.integrations.pdf_import import PdfKnowledgeImportService
from app.db.models.knowledge import KnowledgeDocument
from app.modules.knowledge.application.search_service import KnowledgeService
from app.modules.knowledge.schemas.search import KnowledgeDocumentCreate


async def import_pdf(args: argparse.Namespace) -> None:
    """Extract PDF text and import it as a knowledge document."""
    pdf_path = Path(args.pdf_path).resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

    importer = PdfKnowledgeImportService()
    pages = importer.extract_pages(pdf_path)
    title = args.title or pdf_path.stem
    content = importer.build_document_content(pages)
    chunk_payloads = importer.build_chunk_payloads(
        title=title,
        pages=pages,
        max_chars=args.max_chars,
    )

    request = KnowledgeDocumentCreate(
        title=title,
        source_name=pdf_path.name,
        source_type=args.source_type,
        equipment_type=args.equipment_type,
        equipment_model=args.equipment_model,
        fault_type=args.fault_type,
        section_reference=args.section_reference,
        page_reference=f"P1-P{pages[-1].page_number}",
        content=content,
    )

    settings = get_settings()
    if settings.database_url.startswith("sqlite+aiosqlite:///"):
        document_id, chunk_count = import_pdf_into_sqlite(
            database_url=settings.database_url,
            request=request,
            chunk_payloads=chunk_payloads,
            replace_existing=args.replace_existing,
        )
        print("PDF 知识导入完成。")
        print(f"文档 ID: {document_id}")
        print(f"标题: {request.title}")
        print(f"页数: {len(pages)}")
        print(f"知识分段数: {chunk_count}")
        print(f"设备类型: {request.equipment_type}")
        print(f"设备型号: {request.equipment_model or '未指定'}")
        return

    async with get_session_context() as session:
        if args.replace_existing:
            existing_ids = (
                await session.execute(
                    select(KnowledgeDocument.id).where(
                        KnowledgeDocument.source_name == pdf_path.name
                    )
                )
            ).scalars().all()
            if existing_ids:
                await session.execute(
                    delete(KnowledgeDocument).where(KnowledgeDocument.id.in_(existing_ids))
                )
                await session.flush()

        service = KnowledgeService(session)
        document, chunk_count = await service.create_document(
            request,
            chunk_payloads=chunk_payloads,
        )

    print("PDF 知识导入完成。")
    print(f"文档 ID: {document.id}")
    print(f"标题: {document.title}")
    print(f"页数: {len(pages)}")
    print(f"知识分段数: {chunk_count}")
    print(f"设备类型: {document.equipment_type}")
    print(f"设备型号: {document.equipment_model or '未指定'}")


def import_pdf_into_sqlite(
    database_url: str,
    request: KnowledgeDocumentCreate,
    chunk_payloads: list[dict[str, str | None]],
    replace_existing: bool,
) -> tuple[int, int]:
    """Import PDF-derived knowledge into a file-backed SQLite DB via sqlite3."""
    db_path = resolve_sqlite_path(database_url)
    now = utcnow_string()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()

        if replace_existing:
            existing_ids = [
                row[0]
                for row in cur.execute(
                    "SELECT id FROM knowledge_documents WHERE source_name = ?",
                    (request.source_name,),
                ).fetchall()
            ]
            if existing_ids:
                placeholders = ",".join("?" for _ in existing_ids)
                cur.execute(
                    f"DELETE FROM knowledge_chunks WHERE document_id IN ({placeholders})",
                    existing_ids,
                )
                cur.execute(
                    f"DELETE FROM knowledge_documents WHERE id IN ({placeholders})",
                    existing_ids,
                )

        if request.equipment_model:
            cur.execute(
                """
                INSERT OR IGNORE INTO device_models
                    (equipment_type, model_code, display_name, manufacturer, description, created_at, updated_at)
                VALUES (?, ?, ?, NULL, NULL, ?, ?)
                """,
                (
                    request.equipment_type,
                    request.equipment_model,
                    request.equipment_model,
                    now,
                    now,
                ),
            )

        cur.execute(
            """
            INSERT INTO knowledge_documents
                (title, source_name, source_type, equipment_type, equipment_model, fault_type,
                 section_reference, page_reference, content, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.title,
                request.source_name,
                request.source_type,
                request.equipment_type,
                request.equipment_model,
                request.fault_type,
                request.section_reference,
                request.page_reference,
                request.content,
                "published",
                now,
                now,
            ),
        )
        document_id = int(cur.lastrowid)

        for chunk_index, payload in enumerate(chunk_payloads, start=1):
            cur.execute(
                """
                INSERT INTO knowledge_chunks
                    (document_id, chunk_index, heading, content, equipment_type, equipment_model,
                     fault_type, section_reference, page_reference, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    chunk_index,
                    payload.get("heading") or request.title,
                    payload.get("content") or "",
                    payload.get("equipment_type") or request.equipment_type,
                    payload.get("equipment_model") or request.equipment_model,
                    payload.get("fault_type") or request.fault_type,
                    payload.get("section_reference") or request.section_reference,
                    payload.get("page_reference") or request.page_reference,
                    now,
                ),
            )

        conn.commit()
        return document_id, len(chunk_payloads)
    finally:
        conn.close()


def resolve_sqlite_path(database_url: str) -> Path:
    """Resolve file path from sqlite+aiosqlite URL."""
    prefix = "sqlite+aiosqlite:///"
    raw_path = database_url.removeprefix(prefix)
    path = Path(raw_path)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def utcnow_string() -> str:
    """Return a naive UTC timestamp string compatible with current tables."""
    return datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S.%f")


def build_parser() -> argparse.ArgumentParser:
    """Create CLI parser."""
    parser = argparse.ArgumentParser(description="将 PDF 维修手册导入知识库")
    parser.add_argument("pdf_path", help="PDF 文件路径")
    parser.add_argument("--title", help="知识文档标题，默认使用 PDF 文件名")
    parser.add_argument("--equipment-type", required=True, help="设备类型，例如 摩托车发动机")
    parser.add_argument("--equipment-model", help="设备型号，例如 LX200")
    parser.add_argument("--fault-type", help="故障类型，可选")
    parser.add_argument(
        "--source-type",
        default="manual",
        help="知识来源类型，默认 manual",
    )
    parser.add_argument("--section-reference", help="章节说明，可选")
    parser.add_argument(
        "--max-chars",
        type=int,
        default=480,
        help="单个知识分段最大字符数，默认 480",
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="若存在同名来源文档，则先删除旧文档再导入",
    )
    return parser


def main() -> None:
    """CLI entry."""
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(import_pdf(args))


if __name__ == "__main__":
    main()
