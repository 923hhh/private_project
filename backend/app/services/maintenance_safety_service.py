"""Derived safety guardrails for maintenance planning and execution."""
from __future__ import annotations

from typing import Any


class MaintenanceSafetyService:
    """Build deterministic safety preconditions from task context."""

    HEAT_KEYWORDS = ("高温", "温度", "过热", "焦糊", "发热")
    FLUID_KEYWORDS = ("燃油", "机油", "漏油", "渗漏", "油路", "泄漏", "供油")
    ELECTRICAL_KEYWORDS = ("点火", "短路", "带电", "电路", "接插件")

    @classmethod
    def build_step_guardrails(
        cls,
        *,
        step_title: str,
        step_order: int,
        maintenance_level: str,
        priority: str | None,
        symptom_description: str | None,
        has_image: bool,
        knowledge_locked: bool,
        risk_warning: str | None = None,
    ) -> dict[str, Any]:
        """Return preconditions and approval hints for one maintenance step."""
        risk_flags = cls._classify_risk_flags(symptom_description, risk_warning, step_title)
        preconditions: list[str] = []
        blocking_issues: list[str] = []
        authorization_reasons: list[str] = []

        if step_order == 1 or any(keyword in step_title for keyword in ("安全", "隔离")):
            preconditions.append("确认设备已停机、断电并完成能量隔离。")
            preconditions.append("确认现场 PPE、照明和工位环境检查已完成。")
        else:
            preconditions.append("确认上一步已完成，并已记录现场结论。")

        if knowledge_locked:
            preconditions.append("已核对本步关联知识依据与现场现象一致。")
        else:
            preconditions.append("需先锁定知识依据并核对章节或页码。")
            blocking_issues.append("当前步骤缺少已锁定的知识依据。")

        if risk_flags["heat"]:
            preconditions.append("确认高温部位已冷却到可安全接触状态。")
        if risk_flags["fluid"]:
            preconditions.append("确认油路或压力源已泄压，并做好防泄漏处理。")
        if risk_flags["electrical"]:
            preconditions.append("确认电气回路已断开并完成绝缘检查。")
        if any(keyword in step_title for keyword in ("试车", "验证")):
            preconditions.append("确认试车区域已清场，并具备观察与紧急停机条件。")
        if has_image:
            preconditions.append("关键视觉识别结论已由人工复核。")

        requires_manual_authorization = False
        if maintenance_level == "emergency":
            requires_manual_authorization = True
            authorization_reasons.append("当前处于应急检修模式。")
        if (priority or "").lower() == "urgent":
            requires_manual_authorization = True
            authorization_reasons.append("当前工单优先级为紧急。")
        if any(keyword in step_title for keyword in ("试车", "恢复")) and (priority or "").lower() in {"high", "urgent"}:
            requires_manual_authorization = True
            authorization_reasons.append("高优先级任务进入试车或恢复验证阶段。")
        if risk_flags["fluid"] and any(keyword in step_title for keyword in ("维修", "复装", "应急")):
            requires_manual_authorization = True
            authorization_reasons.append("当前步骤涉及燃油或泄漏风险部件操作。")

        authorization_hint = None
        if requires_manual_authorization:
            authorization_hint = "；".join(cls._dedupe_strings(authorization_reasons)) or "当前步骤需人工授权确认。"

        return {
            "safety_preconditions": cls._dedupe_strings(preconditions)[:6],
            "requires_manual_authorization": requires_manual_authorization,
            "authorization_hint": authorization_hint,
            "blocking_issues": cls._dedupe_strings(blocking_issues),
        }

    @classmethod
    def build_run_guardrails(
        cls,
        *,
        maintenance_level: str,
        priority: str,
        symptom_description: str | None,
        has_image: bool,
        knowledge_locked: bool,
        task_preview: list[dict[str, Any]],
        telemetry_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return run-level checks, blockers and authorization hints."""
        risk_flags = cls._classify_risk_flags(symptom_description, None, None)
        required_checks = [
            "确认工单对象、故障现象和设备型号与现场一致。",
            "确认设备已停机、断电并完成基础能量隔离。",
        ]
        blocking_issues: list[str] = []
        warning_issues: list[str] = []
        authorization_reasons: list[str] = []

        if knowledge_locked:
            required_checks.append("已锁定至少一条知识依据并核对章节或页码。")
        else:
            required_checks.append("需先补充并锁定知识依据。")
            blocking_issues.append("当前未锁定知识依据，不建议直接下发执行。")

        if risk_flags["heat"]:
            required_checks.append("确认设备温度已降至安全阈值以下。")
        if risk_flags["fluid"]:
            required_checks.append("确认油路或压力源已完成泄压和防泄漏处理。")
        if risk_flags["electrical"]:
            required_checks.append("确认电气回路已断开并完成绝缘检查。")
        if has_image:
            required_checks.append("图片识别结论已完成人工复核。")
            warning_issues.append("图片识别线索只能作为辅助依据，关键结论仍需人工确认。")

        latest_temperature = telemetry_snapshot.get("latest_temperature") if telemetry_snapshot else None
        if isinstance(latest_temperature, (int, float)):
            if latest_temperature > 50:
                blocking_issues.append(f"最新遥测温度仍为 {latest_temperature:.1f}，尚未满足安全拆检阈值。")
            else:
                required_checks.append(f"最新遥测温度 {latest_temperature:.1f}，已满足冷却要求。")

        if maintenance_level == "emergency":
            authorization_reasons.append("当前工单为应急检修模式。")
        if priority == "urgent":
            authorization_reasons.append("当前工单优先级为紧急。")
        if any(step.get("requires_manual_authorization") for step in task_preview):
            authorization_reasons.append("后续步骤包含需人工授权的高风险操作。")

        return {
            "required_checks": cls._dedupe_strings(required_checks)[:6],
            "blocking_issues": cls._dedupe_strings(blocking_issues),
            "warning_issues": cls._dedupe_strings(warning_issues),
            "authorization_required": bool(authorization_reasons),
            "authorization_reasons": cls._dedupe_strings(authorization_reasons),
        }

    @classmethod
    def _classify_risk_flags(
        cls,
        symptom_description: str | None,
        risk_warning: str | None,
        step_title: str | None,
    ) -> dict[str, bool]:
        text = " ".join(
            item for item in [symptom_description or "", risk_warning or "", step_title or ""] if item
        )
        return {
            "heat": any(keyword in text for keyword in cls.HEAT_KEYWORDS),
            "fluid": any(keyword in text for keyword in cls.FLUID_KEYWORDS),
            "electrical": any(keyword in text for keyword in cls.ELECTRICAL_KEYWORDS),
        }

    @staticmethod
    def _dedupe_strings(values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped
