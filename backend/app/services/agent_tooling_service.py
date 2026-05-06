"""Agent tool registry and deterministic tool execution for the workbench."""
from __future__ import annotations

from time import perf_counter
from typing import Any

from app.core.metrics import increment_counter, observe_duration
from app.modules.assistant.schemas import AgentAssistRequest
from app.modules.cases.application.case_service import MaintenanceCaseService
from app.services.maintenance_safety_service import MaintenanceSafetyService
from app.services.sensor_service import SensorService


class AgentToolingService:
    """Run deterministic business tools and return auditable tool call records."""

    def __init__(self, session: Any):
        self.session = session
        self.sensor_service = SensorService(session)
        self.case_service = MaintenanceCaseService(session)

    async def run_tool_chain(
        self,
        *,
        request: AgentAssistRequest,
        knowledge_refs: list[dict[str, Any]],
        task_preview: list[dict[str, Any]],
        related_cases: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Execute the first batch of business tools for the Agent flow."""
        telemetry_call = await self._invoke_tool(
            "query_device_telemetry",
            self._query_device_telemetry,
            request=request,
        )
        history_call = await self._invoke_tool(
            "fetch_historical_repairs",
            self._fetch_historical_repairs,
            request=request,
            related_cases=related_cases,
        )
        safety_call = await self._invoke_tool(
            "validate_safety_preconditions",
            self._validate_safety_preconditions,
            request=request,
            knowledge_refs=knowledge_refs,
            task_preview=task_preview,
            telemetry_call=telemetry_call,
        )
        authorization_call = await self._invoke_tool(
            "require_human_authorization",
            self._require_human_authorization,
            request=request,
            safety_call=safety_call,
        )

        return {
            "tool_calls": [telemetry_call, history_call, safety_call, authorization_call],
            "telemetry_call": telemetry_call,
            "history_call": history_call,
            "safety_call": safety_call,
            "authorization_call": authorization_call,
        }

    async def _invoke_tool(self, tool_name: str, handler, **kwargs: Any) -> dict[str, Any]:
        start = perf_counter()
        try:
            payload = await handler(**kwargs)
            payload.setdefault("tool_name", tool_name)
        except Exception as exc:  # pragma: no cover - defensive path
            payload = {
                "tool_name": tool_name,
                "title": self._get_tool_title(tool_name),
                "status": "failed",
                "summary": f"{self._get_tool_title(tool_name)}执行失败，已回退为人工确认。",
                "risk_level": "medium",
                "blocking": False,
                "requires_human_authorization": False,
                "input_summary": None,
                "details": [str(exc)],
                "output_payload": {"error": str(exc)},
            }
        duration_ms = int((perf_counter() - start) * 1000)
        await increment_counter("agent_tool_calls_total", tool_name=tool_name, status=payload["status"])
        await observe_duration(
            "agent_tool_call_duration_ms",
            duration_ms,
            tool_name=tool_name,
            status=payload["status"],
        )
        return payload

    async def _query_device_telemetry(self, *, request: AgentAssistRequest) -> dict[str, Any]:
        input_summary = request.asset_code or request.work_order_id or request.equipment_model or request.equipment_type
        if not hasattr(self.session, "execute"):
            return {
                "title": "设备遥测查询",
                "status": "unavailable",
                "summary": "当前环境未接入可读遥测数据，后续需结合现场点检结果执行。",
                "risk_level": "low",
                "blocking": False,
                "requires_human_authorization": False,
                "input_summary": input_summary,
                "details": ["未检测到可用数据库会话，跳过实时遥测读取。"],
                "output_payload": {"available": False},
            }

        record_count = await self.sensor_service.count()
        if record_count <= 0:
            return {
                "title": "设备遥测查询",
                "status": "no_data",
                "summary": "当前没有可用的实时遥测记录，需按知识依据和现场点检执行。",
                "risk_level": "low",
                "blocking": False,
                "requires_human_authorization": False,
                "input_summary": input_summary,
                "details": ["传感器表中暂无可用记录。"],
                "output_payload": {"available": False},
            }

        latest_records = await self.sensor_service.get_latest(limit=1)
        if not latest_records:
            return {
                "title": "设备遥测查询",
                "status": "no_data",
                "summary": "当前没有可用的最近遥测记录，需按知识依据和现场点检执行。",
                "risk_level": "low",
                "blocking": False,
                "requires_human_authorization": False,
                "input_summary": input_summary,
                "details": ["传感器表计数存在，但未能读取最近一条记录。"],
                "output_payload": {"available": False},
            }

        latest = latest_records[0]
        temperature = next(
            (
                value
                for value in [getattr(latest, "dm_tit01", None), getattr(latest, "dm_tit02", None)]
                if isinstance(value, (int, float))
            ),
            None,
        )
        pressure = next(
            (
                value
                for value in [getattr(latest, "dm_pit01", None), getattr(latest, "dm_pit02", None)]
                if isinstance(value, (int, float))
            ),
            None,
        )
        cooling = getattr(latest, "dm_cool_on", None)
        details = [f"最近遥测时间：{latest.timestamp.isoformat()}"]
        if isinstance(temperature, (int, float)):
            details.append(f"最近温度：{temperature:.1f}")
        if isinstance(pressure, (int, float)):
            details.append(f"最近压力：{pressure:.1f}")
        if cooling is not None:
            details.append(f"冷却状态：{'开启' if float(cooling) > 0 else '关闭'}")

        summary = "已读取最近一条遥测记录，可用于辅助现场风险判断。"
        if isinstance(temperature, (int, float)):
            summary = f"已读取最近遥测记录，当前关键温度约 {temperature:.1f}。"

        return {
            "title": "设备遥测查询",
            "status": "completed",
            "summary": summary,
            "risk_level": "medium" if isinstance(temperature, (int, float)) and temperature > 50 else "low",
            "blocking": False,
            "requires_human_authorization": False,
            "input_summary": input_summary,
            "details": details,
            "output_payload": {
                "available": True,
                "latest_temperature": temperature,
                "latest_pressure": pressure,
                "cooling_on": cooling,
            },
        }

    async def _fetch_historical_repairs(
        self,
        *,
        request: AgentAssistRequest,
        related_cases: list[dict[str, Any]],
    ) -> dict[str, Any]:
        references = related_cases or await self.case_service.recommend_cases(
            equipment_type=request.equipment_type,
            equipment_model=request.equipment_model,
            fault_type=request.fault_type or request.query,
            limit=3,
        )
        if not references:
            return {
                "title": "历史维修案例查询",
                "status": "no_data",
                "summary": "当前未找到可直接复用的历史维修案例。",
                "risk_level": "low",
                "blocking": False,
                "requires_human_authorization": False,
                "input_summary": request.equipment_model or request.equipment_type,
                "details": ["相似案例库暂无稳定命中。"],
                "output_payload": {"case_count": 0},
            }

        top_case = references[0]
        return {
            "title": "历史维修案例查询",
            "status": "completed",
            "summary": f"已命中 {len(references)} 条相似案例，首条为《{top_case['title']}》。",
            "risk_level": "low",
            "blocking": False,
            "requires_human_authorization": False,
            "input_summary": request.equipment_model or request.equipment_type,
            "details": [item["match_reason"] for item in references[:3] if item.get("match_reason")],
            "output_payload": {"case_count": len(references), "top_case_id": top_case["id"]},
        }

    async def _validate_safety_preconditions(
        self,
        *,
        request: AgentAssistRequest,
        knowledge_refs: list[dict[str, Any]],
        task_preview: list[dict[str, Any]],
        telemetry_call: dict[str, Any],
    ) -> dict[str, Any]:
        guardrails = MaintenanceSafetyService.build_run_guardrails(
            maintenance_level=request.maintenance_level,
            priority=request.priority,
            symptom_description=request.query or request.fault_type,
            has_image=bool(request.image_base64),
            knowledge_locked=bool(knowledge_refs),
            task_preview=task_preview,
            telemetry_snapshot=telemetry_call.get("output_payload") or {},
        )
        blocking = bool(guardrails["blocking_issues"])
        details = list(guardrails["required_checks"])
        details.extend(guardrails["warning_issues"])
        details.extend(guardrails["blocking_issues"])
        summary = "前置安全条件已完成规则校验，可结合现场确认继续执行。"
        status = "passed"
        if blocking:
            status = "blocked"
            summary = "存在未满足的前置安全条件，当前不建议直接下发执行。"
        elif guardrails["warning_issues"] or guardrails["authorization_required"]:
            status = "attention"
            summary = "前置安全条件已校验，但仍需人工关注高风险约束。"

        return {
            "title": "前置条件合规校验",
            "status": status,
            "summary": summary,
            "risk_level": "high" if blocking else "medium",
            "blocking": blocking,
            "requires_human_authorization": guardrails["authorization_required"],
            "input_summary": request.maintenance_level,
            "details": details[:8],
            "output_payload": guardrails,
        }

    async def _require_human_authorization(
        self,
        *,
        request: AgentAssistRequest,
        safety_call: dict[str, Any],
    ) -> dict[str, Any]:
        safety_output = safety_call.get("output_payload") or {}
        reasons = list(safety_output.get("authorization_reasons") or [])
        if request.maintenance_level == "emergency" and "当前工单为应急检修模式。" not in reasons:
            reasons.append("当前工单为应急检修模式。")
        if request.priority == "urgent" and "当前工单优先级为紧急。" not in reasons:
            reasons.append("当前工单优先级为紧急。")

        required = bool(reasons)
        summary = "当前工单无需额外人工授权，可按标准流程推进。"
        status = "not_required"
        if required:
            status = "required"
            summary = "当前工单命中高风险条件，关键步骤执行前需人工授权。"

        return {
            "title": "人工授权判定",
            "status": status,
            "summary": summary,
            "risk_level": "high" if required else "low",
            "blocking": required,
            "requires_human_authorization": required,
            "input_summary": request.priority,
            "details": reasons[:5] if reasons else ["当前工单未触发额外授权规则。"],
            "output_payload": {
                "authorization_required": required,
                "authorization_reasons": reasons[:5],
            },
        }

    @staticmethod
    def _get_tool_title(tool_name: str) -> str:
        return {
            "query_device_telemetry": "设备遥测查询",
            "fetch_historical_repairs": "历史维修案例查询",
            "validate_safety_preconditions": "前置条件合规校验",
            "require_human_authorization": "人工授权判定",
        }.get(tool_name, tool_name)
