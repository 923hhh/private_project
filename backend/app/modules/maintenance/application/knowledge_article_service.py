"""Knowledge-article operations for maintenance."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.maintenance import Annotation, KnowledgeArticle
from app.db.models.knowledge import KnowledgeRelation
from app.modules.knowledge.application.search_service import KnowledgeService
from app.modules.knowledge.schemas.search import KnowledgeDocumentCreate
from app.modules.maintenance.application.work_order_service import MaintenanceWorkOrderService
from app.modules.maintenance.datetime_util import to_iso_cn
from app.modules.maintenance.deps import CurrentUserCtx
from app.modules.maintenance.errors import MaintenanceAPIError

AuditCallback = Callable[[str, str, str, int | None, dict | None, str | None], Awaitable[None]]


class MaintenanceKnowledgeArticleService:
    """Knowledge draft, review, and publish operations."""

    def __init__(
        self,
        session: AsyncSession,
        audit: AuditCallback,
        work_order_service: MaintenanceWorkOrderService,
    ) -> None:
        self.session = session
        self._audit = audit
        self.work_order_service = work_order_service

    async def spawn_kb_draft(
        self,
        annotation_id: int,
        body: dict[str, Any],
        ctx: CurrentUserCtx,
    ) -> dict[str, Any]:
        if not ctx.has_any("expert", "admin"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "仅专家可操作")
        annotation = await self.session.get(Annotation, annotation_id)
        if annotation is None:
            raise MaintenanceAPIError(404, "NOT_FOUND", "标注不存在")
        if annotation.candidate_kb_patch_id:
            return {
                "knowledge_article_id": annotation.candidate_kb_patch_id,
                "status": "draft",
                "source_annotation_id": annotation.id,
                "business_code": "ALREADY_PROCESSED",
            }
        title = (body or {}).get("title_hint") or "知识修订草稿"
        article = KnowledgeArticle(
            series_id=0,
            title=title,
            body="（由标注生成的草稿，请专家完善）",
            status="draft",
            version=1,
            source_work_order_id=annotation.work_order_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.session.add(article)
        await self.session.flush()
        article.series_id = article.id
        annotation.candidate_kb_patch_id = article.id
        await self.session.commit()
        return {
            "knowledge_article_id": article.id,
            "status": "draft",
            "source_annotation_id": annotation.id,
        }

    async def kb_from_work_order(self, body: dict[str, Any], ctx: CurrentUserCtx) -> dict[str, Any]:
        if not ctx.has_any("expert", "admin"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "权限不足")
        work_order = await self.work_order_service.get_work_order(int(body["work_order_id"]))
        if work_order.status != "S10":
            raise MaintenanceAPIError(409, "INVALID_STATE_TRANSITION", "工单须已结单")
        article = KnowledgeArticle(
            series_id=0,
            title=body.get("title") or f"工单{work_order.id}沉淀",
            body=body.get("body") or "待完善",
            status="draft",
            version=1,
            source_work_order_id=work_order.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.session.add(article)
        await self.session.flush()
        article.series_id = article.id
        await self.session.commit()
        return {"id": article.id, "status": article.status, "series_id": article.series_id}

    async def list_kb_articles(
        self,
        ctx: CurrentUserCtx,
        status: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        stmt = select(KnowledgeArticle)
        if status:
            stmt = stmt.where(KnowledgeArticle.status == status)
        if not ctx.has_any("admin", "expert"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "无权查看知识列表")
        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (
            await self.session.execute(
                stmt.order_by(KnowledgeArticle.id.desc()).offset((page - 1) * page_size).limit(page_size)
            )
        ).scalars().all()
        items = [
            {
                "id": article.id,
                "series_id": article.series_id,
                "title": article.title,
                "status": article.status,
                "version": article.version,
            }
            for article in rows
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def review_kb(self, article_id: int, body: dict[str, Any], ctx: CurrentUserCtx) -> dict[str, Any]:
        if not ctx.has_any("expert"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "仅专家可审核")
        article = await self.session.get(KnowledgeArticle, article_id)
        if article is None:
            raise MaintenanceAPIError(404, "NOT_FOUND", "条目不存在")
        if article.status not in ("pending_review", "draft"):
            raise MaintenanceAPIError(409, "INVALID_STATE_TRANSITION", "状态不允许审核")
        action = body["action"]
        if action == "reject" and not (body.get("comment") or "").strip():
            raise MaintenanceAPIError(400, "VALIDATION_ERROR", "驳回须填写意见")
        if action == "request_revise" and not (body.get("comment") or "").strip():
            raise MaintenanceAPIError(400, "VALIDATION_ERROR", "须填写修订说明")
        if action == "approve":
            article.status = "pending_publish"
        elif action == "reject":
            article.status = "rejected_review"
        else:
            article.status = "pending_review"
        article.reviewer_expert_user_id = ctx.user_id
        article.updated_at = datetime.now(timezone.utc)
        await self._audit(
            "kb.review",
            "knowledge_article",
            str(article.id),
            ctx.user_id,
            {"action": action},
            None,
        )
        await self.session.commit()
        return {"id": article.id, "status": article.status, "reviewed_at": to_iso_cn(article.updated_at)}

    async def publish_kb(
        self,
        article_id: int,
        body: dict[str, Any] | None,
        ctx: CurrentUserCtx,
    ) -> dict[str, Any]:
        if not ctx.has_any("admin"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "仅管理员可发布")
        article = await self.session.get(KnowledgeArticle, article_id)
        if article is None:
            raise MaintenanceAPIError(404, "NOT_FOUND", "条目不存在")
        if article.status not in ("pending_publish",):
            raise MaintenanceAPIError(409, "INVALID_STATE_TRANSITION", "当前状态不可发布")
        try:
            article.status = "published"
            article.publisher_admin_user_id = ctx.user_id
            article.published_at = datetime.now(timezone.utc)
            article.updated_at = datetime.now(timezone.utc)

            doc_body = (article.body or "").strip()
            if len(doc_body) >= 20 and doc_body != "待完善":
                doc_create = KnowledgeDocumentCreate(
                    title=article.title or f"知识文章 #{article.id}",
                    source_name=f"kb-article-{article.id}",
                    source_type="expert",
                    equipment_type="通用设备",
                    content=doc_body,
                )
                knowledge_service = KnowledgeService(self.session)
                document, _ = await knowledge_service.create_document(doc_create)
                self.session.add(
                    KnowledgeRelation(
                        source_kind="knowledge_article",
                        source_id=article.id,
                        target_kind="knowledge_document",
                        target_id=document.id,
                        relation_type="published_into",
                        notes="知识文章发布后自动沉淀为知识文档",
                    )
                )

            await self._audit(
                "kb.publish",
                "knowledge_article",
                str(article.id),
                ctx.user_id,
                {"series_id": article.series_id},
                None,
            )
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise MaintenanceAPIError(409, "SERIES_PUBLISHED_CONFLICT", "同系列已存在已发布版本") from None
        return {
            "id": article.id,
            "status": article.status,
            "series_id": article.series_id,
            "published_at": to_iso_cn(article.published_at),
        }
