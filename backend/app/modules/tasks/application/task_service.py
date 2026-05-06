"""Maintenance task workflow service."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.knowledge import KnowledgeChunk, KnowledgeDocument, KnowledgeRelation
from app.db.models.tasks import (
    MaintenanceTask,
    MaintenanceTaskStep,
    MaintenanceTaskTemplate,
    MaintenanceTaskTemplateStep,
)
from app.modules.knowledge.application.search_service import KnowledgeService
from app.modules.knowledge.schemas.search import KnowledgeSearchRequest
from app.modules.tasks.schemas import MaintenanceTaskCreate, MaintenanceTaskStepUpdate
from app.modules.diagnosis.application.report_formatter import build_structured_diagnosis
from app.services.knowledge_query_rewrite import analyze_procedural_query
from app.services.maintenance_safety_service import MaintenanceSafetyService


DEFAULT_TEMPLATE_CATALOG: dict[str, dict[str, dict[str, Any]]] = {
    "摩托车发动机": {
        "routine": {
            "name": "摩托车发动机例行检修流程",
            "description": "适用于已知故障现象下的例行排查和基础检修。",
            "steps": [
                {
                    "title": "检修前安全确认",
                    "instruction_template": "确认 {equipment_type}{equipment_model_suffix} 已熄火、断电并完成基础安全隔离，再开始例行检修。",
                    "risk_warning": "严禁在发动机仍处于运行或高温状态时直接拆检。",
                    "caution": "检查工位通风、照明、防护手套和工具绝缘状态。",
                    "confirmation_text": "已完成检修前安全确认",
                },
                {
                    "title": "确认故障现象与外观状态",
                    "instruction_template": "根据当前故障现象“{symptom_text}”确认异常部件范围，并核对外观、油污、松动和烧蚀痕迹。",
                    "risk_warning": "若发现明显烧蚀、漏油或破损，应立即停止后续通电测试。",
                    "caution": "对照已命中的知识来源逐项记录可见异常，避免直接跳步。",
                    "confirmation_text": "已完成故障现象确认",
                },
                {
                    "title": "执行关键部件排查",
                    "instruction_template": "按知识条目建议优先排查点火、供油、进排气和紧固状态，重点核验与“{fault_type_text}”相关的核心部件。",
                    "risk_warning": "拆装点火和供油部件时必须防止短路、误喷油和异物进入缸体。",
                    "caution": "每完成一项检测后记录结论，必要时拍照留档。",
                    "confirmation_text": "已完成关键部件排查",
                },
                {
                    "title": "实施维修与复装",
                    "instruction_template": "依据知识来源中的标准步骤完成维修、清洁、调整和复装，并同步复核扭矩、间隙和接插件状态。",
                    "risk_warning": "维修过程中若出现超出标准步骤的异常，应先停止并升级处理。",
                    "caution": "复装后再次核对零件方向、紧固件数量和连接可靠性。",
                    "confirmation_text": "已完成维修与复装",
                },
                {
                    "title": "试车复核与结果归档",
                    "instruction_template": "进行试车或空载验证，确认故障现象是否消失，并将本次检修结果、引用知识和备注归档。",
                    "risk_warning": "试车阶段需确保周边无人员干扰，防止二次风险。",
                    "caution": "若故障未解除，应重新回看知识来源并标记待补充案例。",
                    "confirmation_text": "已完成试车复核与归档",
                },
            ],
        },
        "standard": {
            "name": "摩托车发动机标准检修流程",
            "description": "适用于较完整的标准化检修闭环。",
            "steps": [
                {
                    "title": "检修前安全隔离",
                    "instruction_template": "确认 {equipment_type}{equipment_model_suffix} 完成停机、断电、燃油风险隔离和工位安全确认。",
                    "risk_warning": "未完成安全隔离前不得拆检点火、供油和高温部件。",
                    "caution": "准备防护手套、绝缘工具、记录表和引用知识清单。",
                    "confirmation_text": "已完成检修前安全隔离",
                },
                {
                    "title": "故障现象与知识来源核对",
                    "instruction_template": "围绕“{symptom_text}”核对现场表现，并对照已选知识来源确认优先排查对象和标准步骤。",
                    "risk_warning": "若现场现象与知识条目冲突，应先记录差异，避免照搬结论。",
                    "caution": "记录本次检修引用的文档、章节和页码，便于后续复核。",
                    "confirmation_text": "已完成故障现象与知识来源核对",
                },
                {
                    "title": "关键部件逐项排查",
                    "instruction_template": "按照知识条目推荐顺序排查点火系统、火花塞、供油、压缩和紧固状态，重点关注“{fault_type_text}”对应部位。",
                    "risk_warning": "排查过程中若发现明显高温、漏油或破损，应暂停并升级为应急流程。",
                    "caution": "每排查一个部件都记录结果，不要只记录最终结论。",
                    "confirmation_text": "已完成关键部件逐项排查",
                },
                {
                    "title": "实施维修与参数复核",
                    "instruction_template": "依据知识来源中的检修步骤完成清洁、替换、调校和复装，并核对关键参数是否恢复到标准范围。",
                    "risk_warning": "未经验证的替代方案不得直接用于正式复装。",
                    "caution": "复装后再次检查连接可靠性、扭矩和零件方向。",
                    "confirmation_text": "已完成维修与参数复核",
                },
                {
                    "title": "试车验证与结果确认",
                    "instruction_template": "执行试车或功能验证，确认“{symptom_text}”是否消失，并形成最终检修结论。",
                    "risk_warning": "试车阶段需严格控制现场环境，防止误操作。",
                    "caution": "若问题仍存在，保留本轮结果并转入知识沉淀或升级处理。",
                    "confirmation_text": "已完成试车验证与结果确认",
                },
                {
                    "title": "结果归档与经验沉淀",
                    "instruction_template": "整理本次检修步骤、引用知识、执行结论和改进建议，为后续案例沉淀和审核做准备。",
                    "risk_warning": "归档信息缺失会影响后续复盘和知识复用。",
                    "caution": "确保导出内容包含引用文档和关键备注。",
                    "confirmation_text": "已完成结果归档与经验沉淀",
                },
            ],
        },
        "emergency": {
            "name": "摩托车发动机应急检修流程",
            "description": "适用于需要先隔离风险再恢复设备的应急场景。",
            "steps": [
                {
                    "title": "立即隔离风险源",
                    "instruction_template": "立即对 {equipment_type}{equipment_model_suffix} 执行停机、断电和危险源隔离，防止故障扩大。",
                    "risk_warning": "未完成隔离前严禁继续运行设备。",
                    "caution": "同步通知现场负责人并记录应急启动时间。",
                    "confirmation_text": "已完成风险源隔离",
                },
                {
                    "title": "快速定位关键异常",
                    "instruction_template": "结合“{symptom_text}”和已选知识来源快速定位高优先级部件，确认是否存在烧蚀、泄漏或卡滞。",
                    "risk_warning": "若存在明显机械破损，应立即停止进一步试验。",
                    "caution": "优先检查对安全影响最大的部位。",
                    "confirmation_text": "已完成关键异常定位",
                },
                {
                    "title": "实施应急处理",
                    "instruction_template": "按标准化应急步骤处理核心故障点，仅执行知识来源已覆盖且风险可控的维修动作。",
                    "risk_warning": "禁止在应急模式下尝试未验证的新方案。",
                    "caution": "保留所有应急处理记录，便于事后复盘。",
                    "confirmation_text": "已完成应急处理",
                },
                {
                    "title": "恢复验证与升级判断",
                    "instruction_template": "验证故障是否解除；若未恢复或存在反复迹象，立即升级为深度检修或专家会诊。",
                    "risk_warning": "故障未清除前不得贸然恢复长期运行。",
                    "caution": "记录是否需要后续标准检修或案例沉淀。",
                    "confirmation_text": "已完成恢复验证与升级判断",
                },
            ],
        },
    }
}


GENERIC_TEMPLATE_CATALOG = {
    "routine": DEFAULT_TEMPLATE_CATALOG["摩托车发动机"]["routine"],
    "standard": DEFAULT_TEMPLATE_CATALOG["摩托车发动机"]["standard"],
    "emergency": DEFAULT_TEMPLATE_CATALOG["摩托车发动机"]["emergency"],
}


STEP_RESOURCE_HINTS: dict[str, dict[str, Any]] = {
    "检修前安全确认": {
        "required_tools": ["绝缘手套", "防护眼镜", "工位照明灯"],
        "required_materials": ["停机挂牌", "检修记录表"],
        "estimated_minutes": 8,
    },
    "确认故障现象与外观状态": {
        "required_tools": ["手电筒", "观察镜", "拍照终端"],
        "required_materials": ["现场点检表"],
        "estimated_minutes": 12,
    },
    "执行关键部件排查": {
        "required_tools": ["火花塞套筒", "万用表", "扭矩扳手"],
        "required_materials": ["清洁布", "检修记录卡"],
        "estimated_minutes": 20,
    },
    "实施维修与复装": {
        "required_tools": ["套筒工具组", "扭矩扳手", "间隙尺"],
        "required_materials": ["清洗剂", "润滑脂", "替换零件"],
        "estimated_minutes": 25,
    },
    "试车复核与结果归档": {
        "required_tools": ["试车检测表", "拍照终端"],
        "required_materials": ["结果归档单"],
        "estimated_minutes": 15,
    },
    "检修前安全隔离": {
        "required_tools": ["绝缘手套", "防护眼镜", "隔离挂牌"],
        "required_materials": ["停机挂牌", "安全确认单"],
        "estimated_minutes": 10,
    },
    "故障现象与知识来源核对": {
        "required_tools": ["知识引用清单", "手电筒", "拍照终端"],
        "required_materials": ["故障复核表"],
        "estimated_minutes": 12,
    },
    "关键部件逐项排查": {
        "required_tools": ["火花塞套筒", "万用表", "压缩压力表"],
        "required_materials": ["检修记录卡", "清洁布"],
        "estimated_minutes": 25,
    },
    "实施维修与参数复核": {
        "required_tools": ["扭矩扳手", "套筒工具组", "间隙尺"],
        "required_materials": ["替换零件", "润滑脂", "清洗剂"],
        "estimated_minutes": 30,
    },
    "试车验证与结果确认": {
        "required_tools": ["试车检测表", "拍照终端"],
        "required_materials": ["结果确认单"],
        "estimated_minutes": 18,
    },
    "结果归档与经验沉淀": {
        "required_tools": ["归档终端", "引用清单"],
        "required_materials": ["案例沉淀表", "导出摘要"],
        "estimated_minutes": 10,
    },
    "立即隔离风险源": {
        "required_tools": ["绝缘手套", "急停装置", "隔离挂牌"],
        "required_materials": ["应急处置单"],
        "estimated_minutes": 6,
    },
    "快速定位关键异常": {
        "required_tools": ["手电筒", "万用表", "观察镜"],
        "required_materials": ["异常记录表"],
        "estimated_minutes": 10,
    },
    "实施应急处理": {
        "required_tools": ["套筒工具组", "扭矩扳手", "万用表"],
        "required_materials": ["应急替换件", "清洗剂"],
        "estimated_minutes": 18,
    },
    "恢复验证与升级判断": {
        "required_tools": ["试车检测表", "拍照终端"],
        "required_materials": ["升级判断单"],
        "estimated_minutes": 12,
    },
}


class MaintenanceTaskService:
    """Service layer for standardized maintenance workflow."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _json_safe_snapshot(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): MaintenanceTaskService._json_safe_snapshot(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [MaintenanceTaskService._json_safe_snapshot(item) for item in value]
        return value

    async def create_task(self, data: MaintenanceTaskCreate) -> dict[str, Any]:
        """Create a task, runtime steps and task-to-knowledge relations."""
        template: MaintenanceTaskTemplate | None = None
        for attempt in range(3):
            try:
                template = await self._ensure_template(
                    equipment_type=data.equipment_type,
                    maintenance_level=data.maintenance_level,
                )
                break
            except OperationalError as exc:
                if "database is locked" not in str(exc).lower() or attempt >= 2:
                    raise
                await self.session.rollback()
                await asyncio.sleep(0.2 * (attempt + 1))
        if template is None:
            raise RuntimeError("检修模板加载失败，请稍后重试。")
        knowledge_refs = self._json_safe_snapshot(await self._load_knowledge_refs(data.source_chunk_ids))

        task = MaintenanceTask(
            title=data.title or self._build_task_title(data),
            work_order_id=data.work_order_id,
            asset_code=data.asset_code,
            report_source=data.report_source,
            priority=data.priority or "medium",
            equipment_type=data.equipment_type,
            equipment_model=data.equipment_model,
            maintenance_level=data.maintenance_level,
            fault_type=data.fault_type,
            symptom_description=data.symptom_description,
            status="pending",
            template_id=template.id,
            source_chunk_ids=list(data.source_chunk_ids),
            source_snapshot=knowledge_refs,
            advice_card=self._build_advice_card(data, knowledge_refs),
        )
        self.session.add(task)
        await self.session.flush()

        for template_step in template.steps:
            task_step = MaintenanceTaskStep(
                task_id=task.id,
                template_step_id=template_step.id,
                step_order=template_step.step_order,
                title=template_step.title,
                instruction=self._render_instruction(
                    template_step.instruction_template,
                    data,
                    knowledge_refs,
                ),
                risk_warning=template_step.risk_warning,
                caution=template_step.caution,
                confirmation_text=template_step.confirmation_text,
                required_tools=self._normalize_step_items(template_step.required_tools),
                required_materials=self._normalize_step_items(template_step.required_materials),
                estimated_minutes=template_step.estimated_minutes,
                status="pending",
                knowledge_refs=knowledge_refs,
            )
            self.session.add(task_step)

        for chunk_id in data.source_chunk_ids:
            self.session.add(
                KnowledgeRelation(
                    source_kind="maintenance_task",
                    source_id=task.id,
                    target_kind="knowledge_chunk",
                    target_id=chunk_id,
                    relation_type="cites",
                    notes="标准化作业任务引用知识条目",
                )
            )

        await self.session.commit()
        return await self.get_task_detail(task.id)

    async def update_task_step(
        self,
        task_id: int,
        step_id: int,
        data: MaintenanceTaskStepUpdate,
    ) -> dict[str, Any]:
        """Update task step status and sync parent task status."""
        step_stmt = select(MaintenanceTaskStep).where(
            MaintenanceTaskStep.id == step_id,
            MaintenanceTaskStep.task_id == task_id,
        )
        step = (await self.session.execute(step_stmt)).scalar_one_or_none()
        if step is None:
            raise ValueError("指定的检修步骤不存在。")

        step.status = data.status
        step.completion_note = data.completion_note
        step.completed_at = datetime.now(timezone.utc) if data.status in {"completed", "skipped"} else None

        task_stmt = (
            select(MaintenanceTask)
            .options(selectinload(MaintenanceTask.steps))
            .where(MaintenanceTask.id == task_id)
        )
        task = (await self.session.execute(task_stmt)).scalar_one_or_none()
        if task is None:
            raise ValueError("指定的检修任务不存在。")

        task_statuses = {item.status for item in task.steps}
        if task_statuses and task_statuses.issubset({"completed", "skipped"}):
            task.status = "completed"
        elif "in_progress" in task_statuses or "completed" in task_statuses or "skipped" in task_statuses:
            task.status = "in_progress"
        else:
            task.status = "pending"

        await self.session.commit()
        return await self.get_task_detail(task_id)

    async def complete_task_after_pipeline_success(self, task_id: int) -> None:
        """协作/诊断流水线成功结束后，将任务及全部未完成步骤标记为已完成。"""
        stmt = (
            select(MaintenanceTask)
            .options(selectinload(MaintenanceTask.steps))
            .where(MaintenanceTask.id == task_id)
        )
        task = (await self.session.execute(stmt)).scalar_one_or_none()
        if task is None or task.status == "completed":
            return
        now = datetime.now(timezone.utc)
        for step in task.steps:
            if step.status not in {"completed", "skipped"}:
                step.status = "completed"
                step.completed_at = now
        task.status = "completed"
        await self.session.commit()

    async def get_task_detail(self, task_id: int) -> dict[str, Any]:
        """Return a fully expanded task detail payload."""
        stmt = (
            select(MaintenanceTask)
            .options(selectinload(MaintenanceTask.steps))
            .where(MaintenanceTask.id == task_id)
        )
        task = (await self.session.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise ValueError("指定的检修任务不存在。")

        source_refs = list(task.source_snapshot or [])
        symptom_text = task.symptom_description or task.fault_type or task.title or ""
        procedural_query = analyze_procedural_query(symptom_text).is_procedural
        if procedural_query or len(source_refs) < 3:
            try:
                payload = await KnowledgeService(self.session).search_multimodal(
                    KnowledgeSearchRequest(
                        query=symptom_text,
                        equipment_type=task.equipment_type,
                        equipment_model=task.equipment_model,
                        fault_type=task.fault_type,
                        limit=5,
                    )
                )
                extra_refs = payload.get("results") or []
                if extra_refs:
                    source_refs = extra_refs[:5]
            except Exception:
                pass
        timeline_payload = list(task.execution_timeline or [])
        if not timeline_payload:
            timeline_payload = self._build_minimal_timeline(task)
        steps_payload = [self._serialize_step(step, task) for step in task.steps]
        derived_steps = self._derive_step_runtime_states(steps_payload, timeline_payload)
        diagnosis_ready = self._has_final_diagnosis(task)
        completed_steps = sum(1 for step in derived_steps if step["status"] == "completed")
        normalized_status = "completed" if diagnosis_ready else task.status
        run_started_at, run_finished_at = self._extract_runtime_window(timeline_payload)

        return {
            "id": task.id,
            "title": task.title,
            "work_order_id": task.work_order_id,
            "asset_code": task.asset_code,
            "report_source": task.report_source,
            "priority": task.priority,
            "equipment_type": task.equipment_type,
            "equipment_model": task.equipment_model,
            "maintenance_level": task.maintenance_level,
            "fault_type": task.fault_type,
            "symptom_description": task.symptom_description,
            "status": normalized_status,
            "advice_card": task.advice_card,
            "diagnosis_report": task.diagnosis_report,
            "diagnosis_structured": build_structured_diagnosis(
                diagnosis_report=task.diagnosis_report,
                advice_card=task.advice_card,
                retrieval_results=source_refs,
                maintenance_level=task.maintenance_level,
                symptom_description=symptom_text,
                work_order_ready=bool(task.asset_code),
            ).model_dump(),
            "execution_timeline": timeline_payload,
            "total_steps": len(task.steps),
            "completed_steps": completed_steps,
            "source_refs": source_refs,
            "steps": derived_steps,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "run_started_at": run_started_at,
            "run_finished_at": run_finished_at,
        }

    async def list_history(
        self,
        *,
        limit: int = 20,
        status_filter: str | None = None,
        priority_filter: str | None = None,
        work_order_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return recent task history."""
        stmt = (
            select(MaintenanceTask)
            .options(selectinload(MaintenanceTask.steps))
            .order_by(MaintenanceTask.updated_at.desc())
            .limit(limit)
        )
        if status_filter:
            stmt = stmt.where(MaintenanceTask.status == status_filter)
        if priority_filter:
            stmt = stmt.where(MaintenanceTask.priority == priority_filter)
        if work_order_id:
            stmt = stmt.where(MaintenanceTask.work_order_id.ilike(f"%{work_order_id.strip()}%"))
        tasks = (await self.session.execute(stmt)).scalars().all()
        return [
            {
                "id": task.id,
                "title": task.title,
                "work_order_id": task.work_order_id,
                "asset_code": task.asset_code,
                "report_source": task.report_source,
                "priority": task.priority,
                "equipment_type": task.equipment_type,
                "equipment_model": task.equipment_model,
                "maintenance_level": task.maintenance_level,
                "status": "completed" if self._has_final_diagnosis(task) else task.status,
                "total_steps": len(task.steps),
                "completed_steps": (
                    len(task.steps)
                    if self._has_final_diagnosis(task)
                    else sum(1 for step in task.steps if step.status == "completed")
                ),
                "created_at": task.created_at,
                "updated_at": task.updated_at,
                "run_started_at": self._extract_runtime_window(
                    getattr(task, "execution_timeline", None)
                )[0],
                "run_finished_at": self._extract_runtime_window(
                    getattr(task, "execution_timeline", None)
                )[1],
            }
            for task in tasks
        ]

    async def export_task(self, task_id: int) -> dict[str, Any]:
        """Build an export-friendly summary payload."""
        task = await self.get_task_detail(task_id)
        summary = self._build_export_summary(task)
        return {
            "task": task,
            "exported_at": datetime.now(timezone.utc),
            "export_summary": summary,
        }

    async def delete_task(self, task_id: int) -> None:
        """Delete maintenance task and related citations."""
        stmt = select(MaintenanceTask).where(MaintenanceTask.id == task_id)
        task = (await self.session.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise ValueError("指定的检修任务不存在。")

        await self.session.execute(
            delete(KnowledgeRelation).where(
                KnowledgeRelation.source_kind == "maintenance_task",
                KnowledgeRelation.source_id == task_id,
            )
        )
        await self.session.delete(task)
        await self.session.commit()

    async def reset_task_for_retry(self, task_id: int) -> dict[str, Any]:
        """Clear persisted diagnosis artifacts and reopen the task for a fresh rerun."""
        stmt = (
            select(MaintenanceTask)
            .options(selectinload(MaintenanceTask.steps))
            .where(MaintenanceTask.id == task_id)
        )
        task = (await self.session.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise ValueError("指定的检修任务不存在。")

        self._reset_task_runtime_state(task)

        await self.session.commit()
        return await self.get_task_detail(task_id)

    async def upsert_execution_timeline(
        self,
        task_id: int,
        events: list[dict[str, Any]],
        diagnosis_report: str | None = None,
    ) -> None:
        """Upsert execution timeline events for a maintenance task."""
        stmt = select(MaintenanceTask).where(MaintenanceTask.id == task_id)
        task = (await self.session.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise ValueError("指定的检修任务不存在。")
        task.execution_timeline = events
        if diagnosis_report is not None:
            normalized = diagnosis_report.strip()
            task.diagnosis_report = normalized or None
            if task.diagnosis_report:
                self._mark_task_completed_from_diagnosis(task)
            elif not events:
                self._reset_task_runtime_state(task, clear_timeline=False)
        elif events and task.status == "pending":
            task.status = "in_progress"
        await self.session.commit()

    async def append_execution_timeline_event(
        self,
        task_id: int,
        event: dict[str, Any],
        *,
        diagnosis_report: str | None = None,
    ) -> None:
        """Append a single execution event while keeping task runtime state in sync."""
        stmt = select(MaintenanceTask).where(MaintenanceTask.id == task_id)
        task = (await self.session.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise ValueError("指定的检修任务不存在。")

        timeline = list(task.execution_timeline or [])
        timeline.append(event)
        task.execution_timeline = timeline

        normalized = (diagnosis_report or "").strip()
        if normalized:
            task.diagnosis_report = normalized
            self._mark_task_completed_from_diagnosis(task)
        elif task.status == "pending":
            task.status = "in_progress"

        await self.session.commit()

    async def update_diagnosis_report(self, task_id: int, diagnosis_report: str | None) -> None:
        """Persist only the final diagnosis report for a maintenance task."""
        stmt = select(MaintenanceTask).where(MaintenanceTask.id == task_id)
        task = (await self.session.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise ValueError("指定的检修任务不存在。")
        normalized = (diagnosis_report or "").strip()
        task.diagnosis_report = normalized or None
        if task.diagnosis_report:
            self._mark_task_completed_from_diagnosis(task)
        await self.session.commit()

    async def update_diagnosis_context(
        self,
        task_id: int,
        *,
        diagnosis_report: str | None,
        source_chunk_ids: list[int],
        source_refs: list[dict[str, Any]],
    ) -> None:
        """Persist diagnosis report and the latest knowledge citation snapshot back to the task."""
        stmt = select(MaintenanceTask).where(MaintenanceTask.id == task_id)
        task = (await self.session.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise ValueError("指定的检修任务不存在。")
        normalized = (diagnosis_report or "").strip()
        task.diagnosis_report = normalized or None
        task.source_chunk_ids = list(source_chunk_ids)
        task.source_snapshot = self._json_safe_snapshot(list(source_refs))
        if task.diagnosis_report:
            self._mark_task_completed_from_diagnosis(task)
        await self.session.commit()

    def _mark_task_completed_from_diagnosis(self, task: MaintenanceTask) -> None:
        """Promote the parent task once a final diagnosis report is available."""
        task.status = "completed"

    def _reset_task_runtime_state(self, task: MaintenanceTask, *, clear_timeline: bool = True) -> None:
        task.diagnosis_report = None
        task.advice_card = None
        if clear_timeline:
            task.execution_timeline = []
        task.status = "pending"
        for step in task.steps:
            step.status = "pending"
            step.completion_note = None
            step.completed_at = None

    def _has_final_diagnosis(self, task: MaintenanceTask) -> bool:
        if (task.diagnosis_report or "").strip():
            return True
        if (task.advice_card or "").strip():
            return True
        timeline = task.execution_timeline or []
        timeline_types = {
            str(item.get("type") or "").strip().lower()
            for item in timeline
            if isinstance(item, dict)
        }
        return "done" in timeline_types or "report" in timeline_types

    def _extract_runtime_window(
        self, timeline: list[dict[str, Any]] | None
    ) -> tuple[datetime | None, datetime | None]:
        started_at: datetime | None = None
        finished_at: datetime | None = None
        for item in timeline or []:
            if not isinstance(item, dict):
                continue
            raw_time = str(item.get("time") or "").strip()
            if not raw_time:
                continue
            try:
                parsed = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            except ValueError:
                continue
            if started_at is None or parsed < started_at:
                started_at = parsed
            if finished_at is None or parsed > finished_at:
                finished_at = parsed
        return started_at, finished_at

    def _build_minimal_timeline(self, task: MaintenanceTask) -> list[dict[str, Any]]:
        if not self._has_final_diagnosis(task):
            return []

        created_at = task.created_at or datetime.now(timezone.utc)
        finished_at = task.updated_at or created_at
        total_seconds = max(int((finished_at - created_at).total_seconds()), 0)
        quarter = max(total_seconds // 4, 1) if total_seconds > 0 else 1
        stage_2_time = created_at + timedelta(seconds=quarter)
        stage_3_time = created_at + timedelta(seconds=quarter * 2)
        evidence_count = len(list(task.source_snapshot or []))
        planned_steps = len(list(task.steps or []))
        report_ready = bool((task.diagnosis_report or "").strip())

        report_description = (
            "系统已生成诊断报告，形成可展示的故障结论与处理建议。"
            if report_ready
            else "系统已整理诊断建议，形成可展示的处理结论。"
        )

        return [
            {
                "id": f"fallback-start-{task.id}",
                "type": "node_start",
                "title": "诊断任务接入",
                "description": "系统已接收诊断请求，开始同步任务上下文与设备信息。",
                "time": created_at.isoformat(),
            },
            {
                "id": f"fallback-retrieval-{task.id}",
                "type": "node_finish",
                "title": "知识检索与步骤整理",
                "description": f"已整理 {evidence_count} 条知识依据，并生成 {planned_steps} 个任务步骤。",
                "time": stage_2_time.isoformat(),
            },
            {
                "id": f"fallback-report-{task.id}",
                "type": "report",
                "title": "诊断报告生成",
                "description": report_description,
                "time": stage_3_time.isoformat(),
            },
            {
                "id": f"fallback-done-{task.id}",
                "type": "done",
                "title": "诊断结果已回写",
                "description": "系统已完成诊断，并已同步当前任务结果。",
                "time": finished_at.isoformat(),
            },
        ]

    def _parse_timeline_datetime(self, value: str | None) -> datetime | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _derive_step_runtime_states(
        self,
        steps_payload: list[dict[str, Any]],
        timeline: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        derived_steps = [dict(step, runtime_events=[]) for step in steps_payload]
        if not derived_steps:
            return derived_steps

        relevant_events: list[dict[str, Any]] = []
        for item in timeline or []:
            if not isinstance(item, dict):
                continue
            event_type = str(item.get("type") or "").strip().lower()
            if event_type not in {"node_start", "node_finish", "report", "done"}:
                continue
            relevant_events.append(item)

        if not relevant_events:
            return derived_steps

        current_step_index = 0
        for event in relevant_events:
            if current_step_index >= len(derived_steps):
                break
            step = derived_steps[current_step_index]
            parsed_time = self._parse_timeline_datetime(event.get("time"))
            event_payload = {
                "id": str(event.get("id") or ""),
                "type": str(event.get("type") or ""),
                "title": str(event.get("title") or "阶段更新"),
                "description": str(event.get("description") or ""),
                "time": str(event.get("time") or ""),
            }
            step["runtime_events"] = [*step.get("runtime_events", []), event_payload]

            if event_payload["type"] == "node_start":
                if step.get("started_at") is None:
                    step["started_at"] = parsed_time
                if step.get("status") not in {"completed", "skipped"}:
                    step["status"] = "in_progress"
                continue

            if step.get("started_at") is None:
                step["started_at"] = parsed_time
            if step.get("status") not in {"skipped"}:
                step["status"] = "completed"
            if step.get("completed_at") is None:
                step["completed_at"] = parsed_time
            current_step_index += 1

        if current_step_index < len(derived_steps):
            current_step = derived_steps[current_step_index]
            if current_step.get("status") == "pending" and current_step.get("started_at") is not None:
                current_step["status"] = "in_progress"

        return derived_steps

    async def _ensure_template(
        self,
        equipment_type: str,
        maintenance_level: str,
    ) -> MaintenanceTaskTemplate:
        stmt = (
            select(MaintenanceTaskTemplate)
            .options(selectinload(MaintenanceTaskTemplate.steps))
            .where(
                MaintenanceTaskTemplate.equipment_type == equipment_type,
                MaintenanceTaskTemplate.maintenance_level == maintenance_level,
            )
        )
        template = (await self.session.execute(stmt)).scalar_one_or_none()
        if template is not None:
            self._sync_template_step_resources(template)
            return template

        catalog = DEFAULT_TEMPLATE_CATALOG.get(equipment_type, GENERIC_TEMPLATE_CATALOG)
        template_spec = catalog.get(maintenance_level, GENERIC_TEMPLATE_CATALOG["standard"])

        template = MaintenanceTaskTemplate(
            equipment_type=equipment_type,
            maintenance_level=maintenance_level,
            name=template_spec["name"],
            description=template_spec["description"],
            status="published",
        )
        self.session.add(template)
        await self.session.flush()

        for index, item in enumerate(template_spec["steps"], start=1):
            resource_hint = self._get_step_resource_hint(item["title"])
            self.session.add(
                MaintenanceTaskTemplateStep(
                    template_id=template.id,
                    step_order=index,
                    title=item["title"],
                    instruction_template=item["instruction_template"],
                    risk_warning=item.get("risk_warning"),
                    caution=item.get("caution"),
                    confirmation_text=item.get("confirmation_text"),
                    required_tools=self._normalize_step_items(
                        item.get("required_tools") or resource_hint["required_tools"]
                    ),
                    required_materials=self._normalize_step_items(
                        item.get("required_materials") or resource_hint["required_materials"]
                    ),
                    estimated_minutes=item.get("estimated_minutes") or resource_hint["estimated_minutes"],
                )
            )

        await self.session.flush()
        refreshed_stmt = (
            select(MaintenanceTaskTemplate)
            .options(selectinload(MaintenanceTaskTemplate.steps))
            .where(MaintenanceTaskTemplate.id == template.id)
        )
        return (await self.session.execute(refreshed_stmt)).scalar_one()

    async def _load_knowledge_refs(self, chunk_ids: list[int]) -> list[dict[str, Any]]:
        if not chunk_ids:
            return []

        stmt = (
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeChunk.id.in_(chunk_ids))
            .order_by(KnowledgeChunk.id.asc())
        )
        rows = (await self.session.execute(stmt)).all()
        refs = []
        for chunk, document in rows:
            refs.append(
                {
                    "chunk_id": chunk.id,
                    "document_id": document.id,
                    "title": document.title,
                    "source_name": document.source_name,
                    "equipment_type": chunk.equipment_type,
                    "equipment_model": chunk.equipment_model,
                    "fault_type": chunk.fault_type,
                    "section_reference": chunk.section_reference or document.section_reference,
                    "section_path": chunk.section_path,
                    "step_anchor": chunk.step_anchor,
                    "page_reference": chunk.page_reference or document.page_reference,
                    "image_anchor": chunk.image_anchor,
                    "citation_label": f"C{len(refs) + 1}",
                    "excerpt": self._truncate_excerpt(chunk.content),
                    "retrieval_score": None,
                    "rerank_score": None,
                }
            )
        return refs

    def _build_task_title(self, data: MaintenanceTaskCreate) -> str:
        suffix = f" - {data.equipment_model}" if data.equipment_model else ""
        fault = f" / {data.fault_type}" if data.fault_type else ""
        return f"{data.equipment_type}{suffix}{fault}检修任务"

    def _build_advice_card(
        self,
        data: MaintenanceTaskCreate,
        knowledge_refs: list[dict[str, Any]],
    ) -> str:
        source_titles = "、".join(ref["title"] for ref in knowledge_refs[:3]) or "当前已选标准检修模板"
        symptom = data.symptom_description or "当前故障现象待现场进一步确认"
        fault_type = data.fault_type or "当前未明确故障类型"
        model = data.equipment_model or "未指定型号"

        return (
            f"智能建议：当前任务聚焦于 {data.equipment_type}（{model}）的“{fault_type}”问题。"
            f"请围绕“{symptom}”优先执行安全隔离、故障现象复核和关键部件排查。"
            f"本次建议主要依据 {source_titles} 生成，"
            f"{self._build_context_hint(data)}"
            f"若现场现象与引用知识不一致，应先记录差异再继续操作。"
        )

    def _render_instruction(
        self,
        template_text: str,
        data: MaintenanceTaskCreate,
        knowledge_refs: list[dict[str, Any]],
    ) -> str:
        source_titles = "、".join(ref["title"] for ref in knowledge_refs[:2]) or "当前标准模板"
        replacements = defaultdict(
            str,
            {
                "equipment_type": data.equipment_type,
                "equipment_model": data.equipment_model or "",
                "equipment_model_suffix": f"（{data.equipment_model}）" if data.equipment_model else "",
                "fault_type_text": data.fault_type or "当前故障现象",
                "symptom_text": data.symptom_description or "现场异常现象",
                "source_titles": source_titles,
            },
        )
        rendered = template_text.format_map(replacements)
        if knowledge_refs:
            rendered = f"{rendered} 本步引用：{source_titles}。"
        return rendered

    def _serialize_step(self, step: MaintenanceTaskStep, task: MaintenanceTask) -> dict[str, Any]:
        guardrails = MaintenanceSafetyService.build_step_guardrails(
            step_title=step.title,
            step_order=step.step_order,
            maintenance_level=task.maintenance_level,
            priority=task.priority,
            symptom_description=task.symptom_description,
            has_image=False,
            knowledge_locked=bool(step.knowledge_refs),
            risk_warning=step.risk_warning,
        )
        return {
            "id": step.id,
            "step_order": step.step_order,
            "title": step.title,
            "instruction": step.instruction,
            "risk_warning": step.risk_warning,
            "caution": step.caution,
            "confirmation_text": step.confirmation_text,
            "required_tools": self._normalize_step_items(step.required_tools),
            "required_materials": self._normalize_step_items(step.required_materials),
            "estimated_minutes": step.estimated_minutes,
            "status": step.status,
            "completion_note": step.completion_note,
            "completed_at": step.completed_at,
            "knowledge_refs": step.knowledge_refs or [],
            "safety_preconditions": guardrails["safety_preconditions"],
            "requires_manual_authorization": guardrails["requires_manual_authorization"],
            "authorization_hint": guardrails["authorization_hint"],
        }

    def _build_export_summary(self, task: dict[str, Any]) -> str:
        completed = task["completed_steps"]
        total = task["total_steps"]
        status_text = "已完成" if task["status"] == "completed" else "进行中"
        sources = "、".join(ref["title"] for ref in task["source_refs"][:3]) or "无外部知识引用"
        tools = "、".join(
            list(
                dict.fromkeys(
                    tool
                    for step in task.get("steps", [])
                    for tool in step.get("required_tools", [])
                )
            )[:4]
        )

        return (
            f"《{task['title']}》当前状态为{status_text}，共 {total} 个标准步骤，已完成 {completed} 个。"
            f"{self._build_export_context_line(task)}"
            f"{f'建议准备工具：{tools}。' if tools else ''}"
            f"本次作业主要依据 {sources} 生成作业指引，建议结合现场备注继续复核未完成步骤。"
        )

    def _truncate_excerpt(self, content: str, limit: int = 180) -> str:
        condensed = " ".join(content.split())
        if len(condensed) <= limit:
            return condensed
        return condensed[:limit] + "..."

    def _build_context_hint(self, data: MaintenanceTaskCreate) -> str:
        context_parts = []
        if data.work_order_id:
            context_parts.append(f"工单编号 {data.work_order_id}")
        if data.asset_code:
            context_parts.append(f"设备编号 {data.asset_code}")
        if data.report_source:
            context_parts.append(f"报修来源 {data.report_source}")
        if data.priority:
            context_parts.append(f"优先级 {self._format_priority(data.priority)}")
        if not context_parts:
            return ""
        return f"当前任务上下文为：{'，'.join(context_parts)}。"

    def _build_export_context_line(self, task: dict[str, Any]) -> str:
        context_parts = []
        if task.get("work_order_id"):
            context_parts.append(f"工单 {task['work_order_id']}")
        if task.get("asset_code"):
            context_parts.append(f"设备 {task['asset_code']}")
        if task.get("priority"):
            context_parts.append(f"优先级 {self._format_priority(task['priority'])}")
        if not context_parts:
            return ""
        return f"{'，'.join(context_parts)}。"

    def _format_priority(self, priority: str) -> str:
        return {
            "low": "低",
            "medium": "中",
            "high": "高",
            "urgent": "紧急",
        }.get(priority, priority)

    def _get_step_resource_hint(self, title: str) -> dict[str, Any]:
        return STEP_RESOURCE_HINTS.get(
            title,
            {"required_tools": [], "required_materials": [], "estimated_minutes": None},
        )

    def _normalize_step_items(self, values: list[str] | None) -> list[str]:
        if not values:
            return []
        return [str(item).strip() for item in values if str(item).strip()]

    def _sync_template_step_resources(self, template: MaintenanceTaskTemplate) -> None:
        for step in template.steps:
            resource_hint = self._get_step_resource_hint(step.title)
            if not step.required_tools:
                step.required_tools = self._normalize_step_items(resource_hint["required_tools"])
            if not step.required_materials:
                step.required_materials = self._normalize_step_items(resource_hint["required_materials"])
            if step.estimated_minutes is None:
                step.estimated_minutes = resource_hint["estimated_minutes"]


async def finalize_maintenance_task_after_pipeline(task_id: int) -> None:
    """在独立会话中完结检修任务（供 SSE 等无注入 session 的场景调用）。"""
    from app.db.session import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        await MaintenanceTaskService(session).complete_task_after_pipeline_success(task_id)


__all__ = ["MaintenanceTaskService", "finalize_maintenance_task_after_pipeline"]
