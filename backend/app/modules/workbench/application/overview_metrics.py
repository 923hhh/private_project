"""Workbench overview metric helpers."""
from __future__ import annotations

from typing import Any


def build_quality_highlights(
    *,
    published_documents: int,
    knowledge_chunks: int,
    active_tasks: int,
    pending_cases: int,
) -> list[dict[str, str]]:
    return [
        {
            "key": "overview_documents",
            "label": "知识文档数",
            "value": str(published_documents),
            "description": "已发布到知识库的文档",
            "accent": "cyan",
        },
        {
            "key": "overview_chunks",
            "label": "知识分段数",
            "value": str(knowledge_chunks),
            "description": "可用于检索的内容分段",
            "accent": "blue",
        },
        {
            "key": "overview_tasks",
            "label": "进行中任务",
            "value": str(active_tasks),
            "description": "当前仍在处理的检修任务",
            "accent": "green",
        },
        {
            "key": "overview_cases",
            "label": "待审核案例",
            "value": str(pending_cases),
            "description": "等待复核与沉淀的案例",
            "accent": "amber",
        },
    ]


def build_runtime_highlights(metrics_snapshot: dict[str, Any] | None) -> list[dict[str, str]]:
    snapshot = metrics_snapshot or {}
    counters = snapshot.get("counters") or []
    durations = snapshot.get("durations") or []

    def counter_total(name: str, **expected_labels: str) -> int:
        total = 0
        for item in counters:
            if item.get("name") != name:
                continue
            labels = item.get("labels") or {}
            if any(str(labels.get(key)) != str(value) for key, value in expected_labels.items()):
                continue
            total += int(item.get("value") or 0)
        return total

    def duration_avg(name: str) -> float:
        total_ms = 0.0
        total_count = 0
        for item in durations:
            if item.get("name") != name:
                continue
            total_ms += float(item.get("total_ms") or 0.0)
            total_count += int(item.get("count") or 0)
        if total_count <= 0:
            return 0.0
        return round(total_ms / total_count, 2)

    import_completed = counter_total("knowledge_import_jobs_completed_total")
    import_failed = counter_total("knowledge_import_jobs_failed_total")
    agent_completed = counter_total("agent_runs_persisted_total", status="completed")
    agent_failed = counter_total("agent_runs_persisted_total", status="failed")

    return [
        {
            "key": "runtime_search_requests",
            "label": "知识检索请求",
            "value": str(counter_total("knowledge_search_requests_total")),
            "description": f"平均 {duration_avg('knowledge_search_duration_ms'):.0f} ms",
            "accent": "cyan",
        },
        {
            "key": "runtime_agent_runs",
            "label": "Agent 协作运行",
            "value": str(counter_total("agent_assist_requests_total")),
            "description": f"已落库 {agent_completed}，失败 {agent_failed}",
            "accent": "blue",
        },
        {
            "key": "runtime_import_jobs",
            "label": "知识导入完成",
            "value": str(import_completed),
            "description": f"失败 {import_failed}，平均 {duration_avg('knowledge_import_processing_ms'):.0f} ms",
            "accent": "green",
        },
        {
            "key": "runtime_tool_calls",
            "label": "工具调用总量",
            "value": str(counter_total("agent_tool_calls_total")),
            "description": f"平均 {duration_avg('agent_tool_call_duration_ms'):.0f} ms",
            "accent": "amber",
        },
    ]
