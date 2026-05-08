"""Metrics helpers for TODO-SB-7 software cup evaluation."""
from __future__ import annotations

from typing import Any


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def build_scorecard(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Build aggregate metrics from per-case evaluation records."""
    retrieval_total = len(records)
    retrieval_hits = sum(1 for item in records if item.get("retrieval_hit"))
    top1_hits = sum(1 for item in records if item.get("top1_hit", item.get("retrieval_hit")))
    top3_hits = sum(1 for item in records if item.get("top3_hit", item.get("retrieval_hit")))
    same_model_records = [item for item in records if item.get("same_model_expected")]
    same_model_hits = sum(1 for item in same_model_records if item.get("same_model_hit"))

    cited_records = [item for item in records if item.get("retrieval_hit")]
    citation_hits = sum(1 for item in cited_records if item.get("citation_ok"))
    anchor_hits = sum(1 for item in cited_records if item.get("anchor_trace_ok"))

    workflow_records = [item for item in records if item.get("workflow_expected")]
    workflow_hits = sum(1 for item in workflow_records if item.get("workflow_completed"))

    feedback_records = [item for item in records if item.get("feedback_expected")]
    feedback_hits = sum(1 for item in feedback_records if item.get("feedback_hit"))

    agent_records = [item for item in records if item.get("agent_expected")]
    agent_hits = sum(1 for item in agent_records if item.get("agent_completed"))
    playback_hits = sum(1 for item in agent_records if item.get("run_playback_ok"))
    tool_hits = sum(1 for item in agent_records if item.get("tooling_ok"))
    authorization_records = [
        item for item in records if item.get("authorization_expected") is not None
    ]
    authorization_hits = sum(1 for item in authorization_records if item.get("authorization_ok"))

    categories: dict[str, dict[str, int]] = {}
    for item in records:
        category = str(item.get("category") or "unknown")
        bucket = categories.setdefault(category, {"total": 0, "hit": 0})
        bucket["total"] += 1
        if item.get("retrieval_hit"):
            bucket["hit"] += 1

    return {
        "case_count": retrieval_total,
        "retrieval": {
            "hits": retrieval_hits,
            "total": retrieval_total,
            "hit_rate": _safe_rate(retrieval_hits, retrieval_total),
            "top1_hits": top1_hits,
            "top1_hit_rate": _safe_rate(top1_hits, retrieval_total),
            "top3_hits": top3_hits,
            "top3_hit_rate": _safe_rate(top3_hits, retrieval_total),
            "same_model_hits": same_model_hits,
            "same_model_total": len(same_model_records),
            "same_model_hit_rate": _safe_rate(same_model_hits, len(same_model_records)),
        },
        "citation": {
            "hits": citation_hits,
            "total": len(cited_records),
            "coverage_rate": _safe_rate(citation_hits, len(cited_records)),
            "anchor_hits": anchor_hits,
            "anchor_trace_rate": _safe_rate(anchor_hits, len(cited_records)),
        },
        "workflow": {
            "hits": workflow_hits,
            "total": len(workflow_records),
            "completion_rate": _safe_rate(workflow_hits, len(workflow_records)),
        },
        "feedback": {
            "hits": feedback_hits,
            "total": len(feedback_records),
            "recall_rate": _safe_rate(feedback_hits, len(feedback_records)),
        },
        "agent": {
            "hits": agent_hits,
            "total": len(agent_records),
            "success_rate": _safe_rate(agent_hits, len(agent_records)),
            "playback_hits": playback_hits,
            "playback_rate": _safe_rate(playback_hits, len(agent_records)),
            "tool_hits": tool_hits,
            "tool_coverage_rate": _safe_rate(tool_hits, len(agent_records)),
            "authorization_hits": authorization_hits,
            "authorization_total": len(authorization_records),
            "authorization_hit_rate": _safe_rate(
                authorization_hits,
                len(authorization_records),
            ),
        },
        "category_breakdown": {
            name: {
                "hits": values["hit"],
                "total": values["total"],
                "hit_rate": _safe_rate(values["hit"], values["total"]),
            }
            for name, values in categories.items()
        },
    }


def build_quality_highlights(results_payload: dict[str, Any] | None) -> list[dict[str, str]]:
    """Build compact evaluation highlights for the workbench home page."""
    current = (((results_payload or {}).get("metrics") or {}).get("current_system") or {})
    retrieval = current.get("retrieval") or {}
    citation = current.get("citation") or {}
    workflow = current.get("workflow") or {}
    feedback = current.get("feedback") or {}
    agent = current.get("agent") or {}

    def fmt_rate(value: Any) -> str:
        try:
            return f"{float(value):.2f}%"
        except (TypeError, ValueError):
            return "0.00%"

    return [
        {
            "key": "eval_top1",
            "label": "Top1 命中率",
            "value": fmt_rate(retrieval.get("top1_hit_rate", retrieval.get("hit_rate", 0.0))),
            "description": f"{retrieval.get('top1_hits', retrieval.get('hits', 0))}/{retrieval.get('total', 0)}",
            "accent": "cyan",
        },
        {
            "key": "eval_top3",
            "label": "Top3 命中率",
            "value": fmt_rate(retrieval.get("top3_hit_rate", retrieval.get("hit_rate", 0.0))),
            "description": f"{retrieval.get('top3_hits', retrieval.get('hits', 0))}/{retrieval.get('total', 0)}",
            "accent": "blue",
        },
        {
            "key": "eval_anchor",
            "label": "来源回看覆盖率",
            "value": fmt_rate(citation.get("anchor_trace_rate", citation.get("coverage_rate", 0.0))),
            "description": f"{citation.get('anchor_hits', citation.get('hits', 0))}/{citation.get('total', 0)}",
            "accent": "green",
        },
        {
            "key": "eval_workflow",
            "label": "作业闭环完成率",
            "value": fmt_rate(workflow.get("completion_rate", 0.0)),
            "description": f"{workflow.get('hits', 0)}/{workflow.get('total', 0)}",
            "accent": "amber",
        },
        {
            "key": "eval_agent",
            "label": "Agent 成功率",
            "value": fmt_rate(agent.get("success_rate", 0.0)),
            "description": f"回放 {agent.get('playback_hits', 0)}/{agent.get('total', 0)}",
            "accent": "cyan",
        },
        {
            "key": "eval_feedback",
            "label": "案例回流召回率",
            "value": fmt_rate(feedback.get("recall_rate", 0.0)),
            "description": f"{feedback.get('hits', 0)}/{feedback.get('total', 0)}",
            "accent": "blue",
        },
    ]


def build_runtime_highlights(metrics_snapshot: dict[str, Any] | None) -> list[dict[str, str]]:
    """Build compact runtime highlights from in-process counters and durations."""
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
