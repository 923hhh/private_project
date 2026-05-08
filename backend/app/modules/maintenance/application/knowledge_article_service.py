"""Knowledge-article operations for maintenance."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.maintenance import Annotation, AuthUser, KnowledgeArticle
from app.db.models.knowledge import KnowledgeDocument, KnowledgeRelation
from app.modules.knowledge.application.search_service import KnowledgeService
from app.modules.knowledge.schemas.search import KnowledgeDocumentCreate
from app.modules.maintenance.application.work_order_service import MaintenanceWorkOrderService
from app.modules.maintenance.datetime_util import to_iso_cn, utc_now_naive
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

    async def _load_user_name_map(self, user_ids: set[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        rows = (
            await self.session.execute(
                select(AuthUser.id, AuthUser.display_name).where(AuthUser.id.in_(user_ids))
            )
        ).all()
        return {user_id: display_name for user_id, display_name in rows}

    async def _load_document_map(self, article_ids: set[int]) -> dict[int, KnowledgeDocument]:
        if not article_ids:
            return {}
        relations = (
            await self.session.execute(
                select(KnowledgeRelation).where(
                    KnowledgeRelation.source_kind == "knowledge_article",
                    KnowledgeRelation.target_kind == "knowledge_document",
                    KnowledgeRelation.relation_type == "published_into",
                    KnowledgeRelation.source_id.in_(article_ids),
                )
            )
        ).scalars().all()
        relation_map = {
            relation.source_id: relation.target_id
            for relation in relations
        }
        document_ids = {document_id for document_id in relation_map.values() if document_id is not None}
        if not document_ids:
            return {}
        documents = (
            await self.session.execute(
                select(KnowledgeDocument).where(KnowledgeDocument.id.in_(document_ids))
            )
        ).scalars().all()
        documents_by_id = {document.id: document for document in documents}
        return {
            article_id: documents_by_id[document_id]
            for article_id, document_id in relation_map.items()
            if document_id in documents_by_id
        }

    async def _serialize_articles(self, articles: list[KnowledgeArticle]) -> list[dict[str, Any]]:
        if not articles:
            return []
        user_ids = {
            user_id
            for article in articles
            for user_id in (
                article.reviewer_expert_user_id,
                article.publisher_admin_user_id,
            )
            if user_id is not None
        }
        user_name_map = await self._load_user_name_map(user_ids)
        document_map = await self._load_document_map({article.id for article in articles})
        return [
            self._serialize_article(article, user_name_map=user_name_map, document=document_map.get(article.id))
            for article in articles
        ]

    def _serialize_article(
        self,
        article: KnowledgeArticle,
        *,
        user_name_map: dict[int, str],
        document: KnowledgeDocument | None,
    ) -> dict[str, Any]:
        retrieval_indexed = (
            article.status == "published"
            and document is not None
            and document.status == "published"
        )
        if retrieval_indexed:
            retrieval_status_label = "已进入检索库"
        elif article.status == "withdrawn":
            retrieval_status_label = "已移出检索库"
        elif article.status == "published":
            retrieval_status_label = "未进入检索库"
        else:
            retrieval_status_label = "未发布"
        body_excerpt = (article.body or "").strip().splitlines()[0][:180] if (article.body or "").strip() else None
        return {
            "id": article.id,
            "series_id": article.series_id,
            "title": article.title,
            "body": article.body,
            "body_excerpt": body_excerpt,
            "status": article.status,
            "version": article.version,
            "source_work_order_id": article.source_work_order_id,
            "reviewer_expert_user_id": article.reviewer_expert_user_id,
            "reviewed_by_name": user_name_map.get(article.reviewer_expert_user_id or 0),
            "publisher_admin_user_id": article.publisher_admin_user_id,
            "published_by_name": user_name_map.get(article.publisher_admin_user_id or 0),
            "published_at": to_iso_cn(article.published_at),
            "created_at": to_iso_cn(article.created_at),
            "updated_at": to_iso_cn(article.updated_at),
            "retrieval_indexed": retrieval_indexed,
            "retrieval_status_label": retrieval_status_label,
            "retrieval_document_id": document.id if document is not None else None,
            "retrieval_document_status": document.status if document is not None else None,
        }

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
            created_at=utc_now_naive(),
            updated_at=utc_now_naive(),
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
            created_at=utc_now_naive(),
            updated_at=utc_now_naive(),
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
        series_id: int | None = None,
    ) -> dict[str, Any]:
        stmt = select(KnowledgeArticle)
        if status:
            stmt = stmt.where(KnowledgeArticle.status == status)
        if series_id is not None:
            stmt = stmt.where(KnowledgeArticle.series_id == series_id)
        if not ctx.has_any("admin", "expert"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "无权查看知识列表")
        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (
            await self.session.execute(
                stmt.order_by(KnowledgeArticle.id.desc()).offset((page - 1) * page_size).limit(page_size)
            )
        ).scalars().all()
        items = await self._serialize_articles(list(rows))
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def get_publish_console(self, ctx: CurrentUserCtx) -> dict[str, Any]:
        if not ctx.has_any("admin", "expert"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "无权查看知识发布台")
        pending_rows = (
            await self.session.execute(
                select(KnowledgeArticle)
                .where(KnowledgeArticle.status == "pending_publish")
                .order_by(KnowledgeArticle.updated_at.desc(), KnowledgeArticle.id.desc())
            )
        ).scalars().all()
        published_rows = (
            await self.session.execute(
                select(KnowledgeArticle)
                .where(KnowledgeArticle.status == "published")
                .order_by(KnowledgeArticle.series_id.asc(), KnowledgeArticle.version.desc(), KnowledgeArticle.id.desc())
            )
        ).scalars().all()
        version_rows = (
            await self.session.execute(
                select(KnowledgeArticle)
                .order_by(KnowledgeArticle.updated_at.desc(), KnowledgeArticle.id.desc())
                .limit(18)
            )
        ).scalars().all()

        current_effective_rows: list[KnowledgeArticle] = []
        seen_series_ids: set[int] = set()
        for article in published_rows:
            if article.series_id in seen_series_ids:
                continue
            seen_series_ids.add(article.series_id)
            current_effective_rows.append(article)

        withdrawn_count = (
            await self.session.execute(
                select(func.count()).select_from(
                    select(KnowledgeArticle.id).where(KnowledgeArticle.status == "withdrawn").subquery()
                )
            )
        ).scalar_one()

        pending_items = await self._serialize_articles(list(pending_rows))
        current_effective_items = await self._serialize_articles(current_effective_rows)
        recent_versions = await self._serialize_articles(list(version_rows))
        retrieval_enabled_count = sum(1 for item in current_effective_items if item["retrieval_indexed"])

        return {
            "summary": {
                "pending_publish_count": len(pending_items),
                "current_effective_count": len(current_effective_items),
                "withdrawn_count": int(withdrawn_count or 0),
                "retrieval_enabled_count": retrieval_enabled_count,
            },
            "pending_publish_items": pending_items,
            "current_effective_items": current_effective_items,
            "recent_version_records": recent_versions,
        }

    async def get_article_versions(self, article_id: int, ctx: CurrentUserCtx) -> dict[str, Any]:
        if not ctx.has_any("admin", "expert"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "无权查看版本记录")
        article = await self.session.get(KnowledgeArticle, article_id)
        if article is None:
            raise MaintenanceAPIError(404, "NOT_FOUND", "条目不存在")
        rows = (
            await self.session.execute(
                select(KnowledgeArticle)
                .where(KnowledgeArticle.series_id == article.series_id)
                .order_by(KnowledgeArticle.version.desc(), KnowledgeArticle.id.desc())
            )
        ).scalars().all()
        items = await self._serialize_articles(list(rows))
        return {
            "article_id": article.id,
            "series_id": article.series_id,
            "items": items,
        }

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
        article.updated_at = utc_now_naive()
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
        from app.services import cache_service

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
            article.published_at = utc_now_naive()
            article.updated_at = utc_now_naive()

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
            cache_service.clear()
        except IntegrityError:
            await self.session.rollback()
            raise MaintenanceAPIError(409, "SERIES_PUBLISHED_CONFLICT", "同系列已存在已发布版本") from None
        items = await self._serialize_articles([article])
        return items[0]

    async def withdraw_kb(self, article_id: int, ctx: CurrentUserCtx) -> dict[str, Any]:
        from app.services import cache_service

        if not ctx.has_any("admin"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "仅管理员可撤回")
        article = await self.session.get(KnowledgeArticle, article_id)
        if article is None:
            raise MaintenanceAPIError(404, "NOT_FOUND", "条目不存在")
        if article.status != "published":
            raise MaintenanceAPIError(409, "INVALID_STATE_TRANSITION", "当前状态不可撤回")

        document_map = await self._load_document_map({article.id})
        document = document_map.get(article.id)
        article.status = "withdrawn"
        article.updated_at = utc_now_naive()
        if document is not None:
            document.status = "withdrawn"
            document.updated_at = utc_now_naive()

        await self._audit(
            "kb.withdraw",
            "knowledge_article",
            str(article.id),
            ctx.user_id,
            {"series_id": article.series_id, "document_id": document.id if document is not None else None},
            None,
        )
        await self.session.commit()
        cache_service.clear()
        items = await self._serialize_articles([article])
        return items[0]
